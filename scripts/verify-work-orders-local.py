"""Real Phase 7 maintenance work orders and approval workflow HTTP verification on disposable PostgreSQL.
Requires explicit SENTINEL_TEST_ADMIN_URL or reads .runtime/postgres.env; never resets existing database.
Uses verified model/data and writes sanitized verification evidence to reports/phase7-http.json.
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
from sentinel.ingestion.importer import load_selection
from sentinel.inference import Predictor


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

        # Bootstrap tenants and users
        pwd = new_token()
        t_a, u_admin_a = bootstrap(database, 'org-a', 'Organization A', 'admin-a@example.com', pwd, 'Admin A')
        t_b, u_admin_b = bootstrap(database, 'org-b', 'Organization B', 'admin-b@example.com', pwd, 'Admin B')

        with database.transaction() as s:
            u_mgr = create_user(s, 'manager-a@example.com', pwd, 'Plant Manager A')
            s.execute(text("INSERT INTO memberships(tenant_id, user_id, roles) VALUES (:t, :u, ARRAY['plant_manager'])"), dict(t=t_a, u=u_mgr))
            u_tech = create_user(s, 'tech-a@example.com', pwd, 'Technician A')
            s.execute(text("INSERT INTO memberships(tenant_id, user_id, roles) VALUES (:t, :u, ARRAY['technician'])"), dict(t=t_a, u=u_tech))
            u_viewer = create_user(s, 'viewer-a@example.com', pwd, 'Viewer A')
            s.execute(text("INSERT INTO memberships(tenant_id, user_id, roles) VALUES (:t, :u, ARRAY['viewer'])"), dict(t=t_a, u=u_viewer))

        # Dynamically allocate loopback port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        sock = None
        origin = f'http://127.0.0.1:{port}'

        default_settings = load_settings()
        app_settings = replace(
            default_settings,
            database_url=raw,
            auth_enabled=True,
            auth_localhost=True,
            auth_origins=(origin,),
        )
        app = create_app(settings=app_settings)

        uv_config = uvicorn.Config(app=app, host='127.0.0.1', port=port, log_level='error')
        server = uvicorn.Server(uv_config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        # Wait for server ready
        ready = False
        for _ in range(50):
            try:
                with httpx.Client(base_url=origin, timeout=1.0) as chk:
                    if chk.get('/health').status_code == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(0.1)
        if not ready:
            raise RuntimeError(f"Server failed to start on {origin}")

        # Start verification workflow
        evidence_log = {
            'phase': 'Phase 7 - Maintenance Work Orders and Human Approval Workflow',
            'transport': 'real HTTP loopback',
            'database': 'disposable PostgreSQL 18',
            'migration': '0006_work_orders',
            'http_statuses': {},
        }

        # Helper login
        def client_login(email):
            client = httpx.Client(base_url=origin, timeout=10.0)
            res = client.post('/api/v1/auth/login', json={'email': email, 'password': pwd}, headers={'Origin': origin, 'X-CSRF-Protection': '1'})
            assert res.status_code == 200, res.text
            csrf = res.json()['csrf_token']
            return client, {'Origin': origin, 'X-CSRF-Token': csrf}

        client_admin_a, h_admin_a = client_login('admin-a@example.com')
        client_mgr, h_mgr = client_login('manager-a@example.com')
        client_tech, h_tech = client_login('tech-a@example.com')
        client_viewer, h_viewer = client_login('viewer-a@example.com')
        client_admin_b, h_admin_b = client_login('admin-b@example.com')

        evidence_log['http_statuses']['login_admin_a'] = 200
        evidence_log['http_statuses']['login_manager'] = 200
        evidence_log['http_statuses']['login_tech'] = 200
        evidence_log['http_statuses']['login_viewer'] = 200
        evidence_log['http_statuses']['login_admin_b'] = 200

        # Step 1: Register machine, ingest observations, and create available prediction
        source, rows = load_selection(ROOT / 'data/raw', 'FD001', 'test', 1)
        mach_payload = {
            'asset_code': 'VERIFY-FD001-ENG1',
            'name': 'Turbofan verification engine 1',
            'machine_type': 'cmapss_engine',
            'data_source': 'nasa_replay',
            'source_binding': {'dataset': 'C-MAPSS', 'subset': 'FD001', 'split': 'test', 'engine_id': 1},
        }
        r_mach = client_admin_a.post(f'/api/v1/organizations/{t_a}/machines', headers=h_admin_a, json=mach_payload)
        assert r_mach.status_code == 201, r_mach.text
        mach_data = r_mach.json()['machine']
        mach_id = mach_data['id']
        path = mach_data['detail_api_path']
        evidence_log['http_statuses']['register_machine'] = 201

        # Ingest 31 cycles
        r_ingest = client_admin_a.post(path + '/replay-batches', headers={**h_admin_a, 'Idempotency-Key': 'ingest-v7-1'}, json={'source': source, 'observations': rows})
        assert r_ingest.status_code == 200, r_ingest.text
        evidence_log['http_statuses']['ingest_observations'] = 200

        # Compute prediction
        r_pred = client_admin_a.post(f'/api/v1/machines/{mach_id}/predictions', headers=h_admin_a)
        assert r_pred.status_code == 200, r_pred.text
        pred_data = r_pred.json()['prediction']
        pred_id = pred_data['id']
        evidence_log['http_statuses']['create_prediction'] = 200
        evidence_log['prediction_sample'] = {
            'id': pred_id,
            'status': pred_data['status'],
            'rul_cycles': pred_data['rul_cycles'],
            'priority_band': pred_data['priority_band'],
            'model_version': pred_data['model_version'],
        }

        # Step 2: Create prediction-linked draft work order
        r_draft = client_admin_a.post(f'/api/v1/predictions/{pred_id}/work-order-draft', headers=h_admin_a)
        assert r_draft.status_code == 200, r_draft.text
        wo_draft = r_draft.json()['work_order']
        wo_id = wo_draft['id']
        evidence_log['http_statuses']['create_prediction_draft'] = 200
        evidence_log['draft_work_order_sample'] = wo_draft

        # Step 3: Repeat creation and demonstrate deduplication (returns existing with already_active: true)
        r_dedup = client_admin_a.post(f'/api/v1/predictions/{pred_id}/work-order-draft', headers=h_admin_a)
        assert r_dedup.status_code == 200, r_dedup.text
        wo_dedup = r_dedup.json()['work_order']
        assert wo_dedup['id'] == wo_id
        assert wo_dedup['already_active'] is True
        evidence_log['http_statuses']['deduplication_repeat_draft'] = 200
        evidence_log['deduplication_sample'] = {
            'id': wo_dedup['id'],
            'already_active': wo_dedup['already_active'],
            'work_order_number': wo_dedup['work_order_number'],
            'status': wo_dedup['status'],
        }

        # Step 4: Approve as Plant Manager
        r_appr = client_mgr.post(f'/api/v1/work-orders/{wo_id}/transitions', headers=h_mgr, json={'action': 'approve', 'version': 1})
        assert r_appr.status_code == 200, r_appr.text
        wo_appr = r_appr.json()['work_order']
        assert wo_appr['status'] == 'approved'
        assert wo_appr['version'] == 2
        evidence_log['http_statuses']['approve_as_manager'] = 200
        evidence_log['approved_sample'] = {
            'status': wo_appr['status'],
            'version': wo_appr['version'],
        }

        # Step 5: Assign eligible technician
        r_assign = client_mgr.post(f'/api/v1/work-orders/{wo_id}/assignment', headers=h_mgr, json={'technician_id': str(u_tech), 'version': 2, 'reason': 'Assigned to day shift specialist'})
        assert r_assign.status_code == 200, r_assign.text
        wo_assign = r_assign.json()['work_order']
        assert wo_assign['assigned_technician_id'] == str(u_tech)
        assert wo_assign['version'] == 3
        evidence_log['http_statuses']['assign_technician'] = 200

        # Step 6: Start work as that technician (approved -> in_progress)
        r_start = client_tech.post(f'/api/v1/work-orders/{wo_id}/transitions', headers=h_tech, json={'action': 'start', 'version': 3})
        assert r_start.status_code == 200, r_start.text
        wo_start = r_start.json()['work_order']
        assert wo_start['status'] == 'in_progress'
        assert wo_start['version'] == 4
        evidence_log['http_statuses']['start_work_as_technician'] = 200

        # Step 7: Block with a reason, then resume
        r_block = client_tech.post(f'/api/v1/work-orders/{wo_id}/transitions', headers=h_tech, json={
            'action': 'block', 'version': 4, 'reason': 'Waiting for borescope probe calibration certificate'
        })
        assert r_block.status_code == 200, r_block.text
        wo_block = r_block.json()['work_order']
        assert wo_block['status'] == 'blocked'
        assert wo_block['version'] == 5
        evidence_log['http_statuses']['block_with_reason'] = 200

        r_resume = client_tech.post(f'/api/v1/work-orders/{wo_id}/transitions', headers=h_tech, json={'action': 'resume', 'version': 5})
        assert r_resume.status_code == 200, r_resume.text
        wo_resume = r_resume.json()['work_order']
        assert wo_resume['status'] == 'in_progress'
        assert wo_resume['block_reason'] is None
        assert wo_resume['version'] == 6
        evidence_log['http_statuses']['resume_work'] = 200

        # Add technician note
        r_note = client_tech.post(f'/api/v1/work-orders/{wo_id}/notes', headers=h_tech, json={
            'version': wo_resume['version'],
            'note_text': 'Replay verification only: review recorded; no physical inspection or diagnosis claimed.'
        })
        assert r_note.status_code == 200, r_note.text
        evidence_log['http_statuses']['add_technician_note'] = 200
        evidence_log['note_sample'] = r_note.json()['note']

        # Step 8: Complete with a summary
        r_comp = client_tech.post(f'/api/v1/work-orders/{wo_id}/transitions', headers=h_tech, json={
            'action': 'complete',
            'version': r_note.json()['work_order_version'],
            'completion_summary': 'Replay verification completed by the test user; no physical repair or machine health claim.',
        })
        assert r_comp.status_code == 200, r_comp.text
        wo_comp = r_comp.json()['work_order']
        assert wo_comp['status'] == 'completed'
        assert wo_comp['completed_at'] is not None
        assert wo_comp['version'] == 8
        evidence_log['http_statuses']['complete_work_order'] = 200
        evidence_log['completed_sample'] = {
            'status': wo_comp['status'],
            'completion_summary': wo_comp['completion_summary'],
            'completed_at': wo_comp['completed_at'],
            'version': wo_comp['version'],
        }

        # Step 9: Retrieve full history
        r_hist = client_admin_a.get(f'/api/v1/work-orders/{wo_id}/history', headers=h_admin_a)
        assert r_hist.status_code == 200, r_hist.text
        hist = r_hist.json()
        assert len(hist['transitions']) >= 5
        assert len(hist['assignments']) >= 1
        assert len(hist['notes']) >= 1
        evidence_log['http_statuses']['get_work_order_history'] = 200
        evidence_log['history_summary'] = {
            'total_transitions': len(hist['transitions']),
            'total_assignments': len(hist['assignments']),
            'total_notes': len(hist['notes']),
            'transitions_flow': [f"{t['from_status']} -> {t['to_status']} ({t['reason']})" for t in hist['transitions']],
        }

        # Step 10: Demonstrate forbidden transition (completed is terminal)
        r_forbidden = client_mgr.post(f'/api/v1/work-orders/{wo_id}/transitions', headers=h_mgr, json={
            'action': 'cancel', 'version': wo_comp['version'], 'reason': 'Attempt to cancel terminal work order'
        })
        assert r_forbidden.status_code == 400
        evidence_log['http_statuses']['forbidden_terminal_transition'] = 400

        # Step 11: Demonstrate cross-tenant denial
        r_cross_read = client_admin_b.get(f'/api/v1/work-orders/{wo_id}', headers=h_admin_b)
        assert r_cross_read.status_code == 404
        r_cross_write = client_admin_b.post(f'/api/v1/work-orders/{wo_id}/notes', headers=h_admin_b, json={'version': wo_comp['version'], 'note_text': 'Attack'})
        assert r_cross_write.status_code == 404
        evidence_log['http_statuses']['cross_tenant_read_denial'] = 404
        evidence_log['http_statuses']['cross_tenant_write_denial'] = 404

        # Corrective verification: actual HTTP rejection of the assessment findings.
        def checked(label, response, expected=200):
            evidence_log['http_statuses'][label] = response.status_code
            assert response.status_code == expected, response.text
            return response.json()

        source2, rows2 = load_selection(ROOT / 'data/raw', 'FD001', 'test', 2)
        machine2 = checked('fix_register_second_trajectory', client_admin_a.post(
            f'/api/v1/organizations/{t_a}/machines', headers=h_admin_a,
            json={**mach_payload, 'asset_code':'VERIFY-FIX-ENGINE2',
                  'source_binding':{'subset':'FD001','split':'test','engine_id':2}}), 201)['machine']
        path2 = machine2['detail_api_path']
        checked('fix_ingest_cutoff30', client_admin_a.post(path2+'/replay-batches',
            headers={**h_admin_a,'Idempotency-Key':'fix-initial'},json={'source':source2,'observations':rows2[:30]}))
        p2 = checked('fix_prediction_cutoff30', client_admin_a.post(path2+'/predictions',headers=h_admin_a,
            json={'cutoff_cycle':30}))['prediction']
        w2 = checked('fix_create_draft',client_admin_a.post(f"/api/v1/predictions/{p2['id']}/work-order-draft",headers=h_admin_a))['work_order']
        checked('fix_advance_observations',client_admin_a.post(path2+'/replay-batches',
            headers={**h_admin_a,'Idempotency-Key':'fix-advance'},json={'source':source2,'observations':rows2[30:31]}))
        rejected = checked('fix_outdated_approval_denied',client_mgr.post(f"/api/v1/work-orders/{w2['id']}/transitions",
            headers=h_mgr,json={'version':w2['version'],'action':'approve'}),409)
        assert rejected['error']['code']=='outdated_evidence'

        manual = checked('fix_manual_draft',client_admin_a.post('/api/v1/work-orders',headers=h_admin_a,
            json={'machine_id':mach_id,'title':'Replay permission verification',
                  'description':'Test record only','due_date':'2030-01-01'}))['work_order']
        manual_path = '/api/v1/work-orders/'+manual['id']
        manual = checked('fix_approve_manual',client_mgr.post(manual_path+'/transitions',headers=h_mgr,
            json={'version':manual['version'],'action':'approve'}))['work_order']
        manual = checked('fix_assign_manual',client_mgr.post(manual_path+'/assignment',headers=h_mgr,
            json={'version':manual['version'],'technician_id':str(u_tech)}))['work_order']
        manual = checked('fix_start_manual',client_tech.post(manual_path+'/transitions',headers=h_tech,
            json={'version':manual['version'],'action':'start'}))['work_order']
        # Test setup revokes execution while preserving the user's valid session.
        with database.transaction() as session:
            session.execute(text("UPDATE memberships SET roles=ARRAY['viewer']::text[] WHERE tenant_id=:t AND user_id=:u"),
                            dict(t=t_a,u=u_tech))
        checked('fix_demoted_assignee_denied',client_tech.post(manual_path+'/transitions',headers=h_tech,
            json={'version':manual['version'],'action':'complete','completion_summary':'Test-only completion'}),403)
        note = checked('fix_versioned_note',client_mgr.post(manual_path+'/notes',headers=h_mgr,
            json={'version':manual['version'],'note_text':'Manager recorded the revoked assignment for review.'}))
        assert note['work_order_version']==manual['version']+1
        checked('fix_stale_note_denied',client_mgr.post(manual_path+'/notes',headers=h_mgr,
            json={'version':manual['version'],'note_text':'Stale retry must not be stored'}),409)
        filtered = checked('fix_date_filters',client_mgr.get('/api/v1/work-orders',params={
            'created_from':manual['created_at'],'created_to':manual['created_at'],
            'due_from':'2030-01-01','due_to':'2030-01-01'}))
        assert filtered['total']==1 and filtered['items'][0]['id']==manual['id']
        evidence_log['corrective_verification'] = dict(outdated_approval_error=rejected['error']['code'],
            demoted_execution_status=403,stale_note_status=409,note_version=note['work_order_version'],filtered_count=filtered['total'])

        # Step 12: Confirm existing model artifacts remain unchanged
        check_res = verify_and_prepare(default_settings, ROOT / 'data/raw', ROOT / '.runtime/replay-engine1.json')
        assert check_res['bundle_verified'] is True
        assert check_res['fd001_files_verified'] == 3
        evidence_log['model_integrity'] = check_res

        # Write evidence log
        report_path = ROOT / 'reports/phase7-http.json'
        report_path.write_text(json.dumps(evidence_log, indent=2) + '\n', encoding='utf-8')
        print(f"Real HTTP loopback verification succeeded. Evidence saved to {report_path}")

    finally:
        if server:
            server.should_exit = True
        if thread and thread.is_alive():
            thread.join(timeout=3)
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
