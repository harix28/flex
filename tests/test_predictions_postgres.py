"""PostgreSQL integration tests for persistent predictions, maintenance priorities, and causal window integrity."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4
from dataclasses import replace
import pytest
from starlette.testclient import TestClient
from sqlalchemy import text, inspect
from tests.test_postgres import db
from tests.test_auth_postgres import setup, login, ORIGIN
from tests.test_registry import machine_payload
from sentinel.api import create_app
from sentinel.ingestion.importer import load_selection
from sentinel.config import ROOT, load_settings
from sentinel.data import COLUMNS
from sentinel.inference import Predictor

pytestmark = pytest.mark.postgres

DEFAULT_SETTINGS = load_settings()


def pred_client(setup, **changes):
    s = replace(
        setup['settings'],
        model_dir=DEFAULT_SETTINGS.model_dir,
        bundle_sha256=DEFAULT_SETTINGS.bundle_sha256,
        **changes
    )
    return TestClient(create_app(settings=s), base_url=ORIGIN)


def registered_machine(c, setup, h, subset='FD001', engine_id=1, **extra):
    base = f"/api/v1/organizations/{setup['a']}"
    binding = {'dataset': 'C-MAPSS', 'subset': subset, 'split': 'test', 'engine_id': engine_id}
    payload = machine_payload(f'REPLAY-{subset}-{engine_id}', 'nasa_replay', machine_type='cmapss_engine', source_binding=binding, **extra)
    res = c.post(base + '/machines', headers=h, json=payload)
    assert res.status_code == 201, res.text
    return res.json()['machine']


def ingest_observations(c, path, h, rows, source, key='ingest-1'):
    body = {'source': source, 'observations': rows}
    res = c.post(path + '/replay-batches', headers={**h, 'Idempotency-Key': key}, json=body)
    assert res.status_code == 200, res.text
    return res.json()


def test_prediction_from_stored_observations_and_direct_parity(setup):
    """Verifies:
    1. Prediction from stored real-format observations.
    2. Exact parity with direct model inference on the same window.
    3. Input digest reproducibility.
    4. Deterministic priority policy output.
    5. No ground truth or future cycle leakage.
    """
    source, rows = load_selection(ROOT / 'data/raw', 'FD001', 'test', 1)
    with pred_client(setup) as c:
        h = login(c, setup)
        machine = registered_machine(c, setup, h)
        m_id = machine['id']
        path = machine['detail_api_path']

        # Ingest 31 cycles
        ingest_observations(c, path, h, rows, source)

        # Predict via POST /api/v1/machines/{machine_id}/predictions (omitted cutoff = latest cycle 31)
        res = c.post(f'/api/v1/machines/{m_id}/predictions', headers=h)
        assert res.status_code == 200, res.text
        data = res.json()['prediction']

        assert data['status'] == 'available'
        assert data['reason'] is None
        assert data['requested_cutoff_cycle'] == 31
        assert data['observed_cutoff_cycle'] == 31
        assert data['input_window_start_cycle'] == 2
        assert data['input_window_end_cycle'] == 31
        assert data['input_observation_count'] == 30
        assert data['priority_band'] == 'low'
        assert 'low priority' in data['priority_rule']
        assert data['failure_probability'] is None
        assert data['interval'] is None
        assert data['diagnosis_basis'] == 'unavailable'
        assert data['release_status'] == 'experiment_only'
        assert len(data['input_digest']) == 64
        assert len(data['model_digest']) == 64

        # Compare with direct inference using existing Predictor
        predictor = Predictor(DEFAULT_SETTINGS.model_dir, DEFAULT_SETTINGS.bundle_sha256)
        records = [
            dict(zip(COLUMNS, [1, r['cycle']] + r['settings'] + r['sensors']))
            for r in rows if 2 <= r['cycle'] <= 31
        ]
        direct = predictor.predict('FD001', records)
        assert abs(data['rul_cycles'] - direct['rul_cycles']) < 1e-6
        assert abs(data['rul_cycles'] - 136.21971130371094) < 1e-4

        # Verify idempotency on second call
        retry_res = c.post(f'/api/v1/machines/{m_id}/predictions', headers=h)
        assert retry_res.status_code == 200
        retry_data = retry_res.json()['prediction']
        assert retry_data['id'] == data['id']
        assert retry_data['idempotency_replayed'] is True


def test_cutoff_selection_and_no_future_leakage(setup):
    """Explicit cutoff cycle selects only observations <= cutoff."""
    source, rows = load_selection(ROOT / 'data/raw', 'FD001', 'test', 1)
    with pred_client(setup) as c:
        h = login(c, setup)
        machine = registered_machine(c, setup, h)
        m_id = machine['id']
        path = machine['detail_api_path']

        # Ingest 31 cycles
        ingest_observations(c, path, h, rows, source)

        # Request cutoff 30 (should select cycles 1..30)
        res30 = c.post(f'/api/v1/machines/{m_id}/predictions', headers=h, json={'cutoff_cycle': 30})
        assert res30.status_code == 200, res30.text
        data30 = res30.json()['prediction']
        assert data30['requested_cutoff_cycle'] == 30
        assert data30['input_window_start_cycle'] == 1
        assert data30['input_window_end_cycle'] == 30
        assert data30['input_observation_count'] == 30

        # Request cutoff 31 (should select cycles 2..31)
        res31 = c.post(f'/api/v1/machines/{m_id}/predictions', headers=h, json={'cutoff_cycle': 31})
        data31 = res31.json()['prediction']
        assert data31['requested_cutoff_cycle'] == 31
        assert data31['input_window_start_cycle'] == 2
        assert data31['input_window_end_cycle'] == 31

        # The input digests must differ because cycle 1 is in 30, but cycle 31 is in 31
        assert data30['input_digest'] != data31['input_digest']


def test_insufficient_history_and_gaps(setup):
    source, rows = load_selection(ROOT / 'data/raw', 'FD001', 'test', 1)
    with pred_client(setup) as c:
        h = login(c, setup)
        machine = registered_machine(c, setup, h)
        m_id = machine['id']
        path = machine['detail_api_path']

        # 1. No observations in stream
        res_empty = c.post(f'/api/v1/machines/{m_id}/predictions', headers=h)
        assert res_empty.status_code == 200, res_empty.text
        assert res_empty.json()['prediction']['status'] == 'unavailable'
        assert res_empty.json()['prediction']['reason'] == 'no_observations'
        assert res_empty.json()['prediction']['rul_cycles'] is None
        assert res_empty.json()['prediction']['priority_band'] == 'unknown'

        # 2. Insufficient history (< 30 cycles ingested)
        ingest_observations(c, path, h, rows[:10], source, key='batch-10')
        res_short = c.post(f'/api/v1/machines/{m_id}/predictions', headers=h, json={'cutoff_cycle': 10})
        assert res_short.status_code == 200
        assert res_short.json()['prediction']['status'] == 'unavailable'
        assert res_short.json()['prediction']['reason'] == 'insufficient_history'

        # 3. Gaps in history: ingest cycles 20..35, skipping 11..19
        ingest_observations(c, path, h, [r for r in rows if 20 <= r['cycle'] <= 35], source, key='batch-gap')
        res_gap = c.post(f'/api/v1/machines/{m_id}/predictions', headers=h, json={'cutoff_cycle': 35})
        assert res_gap.status_code == 200
        assert res_gap.json()['prediction']['status'] == 'unavailable'
        assert res_gap.json()['prediction']['reason'] == 'gaps_in_history'


def test_gap_filled_allows_new_successful_prediction(setup):
    """Demonstrates that an earlier gap failure is not permanently cached once the missing cycles are ingested."""
    source, rows = load_selection(ROOT / 'data/raw', 'FD001', 'test', 1)
    with pred_client(setup) as c:
        h = login(c, setup)
        machine = registered_machine(c, setup, h)
        m_id = machine['id']
        path = machine['detail_api_path']

        # Ingest cycles 1..28 and 30 (missing cycle 29)
        partial = [r for r in rows if r['cycle'] != 29 and r['cycle'] <= 30]
        ingest_observations(c, path, h, partial, source, key='gap-partial')

        # Predict cutoff 30 -> gap failure
        res_gap = c.post(f'/api/v1/machines/{m_id}/predictions', headers=h, json={'cutoff_cycle': 30})
        assert res_gap.json()['prediction']['status'] == 'unavailable'
        assert res_gap.json()['prediction']['reason'] == 'gaps_in_history'

        # Now backfill cycle 29
        cycle_29 = [r for r in rows if r['cycle'] == 29]
        ingest_observations(c, path, h, cycle_29, source, key='fill-29')

        # Predict cutoff 30 again -> now complete and available!
        res_success = c.post(f'/api/v1/machines/{m_id}/predictions', headers=h, json={'cutoff_cycle': 30})
        assert res_success.json()['prediction']['status'] == 'available'
        assert res_success.json()['prediction']['rul_cycles'] is not None


def test_unsupported_machine_and_subset(setup):
    with pred_client(setup) as c:
        h = login(c, setup)
        base = f"/api/v1/organizations/{setup['a']}"

        # Register physical machine
        phys_res = c.post(base + '/machines', headers=h, json=machine_payload('PHYS-1', 'physical_device'))
        phys_id = phys_res.json()['machine']['id']
        res_phys = c.post(f'/api/v1/machines/{phys_id}/predictions', headers=h)
        assert res_phys.status_code == 200
        assert res_phys.json()['prediction']['status'] == 'unavailable'
        assert res_phys.json()['prediction']['reason'] == 'unsupported_machine'

        # Register FD002 replay machine
        fd002_res = c.post(base + '/machines', headers=h, json=machine_payload(
            'FD002-1', 'nasa_replay', machine_type='cmapss_engine', source_binding={'dataset': 'C-MAPSS', 'subset': 'FD002', 'split': 'test', 'engine_id': 1}
        ))
        fd002_id = fd002_res.json()['machine']['id']
        res_fd002 = c.post(f'/api/v1/machines/{fd002_id}/predictions', headers=h)
        assert res_fd002.status_code == 200
        assert res_fd002.json()['prediction']['status'] == 'unavailable'
        assert res_fd002.json()['prediction']['reason'] == 'unsupported_subset'


def test_concurrency_and_race_safety(setup):
    source, rows = load_selection(ROOT / 'data/raw', 'FD001', 'test', 1)
    with pred_client(setup) as c:
        h = login(c, setup)
        machine = registered_machine(c, setup, h)
        m_id = machine['id']
        ingest_observations(c, machine['detail_api_path'], h, rows, source)

        barrier = Barrier(3)

        def make_request():
            with pred_client(setup) as client:
                client.cookies.update(c.cookies)
                barrier.wait(timeout=5)
                return client.post(f'/api/v1/machines/{m_id}/predictions', headers=h, json={'cutoff_cycle': 31})

        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda _: make_request(), range(3)))

        assert all(r.status_code == 200 for r in results)
        prediction_ids = {r.json()['prediction']['id'] for r in results}
        # Exactly one unique prediction record was inserted
        assert len(prediction_ids) == 1


def test_tenant_isolation_role_checks_and_csrf(setup):
    source, rows = load_selection(ROOT / 'data/raw', 'FD001', 'test', 1)
    with pred_client(setup) as c:
        h_a = login(c, setup, email='admin-a@example.com')
        machine = registered_machine(c, setup, h_a)
        m_id = machine['id']
        ingest_observations(c, machine['detail_api_path'], h_a, rows, source)

        # CSRF check: POST without CSRF header fails
        h_no_csrf = {k: v for k, v in h_a.items() if k.lower() != 'x-csrf-token'}
        assert c.post(f'/api/v1/machines/{m_id}/predictions', headers=h_no_csrf).status_code == 403

        # Create prediction as admin
        pred_res = c.post(f'/api/v1/machines/{m_id}/predictions', headers=h_a)
        assert pred_res.status_code == 200
        p_id = pred_res.json()['prediction']['id']

        # Viewer role check: viewer can read but cannot create
        h_viewer = login(c, setup, email='viewer@example.com')
        assert c.post(f'/api/v1/machines/{m_id}/predictions', headers=h_viewer).status_code == 403

        # Viewer can read list, latest, and detail
        assert c.get(f'/api/v1/machines/{m_id}/predictions', headers=h_viewer).status_code == 200
        assert c.get(f'/api/v1/machines/{m_id}/predictions/latest', headers=h_viewer).status_code == 200
        assert c.get(f'/api/v1/predictions/{p_id}', headers=h_viewer).status_code == 200
        assert c.get('/api/v1/maintenance-priorities', headers=h_viewer).status_code == 200

        # Login as tenant B: tenant B cannot see machine predictions (404)
        h_b = login(c, setup, email='admin-b@example.com')
        assert c.get(f'/api/v1/machines/{m_id}/predictions', headers=h_b).status_code == 404
        assert c.post(f'/api/v1/machines/{m_id}/predictions', headers=h_b).status_code == 404
        assert c.get(f'/api/v1/predictions/{p_id}', headers=h_b).status_code == 404


def test_latest_prediction_and_outdated_tracking(setup):
    """Verifies:
    1. Historical request does not overwrite newer latest result.
    2. Advancing observations marks prediction outdated.
    3. Unavailable latest attempt does not appear healthy.
    """
    source, rows = load_selection(ROOT / 'data/raw', 'FD001', 'test', 1)
    with pred_client(setup) as c:
        h = login(c, setup)
        machine = registered_machine(c, setup, h)
        m_id = machine['id']
        path = machine['detail_api_path']

        # Ingest 30 observations
        ingest_observations(c, path, h, rows[:30], source, key='ingest-30')

        # Predict at cutoff 30 -> available
        pred30 = c.post(f'/api/v1/machines/{m_id}/predictions', headers=h, json={'cutoff_cycle': 30}).json()['prediction']
        assert pred30['status'] == 'available'

        # GET latest -> returns cutoff 30, current: True, outdated: False
        latest = c.get(f'/api/v1/machines/{m_id}/predictions/latest', headers=h).json()['prediction']
        assert latest['requested_cutoff_cycle'] == 30
        assert latest['is_current'] is True
        assert latest['is_outdated'] is False

        # Ingest observation 31 -> now DB has 31 cycles, but latest prediction is still at 30
        ingest_observations(c, path, h, [rows[30]], source, key='ingest-31')

        # GET latest -> now marked outdated!
        latest_after_ingest = c.get(f'/api/v1/machines/{m_id}/predictions/latest', headers=h).json()['prediction']
        assert latest_after_ingest['requested_cutoff_cycle'] == 30
        assert latest_after_ingest['is_current'] is False
        assert latest_after_ingest['is_outdated'] is True
        assert latest_after_ingest['latest_observation_cycle'] == 31

        # Now make an unavailable request at cutoff 20 (historical request)
        c.post(f'/api/v1/machines/{m_id}/predictions', headers=h, json={'cutoff_cycle': 20})

        # Latest prediction must STILL be cutoff 30 (greatest relevant cutoff, not newest execution!)
        latest_after_hist = c.get(f'/api/v1/machines/{m_id}/predictions/latest', headers=h).json()['prediction']
        assert latest_after_hist['requested_cutoff_cycle'] == 30

        # Now make a request at cutoff 35 (which has gaps/missing observations in DB -> unavailable)
        pred35 = c.post(f'/api/v1/machines/{m_id}/predictions', headers=h, json={'cutoff_cycle': 35}).json()['prediction']
        assert pred35['status'] == 'unavailable'

        # Now greatest cutoff is 35! It must NOT hide cutoff 35 by showing older cutoff 30
        latest_35 = c.get(f'/api/v1/machines/{m_id}/predictions/latest', headers=h).json()['prediction']
        assert latest_35['requested_cutoff_cycle'] == 35
        assert latest_35['status'] == 'unavailable'


def test_maintenance_priority_ranking_and_pagination(setup):
    """Verifies deterministic ranking in GET /api/v1/maintenance-priorities."""
    source, rows = load_selection(ROOT / 'data/raw', 'FD001', 'test', 1)
    with pred_client(setup) as c:
        h = login(c, setup)

        # Machine 1: available, RUL ~ 136.2 (low)
        m1 = registered_machine(c, setup, h, subset='FD001', engine_id=1)
        ingest_observations(c, m1['detail_api_path'], h, rows, source, key='m1-ingest')
        c.post(f"/api/v1/machines/{m1['id']}/predictions", headers=h)

        # Machine 2: registered physical machine (no prediction yet -> no_predictions / unknown)
        base = f"/api/v1/organizations/{setup['a']}"
        m2 = c.post(base + '/machines', headers=h, json=machine_payload('PHYS-MACHINE', 'physical_device')).json()['machine']

        # GET /api/v1/maintenance-priorities
        res = c.get('/api/v1/maintenance-priorities', headers=h)
        assert res.status_code == 200
        pdata = res.json()
        assert pdata['summary']['low'] == 1
        assert pdata['summary']['unknown'] == 1

        # Check items ranking: available low comes before no_predictions
        assert pdata['items'][0]['machine_id'] == m1['id']
        assert pdata['items'][0]['status'] == 'available'
        assert pdata['items'][0]['priority_band'] == 'low'

        assert pdata['items'][1]['machine_id'] == m2['id']
        assert pdata['items'][1]['status'] == 'no_predictions'
        assert pdata['items'][1]['priority_band'] == 'unknown'

        # Test pagination
        p_limit1 = c.get('/api/v1/maintenance-priorities?limit=1&offset=0', headers=h).json()
        assert len(p_limit1['items']) == 1
        assert p_limit1['total'] == 2


def test_audit_event_written_for_prediction(setup):
    source, rows = load_selection(ROOT / 'data/raw', 'FD001', 'test', 1)
    with pred_client(setup) as c:
        h = login(c, setup)
        machine = registered_machine(c, setup, h)
        m_id = machine['id']
        ingest_observations(c, machine['detail_api_path'], h, rows, source)

        res = c.post(f'/api/v1/machines/{m_id}/predictions', headers=h)
        pred_id = res.json()['prediction']['id']

        with setup['database'].transaction() as s:
            audit = s.execute(
                text("SELECT * FROM auth_audit_events WHERE target_type='prediction' AND target_id=:id"),
                dict(id=pred_id)
            ).mappings().one_or_none()
            assert audit is not None
            assert audit['action'] == 'prediction_completed'
            assert audit['tenant_id'] == setup['a']
