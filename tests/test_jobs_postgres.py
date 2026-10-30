import pytest
from alembic import command
from sqlalchemy import text

from tests.test_postgres import db, tenant
from sentinel.jobs.queue import enqueue, claim, run_once

pytestmark = pytest.mark.postgres


def state(database, job):
    with database.transaction() as s:
        return dict(s.execute(text('SELECT * FROM outbox_events WHERE id=:id'), {'id': job}).mappings().one())


def test_atomic_enqueue_and_tenant_dedup(db):
    database, _ = db
    with database.transaction() as s:
        a, b = tenant(s), tenant(s)
        job = enqueue(s, a, 'source-1', {})
        assert enqueue(s, a, 'source-1', {}) == job
        assert enqueue(s, b, 'source-1', {}) != job
    with pytest.raises(RuntimeError):
        with database.transaction() as s:
            enqueue(s, a, 'rolled-back', {})
            raise RuntimeError()
    with database.transaction() as s:
        assert s.execute(text('SELECT count(*) FROM outbox_events')).scalar_one() == 2
        with pytest.raises(ValueError):
            enqueue(s, a, 'invalid', {'tenant_id': str(b)})


def test_claim_skips_locked_and_recovers_expired_lease(db):
    database, _ = db
    with database.transaction() as s:
        a = tenant(s)
        first = enqueue(s, a, 'first', {})
        second = enqueue(s, a, 'second', {})
    with database.transaction() as s:
        s.execute(text('SELECT id FROM outbox_events WHERE id=:id FOR UPDATE'), {'id': first})
        claimed = claim(database)
        assert claimed['id'] == second
    assert claim(database)['id'] == first
    assert claim(database) is None
    with database.transaction() as s:
        s.execute(text("UPDATE outbox_events SET lease_until=clock_timestamp()-interval '1 second' WHERE id=:id"), {'id': first})
    recovered = claim(database)
    assert recovered['id'] == first
    assert state(database, first)['attempts'] == 2


def test_handler_rollback_retry_dead_letter_and_error_redaction(db):
    database, _ = db
    with database.transaction() as s:
        a = tenant(s)
        job = enqueue(s, a, 'failure', {})
        s.execute(text('UPDATE outbox_events SET max_attempts=2 WHERE id=:id'), {'id': job})
    def fail(s, event):
        assert event['tenant_id'] == a
        s.execute(text("UPDATE tenants SET name='should rollback' WHERE id=:id"), {'id': a})
        raise RuntimeError('SECRET must never be stored')
    assert run_once(database, fail)
    row = state(database, job)
    assert row['status'] == 'pending' and row['error_code'] == 'handler_failed'
    assert claim(database) is None  # retry backoff enforced
    with database.transaction() as s:
        assert s.execute(text('SELECT name FROM tenants WHERE id=:id'), {'id': a}).scalar_one() != 'should rollback'
        s.execute(text("UPDATE outbox_events SET next_attempt_at=clock_timestamp() WHERE id=:id"), {'id': job})
    assert run_once(database, fail)
    assert state(database, job)['status'] == 'dead_letter'
    with database.transaction() as s:
        assert s.execute(text('SELECT count(*) FROM outbox_dead_letter')).scalar_one() == 1
    assert not run_once(database, fail)


def test_success_commits_effect_once_and_migration_roundtrip(db):
    database, config = db
    with database.transaction() as s:
        a = tenant(s)
        job = enqueue(s, a, 'success', {})
    calls = []
    def success(s, event):
        calls.append(event['id'])
        s.execute(text("UPDATE tenants SET name='processed' WHERE id=:id"), {'id': event['tenant_id']})
    assert run_once(database, success)
    assert not run_once(database, success)
    assert calls == [job]
    assert state(database, job)['status'] == 'delivered'
    with database.transaction() as s:
        assert s.execute(text('SELECT name FROM tenants WHERE id=:id'), {'id': a}).scalar_one() == 'processed'
    command.downgrade(config, '0007_mlops')
    command.upgrade(config, 'head')
    assert database.ready()


def test_crashes_eventually_exhaust_attempts(db):
    database, _ = db
    with database.transaction() as s:
        job = enqueue(s, tenant(s), 'crashed', {})
        s.execute(text('UPDATE outbox_events SET max_attempts=1 WHERE id=:id'), {'id': job})
    assert claim(database)['id'] == job
    with database.transaction() as s:
        s.execute(text("UPDATE outbox_events SET lease_until=clock_timestamp()-interval '1 second' WHERE id=:id"), {'id': job})
    assert claim(database) is None
    assert state(database, job)['status'] == 'dead_letter'


def test_real_drift_handler(db):
    database, _ = db
    with database.transaction() as s:
        a = tenant(s)
        job = enqueue(s, a, 'drift', {})
    assert run_once(database)
    assert state(database, job)['status'] == 'delivered'
    with database.transaction() as s:
        row = s.execute(text('SELECT tenant_id,status FROM ml_monitoring_runs')).mappings().one()
        assert row['tenant_id'] == a and row['status'] == 'insufficient_data'


def test_stale_worker_cannot_execute_after_reclaim(db, monkeypatch):
    from sentinel.jobs import queue
    database, _ = db
    with database.transaction() as s:
        job = enqueue(s, tenant(s), 'stale', {})
    old = claim(database)
    with database.transaction() as s:
        s.execute(text("UPDATE outbox_events SET lease_until=clock_timestamp()-interval '1 second' WHERE id=:id"), {'id': job})
    new = claim(database)
    assert old['lease_token'] != new['lease_token']
    monkeypatch.setattr(queue, 'claim', lambda database: old)
    def forbidden(s, event):
        pytest.fail('Stale worker executed handler')
    assert run_once(database, forbidden)
    assert state(database, job)['lease_token'] == new['lease_token']


def test_process_crash_rolls_back_effect_and_can_recover(db):
    database, _ = db
    with database.transaction() as s:
        a = tenant(s)
        job = enqueue(s, a, 'interrupt', {})
    def interrupt(s, event):
        s.execute(text("UPDATE tenants SET name='interrupted' WHERE id=:id"), {'id': a})
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        run_once(database, interrupt)
    with database.transaction() as s:
        assert s.execute(text('SELECT name FROM tenants WHERE id=:id'), {'id': a}).scalar_one() != 'interrupted'
        s.execute(text("UPDATE outbox_events SET lease_until=clock_timestamp()-interval '1 second' WHERE id=:id"), {'id': job})
    assert run_once(database, lambda s, event: None)
    assert state(database, job)['status'] == 'delivered'
