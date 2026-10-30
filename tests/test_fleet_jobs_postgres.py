from copy import copy
import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from sentinel.inference import Predictor
from sentinel.ingestion.importer import load_selection
from sentinel.config import ROOT
from sentinel.jobs.fleet import enqueue_fleet, fleet_handler
from sentinel.jobs.queue import enqueue, run_once
from tests.test_postgres import db
from tests.test_auth_postgres import setup, login
from tests.test_predictions_postgres import pred_client, registered_machine, ingest_observations, DEFAULT_SETTINGS
from tests.test_jobs_postgres import state

pytestmark = pytest.mark.postgres


@pytest.fixture
def predictor():
    return Predictor(DEFAULT_SETTINGS.model_dir, DEFAULT_SETTINGS.bundle_sha256)


def submit(setup, predictor, key='fleet-1', actor=None):
    with setup['database'].transaction() as s:
        return enqueue_fleet(s, setup['a'], actor or setup['users']['admin'], key, predictor)


def test_frozen_fleet_real_predictions_dedup_and_unknown(setup, predictor):
    database = setup['database']
    source, rows = load_selection(ROOT/'data/raw', 'FD001', 'test', 1)
    with pred_client(setup) as c:
        h = login(c, setup)
        machine = registered_machine(c, setup, h)
        unknown = registered_machine(c, setup, h, engine_id=2)
        registered_machine(c, setup, h, engine_id=3, lifecycle_status='inactive')
        ingest_observations(c, machine['detail_api_path'], h, rows, source)
        job = submit(setup, predictor)
        ingest_observations(c, machine['detail_api_path'], h, [dict(rows[-1], cycle=32)], source, key='later')
        assert submit(setup, predictor) == job
        assert run_once(database)  # real configured model, default dispatcher
        result = state(database, job)
        assert result['status'] == 'delivered'
        assert result['result']['total'] == 2
        assert result['result']['available'] == 1 and result['result']['unavailable'] == 1
        response = c.get(machine['detail_api_path']+'/predictions/latest').json()['prediction']
        assert response['requested_cutoff_cycle'] == 31
        assert response['actor_id'] == str(setup['users']['admin'])
        synchronous = c.post(machine['detail_api_path']+'/predictions', headers=h,
                             json={'cutoff_cycle': 31}).json()['prediction']
        assert synchronous['id'] == response['id']
        unavailable = c.get(unknown['detail_api_path']+'/predictions/latest').json()['prediction']
        assert unavailable['priority_band'] == 'unknown' and unavailable['rul_cycles'] is None
        assert not run_once(database)
    with database.transaction() as s:
        assert s.execute(text('SELECT count(*) FROM predictions')).scalar_one() == 2
        assert s.execute(text("SELECT count(*) FROM auth_audit_events WHERE request_id=:id"), {'id': job}).scalar_one() == 2


@pytest.mark.parametrize('role', ['viewer', 'admin_b'])
def test_fleet_rejects_unauthorized_actor(setup, predictor, role):
    with pytest.raises(ValueError, match='permission'):
        submit(setup, predictor, actor=setup['users'][role])
    with setup['database'].transaction() as s:
        assert s.execute(text('SELECT count(*) FROM outbox_events')).scalar_one() == 0


@pytest.mark.parametrize('disabled', ['membership', 'user'])
def test_permission_rechecked_after_enqueue(setup, predictor, disabled):
    job = submit(setup, predictor, actor=setup['users']['technician'])
    with setup['database'].transaction() as s:
        if disabled == 'membership':
            s.execute(text('UPDATE memberships SET active=false WHERE tenant_id=:t AND user_id=:u'),
                      dict(t=setup['a'], u=setup['users']['technician']))
        else:
            s.execute(text('UPDATE users SET active=false WHERE id=:u'), dict(u=setup['users']['technician']))
    assert run_once(setup['database'])
    assert state(setup['database'], job)['status'] == 'pending'
    assert state(setup['database'], job)['result'] is None


def test_backfill_invalidates_snapshot_and_model_changes_rejected(setup, predictor):
    database = setup['database']
    source, rows = load_selection(ROOT/'data/raw', 'FD001', 'test', 1)
    with pred_client(setup) as c:
        h = login(c, setup)
        machine = registered_machine(c, setup, h)
        ingest_observations(c, machine['detail_api_path'], h, [r for r in rows if r['cycle'] != 10], source)
        job = submit(setup, predictor)
        wrong = copy(predictor)
        wrong.bundle_sha256 = '0'*64
        assert run_once(database, lambda s, event: fleet_handler(s, event, wrong))
        assert state(database, job)['status'] == 'pending'
        ingest_observations(c, machine['detail_api_path'], h, [r for r in rows if r['cycle']==10], source, key='backfill')
        with database.transaction() as s:
            s.execute(text('UPDATE outbox_events SET next_attempt_at=clock_timestamp() WHERE id=:id'), {'id': job})
        assert run_once(database)
        assert state(database, job)['status'] == 'pending'
        with database.transaction() as s:
            assert s.execute(text('SELECT count(*) FROM predictions')).scalar_one() == 0


def test_batch_failure_rolls_back_predictions_and_successful_retry(setup, predictor, monkeypatch):
    from sentinel.jobs import fleet
    database = setup['database']
    with pred_client(setup) as c:
        h = login(c, setup)
        registered_machine(c, setup, h)
        registered_machine(c, setup, h, engine_id=2)
    job = submit(setup, predictor)
    original = fleet.compute_and_persist
    calls = []
    def fail_second(*args, **kwargs):
        calls.append(True)
        if len(calls) == 2:
            raise RuntimeError('simulated transient failure')
        return original(*args, **kwargs)
    monkeypatch.setattr(fleet, 'compute_and_persist', fail_second)
    assert run_once(database)
    assert state(database, job)['status'] == 'pending'
    with database.transaction() as s:
        assert s.execute(text('SELECT count(*) FROM predictions')).scalar_one() == 0
        assert s.execute(text('SELECT count(*) FROM auth_audit_events WHERE request_id=:id'), {'id': job}).scalar_one() == 0
        s.execute(text('UPDATE outbox_events SET next_attempt_at=clock_timestamp() WHERE id=:id'), {'id': job})
    monkeypatch.setattr(fleet, 'compute_and_persist', original)
    assert run_once(database)
    assert state(database, job)['status'] == 'delivered'
    assert state(database, job)['result']['total'] == 2


def test_conflicting_payload_tenant_selection_and_downgrade_guard(setup, predictor):
    database = setup['database']
    with pred_client(setup) as c:
        h = login(c, setup, 'admin-b@example.com')
        # Register a machine in B, using helper's organization selection.
        registered_machine(c, dict(setup, a=setup['b']), h)
    job = submit(setup, predictor)
    row = state(database, job)
    assert row['payload']['machines'] == []
    modified = dict(row['payload'], policy_version='different')
    with database.transaction() as s:
        with pytest.raises(ValueError, match='different payload'):
            enqueue(s, setup['a'], 'fleet-1', modified, event_type='fleet.score')
    with pytest.raises(DBAPIError):
        command.downgrade(setup['config'], '0008_outbox')
    assert database.ready()


def test_oversized_fleet_rejected_without_partial_enqueue(setup, predictor):
    with setup['database'].transaction() as s:
        s.execute(text("""INSERT INTO machines(tenant_id,asset_code,name,machine_type,location,lifecycle_status)
            SELECT :t,'asset-'||n,'Test','test','test','active' FROM generate_series(1,101) n"""), {'t': setup['a']})
    with pytest.raises(ValueError, match='100-machine'):
        submit(setup, predictor)
    with setup['database'].transaction() as s:
        assert s.execute(text('SELECT count(*) FROM outbox_events')).scalar_one() == 0


def test_cross_tenant_payload_and_inactive_machine_rejected_at_execution(setup, predictor):
    with pred_client(setup) as c:
        h = login(c, setup)
        machine = registered_machine(c, setup, h)
    job = submit(setup, predictor)
    database = setup['database']
    with database.transaction() as s:
        s.execute(text("UPDATE machines SET lifecycle_status='inactive' WHERE id=:id"), {'id': machine['id']})
    assert run_once(database)
    assert state(database, job)['status'] == 'pending'
    payload = state(database, job)['payload']
    payload['actor_id'] = str(setup['users']['admin_b'])
    with database.transaction() as s:
        s.execute(text("UPDATE outbox_events SET next_attempt_at=clock_timestamp()+interval '1 hour' WHERE id=:id"), {'id': job})
        other = enqueue(s, setup['b'], 'foreign-machine', payload, event_type='fleet.score')
    assert run_once(database)
    assert state(database, other)['status'] == 'pending'
    with database.transaction() as s:
        assert s.execute(text('SELECT count(*) FROM predictions')).scalar_one() == 0


def test_cli_status_is_tenant_scoped(setup, predictor, monkeypatch, capsys):
    import json
    import sys
    from sentinel.jobs.__main__ import main
    job = submit(setup, predictor)
    monkeypatch.setenv('DATABASE_URL', setup['database'].engine.url.render_as_string(hide_password=False))
    monkeypatch.setattr(sys, 'argv', ['jobs', 'status', '--tenant', str(setup['a']), '--job', str(job)])
    main()
    output = json.loads(capsys.readouterr().out)
    assert output['status'] == 'pending' and output['id'] == str(job)
    assert 'payload' not in output
    monkeypatch.setattr(sys, 'argv', ['jobs', 'status', '--tenant', str(setup['b']), '--job', str(job)])
    with pytest.raises(SystemExit, match='not found'):
        main()
