"""PostgreSQL integration tests for maintenance work orders, approval workflow, assignment, notes, and evidence tracking."""
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
from tests.test_predictions_postgres import pred_client, registered_machine, ingest_observations
from sentinel.api import create_app
from sentinel.ingestion.importer import load_selection
from sentinel.config import ROOT, load_settings

pytestmark = pytest.mark.postgres

DEFAULT_SETTINGS = load_settings()


def test_manual_draft_creation_and_fields(setup):
    """Verifies creating a manual draft work order without model predictions."""
    with pred_client(setup) as c:
        h_admin = login(c, setup, 'admin-a@example.com')
        mach = registered_machine(c, setup, h_admin)

        payload = {
            'machine_id': mach['id'],
            'title': 'Inspect fuel pump vibration',
            'description': 'Technician noted unusual acoustic hum during shift walk-through.',
            'priority': 'high',
        }
        res = c.post('/api/v1/work-orders', headers=h_admin, json=payload)
        assert res.status_code == 200, res.text
        wo = res.json()['work_order']

        assert wo['work_order_number'] == 'WO-00001'
        assert wo['status'] == 'draft'
        assert wo['priority'] == 'high'
        assert wo['origin'] == 'manual'
        assert wo['version'] == 1
        assert wo['evidence']['origin'] == 'manual'
        assert wo['evidence']['prediction_id'] is None
        assert wo['evidence']['rul_cycles'] is None
        assert wo['is_evidence_outdated'] is False


def test_prediction_linked_draft_creation_and_evidence_immutability(setup):
    """Verifies creating a draft from an existing prediction and preserving immutable snapshot evidence."""
    source, rows = load_selection(ROOT / 'data/raw', 'FD001', 'test', 1)
    with pred_client(setup) as c:
        h_admin = login(c, setup, 'admin-a@example.com')
        mach = registered_machine(c, setup, h_admin)
        path = mach['detail_api_path']

        # Ingest 31 observations and generate a prediction
        ingest_observations(c, path, h_admin, rows, source)
        pred_res = c.post(f"/api/v1/machines/{mach['id']}/predictions", headers=h_admin)
        assert pred_res.status_code == 200, pred_res.text
        pred = pred_res.json()['prediction']

        # Create draft from prediction
        draft_res = c.post(f"/api/v1/predictions/{pred['id']}/work-order-draft", headers=h_admin)
        assert draft_res.status_code == 200, draft_res.text
        wo = draft_res.json()['work_order']

        assert wo['origin'] == 'prediction'
        assert wo['status'] == 'draft'
        assert wo['priority'] == pred['priority_band']
        assert wo['evidence']['prediction_id'] == pred['id']
        assert abs(wo['evidence']['rul_cycles'] - pred['rul_cycles']) < 1e-6
        assert wo['evidence']['model_version'] == 'fd001-v1'
        assert wo['evidence']['cutoff_cycle'] == 31
        assert wo['is_evidence_outdated'] is False

        # Attempting to directly alter evidence via database trigger fails
        database = setup['database']
        with pytest.raises(Exception) as exc:
            with database.transaction() as s:
                s.execute(text("UPDATE work_orders SET rul_cycles = 999.0 WHERE id = :id"), dict(id=wo['id']))
        assert "immutable" in str(exc.value).lower()


def test_active_prediction_work_order_deduplication(setup):
    """Verifies that multiple active prediction drafts for the same machine are prevented and return existing work order."""
    source, rows = load_selection(ROOT / 'data/raw', 'FD001', 'test', 1)
    with pred_client(setup) as c:
        h_admin = login(c, setup, 'admin-a@example.com')
        mach = registered_machine(c, setup, h_admin)
        path = mach['detail_api_path']

        ingest_observations(c, path, h_admin, rows, source)
        pred = c.post(f"/api/v1/machines/{mach['id']}/predictions", headers=h_admin).json()['prediction']

        # 1. Create first work order draft
        res1 = c.post(f"/api/v1/predictions/{pred['id']}/work-order-draft", headers=h_admin)
        assert res1.status_code == 200, res1.text
        wo1 = res1.json()['work_order']
        assert wo1['already_active'] is False

        # 2. Subsequent call returns existing active work order with already_active: true
        res2 = c.post(f"/api/v1/predictions/{pred['id']}/work-order-draft", headers=h_admin)
        assert res2.status_code == 200, res2.text
        wo2 = res2.json()['work_order']
        assert wo2['id'] == wo1['id']
        assert wo2['already_active'] is True


def test_idempotency_key_replay_and_conflict(setup):
    """Verifies scoped Idempotency-Key returns original result on match and 409 on modified payload."""
    with pred_client(setup) as c:
        h_admin = login(c, setup, 'admin-a@example.com')
        mach = registered_machine(c, setup, h_admin)

        key = "idemp-test-unique-key-1"
        payload_1 = {
            'machine_id': mach['id'],
            'title': 'Check hydraulic seal',
            'description': 'Initial inspection request',
            'priority': 'medium',
        }
        res1 = c.post('/api/v1/work-orders', headers={**h_admin, 'Idempotency-Key': key}, json=payload_1)
        assert res1.status_code == 200, res1.text
        wo1 = res1.json()['work_order']
        assert wo1['idempotency_replayed'] is False

        # Same key, identical payload -> returns original
        res2 = c.post('/api/v1/work-orders', headers={**h_admin, 'Idempotency-Key': key}, json=payload_1)
        assert res2.status_code == 200, res2.text
        wo2 = res2.json()['work_order']
        assert wo2['id'] == wo1['id']
        assert wo2['idempotency_replayed'] is True

        # Same key, different payload -> 409 conflict
        payload_conflict = {**payload_1, 'priority': 'urgent'}
        res3 = c.post('/api/v1/work-orders', headers={**h_admin, 'Idempotency-Key': key}, json=payload_conflict)
        assert res3.status_code == 409


def test_full_state_machine_workflow_and_assignment(setup):
    """Verifies complete workflow: draft -> approved -> in_progress -> blocked -> in_progress -> completed."""
    with pred_client(setup) as c_admin, pred_client(setup) as c_mgr, pred_client(setup) as c_tech:
        h_admin = login(c_admin, setup, 'admin-a@example.com')
        h_mgr = login(c_mgr, setup, 'plant_manager@example.com')
        h_tech = login(c_tech, setup, 'technician@example.com')
        mach = registered_machine(c_admin, setup, h_admin)
        tech_user_id = setup['users']['technician']

        # 1. Technician creates draft
        draft_payload = {
            'machine_id': mach['id'],
            'title': 'Borescope inspection of HP compressor',
            'description': 'Inspect stage 1-3 blades for abnormal wear patterns.',
            'priority': 'high',
        }
        res = c_tech.post('/api/v1/work-orders', headers=h_tech, json=draft_payload)
        assert res.status_code == 200, res.text
        wo = res.json()['work_order']
        wo_id = wo['id']
        assert wo['status'] == 'draft'
        assert wo['version'] == 1

        # 2. Technician CANNOT approve work order (requires plant_manager or admin)
        tech_appr = c_tech.post(f"/api/v1/work-orders/{wo_id}/transitions", headers=h_tech, json={'action': 'approve', 'version': 1})
        assert tech_appr.status_code == 403

        # 3. Plant Manager approves work order
        appr_res = c_mgr.post(f"/api/v1/work-orders/{wo_id}/transitions", headers=h_mgr, json={'action': 'approve', 'version': 1})
        assert appr_res.status_code == 200, appr_res.text
        wo = appr_res.json()['work_order']
        assert wo['status'] == 'approved'
        assert wo['version'] == 2

        # 4. Starting work fails without an assigned technician
        start_fail = c_mgr.post(f"/api/v1/work-orders/{wo_id}/transitions", headers=h_mgr, json={'action': 'start', 'version': 2})
        assert start_fail.status_code == 400

        # 5. Manager assigns eligible technician
        assign_res = c_mgr.post(f"/api/v1/work-orders/{wo_id}/assignment", headers=h_mgr, json={'technician_id': str(tech_user_id), 'version': 2})
        assert assign_res.status_code == 200, assign_res.text
        wo = assign_res.json()['work_order']
        assert wo['assigned_technician_id'] == str(tech_user_id)
        assert wo['version'] == 3

        # 6. Assigned technician starts work (approved -> in_progress)
        start_res = c_tech.post(f"/api/v1/work-orders/{wo_id}/transitions", headers=h_tech, json={'action': 'start', 'version': 3})
        assert start_res.status_code == 200, start_res.text
        wo = start_res.json()['work_order']
        assert wo['status'] == 'in_progress'
        assert wo['version'] == 4

        # 7. Technician blocks work (requires reason)
        block_fail = c_tech.post(f"/api/v1/work-orders/{wo_id}/transitions", headers=h_tech, json={'action': 'block', 'version': 4})
        assert block_fail.status_code == 400

        block_res = c_tech.post(f"/api/v1/work-orders/{wo_id}/transitions", headers=h_tech, json={
            'action': 'block', 'version': 4, 'reason': 'Waiting for specialized borescope probe calibration kit'
        })
        assert block_res.status_code == 200, block_res.text
        wo = block_res.json()['work_order']
        assert wo['status'] == 'blocked'
        assert wo['block_reason'] == 'Waiting for specialized borescope probe calibration kit'
        assert wo['version'] == 5

        # 8. Technician resumes work (blocked -> in_progress)
        resume_res = c_tech.post(f"/api/v1/work-orders/{wo_id}/transitions", headers=h_tech, json={'action': 'resume', 'version': 5})
        assert resume_res.status_code == 200, resume_res.text
        wo = resume_res.json()['work_order']
        assert wo['status'] == 'in_progress'
        assert wo['block_reason'] is None
        assert wo['version'] == 6

        # 9. Technician adds operational note
        note_res = c_tech.post(f"/api/v1/work-orders/{wo_id}/notes", headers=h_tech, json={'version': 6, 'note_text': 'Completed visual inspection of stage 1 and 2 blades; no microcracks observed.'})
        assert note_res.status_code == 200, note_res.text

        assert note_res.json()['work_order_version'] == 7

        # 10. Technician completes work (requires completion_summary)
        comp_fail = c_tech.post(f"/api/v1/work-orders/{wo_id}/transitions", headers=h_tech, json={'action': 'complete', 'version': 7})
        assert comp_fail.status_code == 400

        comp_res = c_tech.post(f"/api/v1/work-orders/{wo_id}/transitions", headers=h_tech, json={
            'action': 'complete', 'version': 7, 'completion_summary': 'Borescope inspection completed according to AMM 72-00. All blade tolerances within operating limits.'
        })
        assert comp_res.status_code == 200, comp_res.text
        wo = comp_res.json()['work_order']
        assert wo['status'] == 'completed'
        assert wo['completed_at'] is not None
        assert wo['version'] == 8

        # 11. Terminal state protection: completed work order cannot transition further
        term_res = c_mgr.post(f"/api/v1/work-orders/{wo_id}/transitions", headers=h_mgr, json={'action': 'cancel', 'version': 8, 'reason': 'reopen attempt'})
        assert term_res.status_code == 400

        # 12. Retrieve full history
        hist_res = c_admin.get(f"/api/v1/work-orders/{wo_id}/history", headers=h_admin)
        assert hist_res.status_code == 200, hist_res.text
        hist = hist_res.json()
        assert len(hist['transitions']) >= 5
        assert len(hist['assignments']) >= 1
        assert len(hist['notes']) >= 1


def test_cancellation_workflow(setup):
    """Verifies cancellation requires manager/admin role and non-empty cancellation reason."""
    with pred_client(setup) as c_admin, pred_client(setup) as c_mgr, pred_client(setup) as c_tech:
        h_admin = login(c_admin, setup, 'admin-a@example.com')
        h_mgr = login(c_mgr, setup, 'plant_manager@example.com')
        h_tech = login(c_tech, setup, 'technician@example.com')
        mach = registered_machine(c_admin, setup, h_admin)

        res = c_admin.post('/api/v1/work-orders', headers=h_admin, json={
            'machine_id': mach['id'],
            'title': 'Check exhaust gas temperature',
            'description': 'Routine review',
            'priority': 'low',
        })
        assert res.status_code == 200, res.text
        wo = res.json()['work_order']
        wo_id = wo['id']

        # Technician cannot cancel
        tech_cancel = c_tech.post(f"/api/v1/work-orders/{wo_id}/transitions", headers=h_tech, json={
            'action': 'cancel', 'version': 1, 'reason': 'test reason'
        })
        assert tech_cancel.status_code == 403

        # Manager cancel without reason fails
        cancel_no_reason = c_mgr.post(f"/api/v1/work-orders/{wo_id}/transitions", headers=h_mgr, json={
            'action': 'cancel', 'version': 1
        })
        assert cancel_no_reason.status_code == 400

        # Manager cancel with valid reason succeeds
        cancel_ok = c_mgr.post(f"/api/v1/work-orders/{wo_id}/transitions", headers=h_mgr, json={
            'action': 'cancel', 'version': 1, 'reason': 'Engine decommissioned from test stand'
        })
        assert cancel_ok.status_code == 200, cancel_ok.text
        wo_cancelled = cancel_ok.json()['work_order']
        assert wo_cancelled['status'] == 'cancelled'
        assert wo_cancelled['cancellation_reason'] == 'Engine decommissioned from test stand'


def test_optimistic_concurrency_version_conflict(setup):
    """Verifies that mutations with stale version numbers are rejected with 409 conflict."""
    with pred_client(setup) as c:
        h_admin = login(c, setup, 'admin-a@example.com')
        mach = registered_machine(c, setup, h_admin)

        res = c.post('/api/v1/work-orders', headers=h_admin, json={
            'machine_id': mach['id'],
            'title': 'Test concurrency work order',
            'description': 'Initial desc',
            'priority': 'medium',
        })
        assert res.status_code == 200, res.text
        wo = res.json()['work_order']
        wo_id = wo['id']
        assert wo['version'] == 1

        # First update succeeds with version=1 -> advances to version=2
        res1 = c.patch(f"/api/v1/work-orders/{wo_id}", headers=h_admin, json={
            'version': 1, 'title': 'Updated title first'
        })
        assert res1.status_code == 200, res1.text
        assert res1.json()['work_order']['version'] == 2

        # Second update using stale version=1 fails with 409
        res2 = c.patch(f"/api/v1/work-orders/{wo_id}", headers=h_admin, json={
            'version': 1, 'title': 'Stale update attempt'
        })
        assert res2.status_code == 409


def test_assignee_eligibility_and_tenant_boundary(setup):
    """Verifies that non-technician roles, cross-tenant users, and disabled members are rejected as assignees."""
    with pred_client(setup) as c:
        h_admin = login(c, setup, 'admin-a@example.com')
        mach = registered_machine(c, setup, h_admin)

        res = c.post('/api/v1/work-orders', headers=h_admin, json={
            'machine_id': mach['id'],
            'title': 'Assignment eligibility test',
            'description': 'Testing assignee validation',
            'priority': 'low',
        })
        assert res.status_code == 200, res.text
        wo = res.json()['work_order']
        wo_id = wo['id']

        # 1. Assigning a viewer (no work_orders.execute permission) fails
        viewer_id = setup['users']['viewer']
        res_viewer = c.post(f"/api/v1/work-orders/{wo_id}/assignment", headers=h_admin, json={
            'technician_id': str(viewer_id), 'version': 1
        })
        assert res_viewer.status_code == 400

        # 2. Assigning cross-tenant user from Organization B fails
        admin_b_id = setup['users']['admin_b']
        res_cross = c.post(f"/api/v1/work-orders/{wo_id}/assignment", headers=h_admin, json={
            'technician_id': str(admin_b_id), 'version': 1
        })
        assert res_cross.status_code == 400

        # 3. Assigning valid technician succeeds
        tech_id = setup['users']['technician']
        res_tech = c.post(f"/api/v1/work-orders/{wo_id}/assignment", headers=h_admin, json={
            'technician_id': str(tech_id), 'version': 1
        })
        assert res_tech.status_code == 200, res_tech.text


def test_cross_tenant_isolation_reads_and_writes(setup):
    """Verifies that Organization B cannot read or modify Organization A work orders."""
    with pred_client(setup) as c_a, pred_client(setup) as c_b:
        h_admin_a = login(c_a, setup, 'admin-a@example.com')
        h_admin_b = login(c_b, setup, 'admin-b@example.com')
        mach_a = registered_machine(c_a, setup, h_admin_a)

        res = c_a.post('/api/v1/work-orders', headers=h_admin_a, json={
            'machine_id': mach_a['id'],
            'title': 'Tenant A proprietary work order',
            'description': 'Sensitive aircraft maintenance data',
            'priority': 'urgent',
        })
        assert res.status_code == 200, res.text
        wo_a = res.json()['work_order']
        wo_id = wo_a['id']

        # Org B read attempt returns 404
        assert c_b.get(f"/api/v1/work-orders/{wo_id}", headers=h_admin_b).status_code == 404
        assert c_b.get(f"/api/v1/work-orders/{wo_id}/history", headers=h_admin_b).status_code == 404

        # Org B mutation attempt returns 404
        assert c_b.patch(f"/api/v1/work-orders/{wo_id}", headers=h_admin_b, json={'version': 1, 'title': 'Hacked'}).status_code == 404
        assert c_b.post(f"/api/v1/work-orders/{wo_id}/notes", headers=h_admin_b, json={'version': 1, 'note_text': 'Inject note'}).status_code == 404
        assert c_b.post(f"/api/v1/work-orders/{wo_id}/transitions", headers=h_admin_b, json={'action': 'approve', 'version': 1}).status_code == 404


def test_outdated_prediction_flagging_on_work_orders(setup):
    """Verifies that work orders correctly flag when new observations arrive after draft creation."""
    source, rows = load_selection(ROOT / 'data/raw', 'FD001', 'test', 1)
    with pred_client(setup) as c:
        h_admin = login(c, setup, 'admin-a@example.com')
        mach = registered_machine(c, setup, h_admin)
        path = mach['detail_api_path']

        # Ingest first 30 cycles
        ingest_observations(c, path, h_admin, rows[:30], source, key='batch-1')
        pred = c.post(f"/api/v1/machines/{mach['id']}/predictions", headers=h_admin, json={'cutoff_cycle': 30}).json()['prediction']

        # Create draft at cutoff 30
        wo_res = c.post(f"/api/v1/predictions/{pred['id']}/work-order-draft", headers=h_admin)
        assert wo_res.status_code == 200, wo_res.text
        wo = wo_res.json()['work_order']
        assert wo['is_evidence_outdated'] is False

        # FD001 test engine1 has exactly31 rows: exercise the real final row.
        next_rows = [r for r in rows if r['cycle'] == 31]
        assert len(next_rows) == 1
        ingest_observations(c, path, h_admin, next_rows, source, key='batch-2')
        wo_updated = c.get(f"/api/v1/work-orders/{wo['id']}", headers=h_admin).json()['work_order']
        assert wo_updated['is_evidence_outdated'] is True
        assert wo_updated['evidence']['cutoff_cycle'] == 30
        assert wo_updated['latest_observation_cycle'] == 31
