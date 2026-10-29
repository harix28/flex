"""Real Phase 6 persistent predictions and maintenance priority HTTP verification on disposable PostgreSQL.
Requires explicit SENTINEL_TEST_ADMIN_URL or uses .runtime/postgres.env for testing; never resets an existing database.
Uses the existing verified model/data and writes sanitized verification evidence.
"""
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
from dataclasses import replace
from uuid import UUID, uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sentinel.config import ROOT, load_settings, validate_database_url
from sentinel.check import verify_and_prepare
from sentinel.api import create_app
from sentinel.db import Database
from sentinel.auth.security import new_token
from sentinel.auth.service import bootstrap, create_user
from sentinel.ingestion.importer import load_selection, authenticated_import
from sentinel.inference import Predictor
from sentinel.data import COLUMNS


def main():
    raw_admin = os.environ.get('SENTINEL_TEST_ADMIN_URL')
    if not raw_admin:
        env_file = ROOT / '.runtime/postgres.env'
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith('DATABASE_URL='):
                    db_url = line.split('=', 1)[1].strip()
                    val = validate_database_url(db_url)
                    raw_admin = val.set(database='postgres').render_as_string(hide_password=False)
                    break
    if not raw_admin:
        raise RuntimeError('SENTINEL_TEST_ADMIN_URL or .runtime/postgres.env required')

    url = validate_database_url(raw_admin)
    name = 'meridian_test_' + uuid4().hex
    admin = create_engine(url.set(database='postgres'), isolation_level='AUTOCOMMIT', hide_parameters=True, connect_args={'connect_timeout': 3})
    database = None
    server = None
    thread = None
    sock = None
    created = False

    try:
        with admin.connect() as c:
            c.exec_driver_sql('CREATE DATABASE ' + name)
            created = True

        raw = url.set(database=name).render_as_string(hide_password=False)
        config = Config(str(ROOT / 'alembic.ini'))
        config.attributes['database_url'] = raw
        command.upgrade(config, 'head')
        database = Database(raw)

        password = new_token()
        first, admin_a = bootstrap(database, 'verify-a', 'TEST Organization A', 'verify-admin-a@example.com', password, 'TEST Admin A')
        second, admin_b = bootstrap(database, 'verify-b', 'TEST Organization B', 'verify-admin-b@example.com', password, 'TEST Admin B')

        with database.transaction() as s:
            for role in ('viewer', 'technician', 'plant_manager'):
                uid = create_user(s, 'verify-' + role + '@example.com', password, 'TEST ' + role)
                s.execute(text('INSERT INTO memberships(tenant_id,user_id,roles) VALUES (:t,:u,:r)'), dict(t=first, u=uid, r=[role]))

        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        origin = 'http://127.0.0.1:' + str(port)

        settings = replace(load_settings(), database_url=raw, auth_enabled=True, auth_localhost=True, auth_origins=(origin,))
        model_check = verify_and_prepare(settings, ROOT / 'data/raw', ROOT / '.runtime/replay-engine1.json')

        app = create_app(settings=settings)
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, proxy_headers=False,
                                              access_log=False, log_config=None, log_level='critical'))
        thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
        thread.start()

        deadline = time.monotonic() + 15
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not server.started:
            raise RuntimeError('Verification HTTP server did not start')

        http_statuses = {}

        def expect(label, response, expected_status):
            http_statuses[label] = response.status_code
            if response.status_code != expected_status:
                raise RuntimeError(f'Unexpected HTTP status for {label}: got {response.status_code}, expected {expected_status}. Body: {response.text}')
            return response

        source, rows = load_selection(ROOT / 'data/raw', 'FD001', 'test', 1)

        with httpx.Client(base_url=origin, timeout=30, trust_env=False) as client:
            # 1. Authenticate Admin A
            login_a = expect('login_admin_a', client.post('/api/v1/auth/login', headers={'Origin': origin, 'X-CSRF-Protection': '1'},
                                                          json={'email': 'verify-admin-a@example.com', 'password': password}), 200)
            csrf_a = {'Origin': origin, 'X-CSRF-Token': login_a.json()['csrf_token']}
            base_a = f'/api/v1/organizations/{first}'

            # 2. Register FD001 test trajectory engine 1
            reg_resp = expect('register_machine', client.post(base_a + '/machines', headers=csrf_a, json={
                'asset_code': 'VERIFY-FD001-TEST-1',
                'name': 'SIMULATED verification engine 1',
                'machine_type': 'cmapss_engine',
                'data_source': 'nasa_replay',
                'source_binding': {'dataset': 'C-MAPSS', 'subset': 'FD001', 'split': 'test', 'engine_id': 1, 'file_sha256': source['file_sha256']}
            }), 201)
            machine = reg_resp.json()['machine']
            m_id = machine['id']
            m_path = machine['detail_api_path']

            # Ingest 31 observations
            import_result = authenticated_import(origin, 'verify-admin-a@example.com', password, first, m_id, source, rows, 10)
            assert import_result['inserted'] == 31

            # 3. Retrieve stored input window (cycles 2..31 = 30 observations)
            window_obs = expect('stored_window', client.get(m_path + '/observations?limit=50'), 200).json()
            assert len(window_obs['items']) >= 30

            # 4. Request persistent prediction (POST /api/v1/machines/{machine_id}/predictions)
            pred_resp = expect('create_prediction', client.post(f'/api/v1/machines/{m_id}/predictions', headers=csrf_a), 200)
            pred_data = pred_resp.json()['prediction']
            assert pred_data['status'] == 'available'
            assert pred_data['priority_band'] == 'low'
            assert pred_data['requested_cutoff_cycle'] == 31
            p_id = pred_data['id']

            # 5. Retrieve persisted history (GET /api/v1/machines/{machine_id}/predictions)
            history_resp = expect('list_predictions', client.get(f'/api/v1/machines/{m_id}/predictions'), 200)
            history_data = history_resp.json()
            assert history_data['total'] == 1
            assert history_data['items'][0]['id'] == p_id

            # Retrieve latest prediction (GET /api/v1/machines/{machine_id}/predictions/latest)
            latest_resp = expect('get_latest_prediction', client.get(f'/api/v1/machines/{m_id}/predictions/latest'), 200)
            latest_data = latest_resp.json()['prediction']
            assert latest_data['id'] == p_id
            assert latest_data['is_current'] is True
            assert latest_data['is_outdated'] is False

            # Retrieve prediction by ID (GET /api/v1/predictions/{prediction_id})
            detail_resp = expect('get_prediction_by_id', client.get(f'/api/v1/predictions/{p_id}'), 200)
            assert detail_resp.json()['prediction']['id'] == p_id

            # 6. Retrieve maintenance priority list (GET /api/v1/maintenance-priorities)
            priority_resp = expect('get_maintenance_priorities', client.get('/api/v1/maintenance-priorities'), 200)
            priority_data = priority_resp.json()
            assert len(priority_data['items']) == 1
            p_item = priority_data['items'][0]
            assert p_item['machine_id'] == m_id
            assert p_item['priority_band'] == 'low'
            assert p_item['is_current'] is True

            # 7. Compare result with direct existing-model inference (assert exact parity)
            predictor = Predictor(settings.model_dir, settings.bundle_sha256)
            records = [
                dict(zip(COLUMNS, [1, r['cycle']] + r['settings'] + r['sensors']))
                for r in rows if 2 <= r['cycle'] <= 31
            ]
            direct_result = predictor.predict('FD001', records)
            parity_diff = abs(pred_data['rul_cycles'] - direct_result['rul_cycles'])
            assert parity_diff < 1e-6
            print(f"Parity verified: persisted RUL={pred_data['rul_cycles']} cycles, direct inference RUL={direct_result['rul_cycles']} cycles (diff={parity_diff:.2e})")

            # 8. Demonstrate unavailable cases
            # Case A: Insufficient history (cutoff = 15 < window 30)
            unavail_hist = expect('unavailable_insufficient_history', client.post(
                f'/api/v1/machines/{m_id}/predictions', headers=csrf_a, json={'cutoff_cycle': 15}
            ), 200).json()['prediction']
            assert unavail_hist['status'] == 'unavailable'
            assert unavail_hist['reason'] == 'insufficient_history'
            assert unavail_hist['priority_band'] == 'unknown'

            # Case B: Unsupported physical machine
            phys_machine = expect('register_phys_machine', client.post(base_a + '/machines', headers=csrf_a, json={
                'asset_code': 'VERIFY-PHYS-1', 'name': 'Physical Pump', 'machine_type': 'centrifugal_pump', 'data_source': 'physical_device'
            }), 201).json()['machine']
            unavail_phys = expect('unavailable_phys_machine', client.post(
                f"/api/v1/machines/{phys_machine['id']}/predictions", headers=csrf_a
            ), 200).json()['prediction']
            assert unavail_phys['status'] == 'unavailable'
            assert unavail_phys['reason'] == 'unsupported_machine'

            # 9. Demonstrate cross-tenant denial
            login_b = expect('login_admin_b', client.post('/api/v1/auth/login', headers={'Origin': origin, 'X-CSRF-Protection': '1'},
                                                          json={'email': 'verify-admin-b@example.com', 'password': password}), 200)
            csrf_b = {'Origin': origin, 'X-CSRF-Token': login_b.json()['csrf_token']}

            expect('cross_tenant_predictions_list', client.get(f'/api/v1/machines/{m_id}/predictions'), 404)
            expect('cross_tenant_predictions_post', client.post(f'/api/v1/machines/{m_id}/predictions', headers=csrf_b), 404)
            expect('cross_tenant_predictions_latest', client.get(f'/api/v1/machines/{m_id}/predictions/latest'), 404)
            expect('cross_tenant_prediction_detail', client.get(f'/api/v1/predictions/{p_id}'), 404)

            # 10. Verify saved model artifacts remain unchanged
            final_model_check = verify_and_prepare(settings, ROOT / 'data/raw', ROOT / '.runtime/replay-engine1.json')
            assert final_model_check['bundle_verified'] is True
            assert final_model_check['fd001_files_verified'] == 3
            from sentinel.data import sha256
            model_hash = sha256(settings.model_dir / 'model.json')
            bundle_hash = sha256(settings.model_dir / 'bundle.json')

        # Persist report
        evidence = {
            'phase': 'Phase 6 - Persistent RUL Predictions and Maintenance Priority',
            'transport': 'real HTTP loopback',
            'database': 'disposable PostgreSQL 18',
            'migration': '0005_predictions',
            'http_statuses': http_statuses,
            'prediction_sample': pred_data,
            'latest_sample': latest_data,
            'maintenance_priority_sample': priority_data,
            'direct_inference_comparison': {
                'persisted_rul_cycles': pred_data['rul_cycles'],
                'direct_rul_cycles': direct_result['rul_cycles'],
                'parity_diff': parity_diff,
            },
            'unavailable_examples': {
                'insufficient_history': unavail_hist,
                'unsupported_machine': unavail_phys,
            },
            'model_integrity': {
                'model_sha256': model_hash,
                'bundle_sha256': bundle_hash,
                'artifacts_unchanged': True,
            }
        }

        report_file = ROOT / 'reports/phase6-http.json'
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')

        print("\n=== PHASE 6 REAL HTTP VERIFICATION SUMMARY ===")
        print(f"HTTP Statuses: {json.dumps(http_statuses, indent=2)}")
        print(f"\nPersisted Prediction Response:\n{json.dumps(pred_data, indent=2)}")
        print(f"\nMaintenance Priority Response:\n{json.dumps(priority_data, indent=2)}")
        print("\nAll 10 Phase 6 end-to-end verification steps succeeded.")

    finally:
        if server:
            server.should_exit = True
        if thread:
            thread.join(timeout=15)
        if sock:
            sock.close()
        if database:
            database.close()
        if created:
            with admin.connect() as c:
                c.exec_driver_sql('DROP DATABASE ' + name)
        admin.dispose()


if __name__ == '__main__':
    main()
