"""Real PostgreSQL only. Creates/drops exclusively generated disposable databases.
Set SENTINEL_TEST_ADMIN_URL explicitly to a PostgreSQL role with CREATEDB and
extension privileges. Never reads DATABASE_URL or the development .env.
"""
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sentinel.config import ROOT, validate_database_url
from sentinel.db import Database
from sentinel.db.repository import RegistryRepository
from sentinel.db.seed import seed_demo

pytestmark = pytest.mark.postgres

@pytest.fixture
def db():
    raw = os.environ.get('SENTINEL_TEST_ADMIN_URL')
    if not raw:
        pytest.skip('Real PostgreSQL unavailable: set SENTINEL_TEST_ADMIN_URL (CREATEDB); no SQLite fallback')
    url = validate_database_url(raw)
    name = 'meridian_test_' + uuid4().hex
    admin = create_engine(url.set(database='postgres'), isolation_level='AUTOCOMMIT', hide_parameters=True,
                          connect_args={'connect_timeout': 3})
    database = None
    created = False
    try:
        with admin.connect() as c:
            c.exec_driver_sql('CREATE DATABASE ' + name)
            created = True
        config = Config(str(ROOT / 'alembic.ini'))
        config.attributes['database_url'] = url.set(database=name).render_as_string(hide_password=False)
        command.upgrade(config, 'head')
        database = Database(config.attributes['database_url'])
        yield database, config
    finally:
        if database:
            database.close()
        if created:
            # name is generated here, never supplied by caller/configuration.
            with admin.connect() as c:
                c.exec_driver_sql('DROP DATABASE ' + name)
        admin.dispose()


def tenant(session):
    return session.execute(text("INSERT INTO tenants(name) VALUES ('TEST organization') RETURNING id")).scalar_one()


def assets(database):
    with database.transaction() as s:
        tid = tenant(s)
        r = RegistryRepository(s, tenant_id=tid)
        machine = r.add('machines', asset_code='A', name='Test machine', machine_type='test', location='test')
        sensor = r.add('sensors', sensor_code='S', kind='test', canonical_unit='test')
    return tid, machine, sensor


def install(r, machine, sensor, start, end=None, **extra):
    return r.add('installations', machine_id=machine, sensor_id=sensor, gateway_channel='test', valid_from=start, valid_to=end, **extra)


def test_schema_and_disposable_downgrade_upgrade(db):
    database, config = db
    expected = {
        'tenants', 'users', 'memberships', 'machines', 'sensors', 'installations',
        'alembic_version', 'auth_sessions', 'auth_audit_events', 'replay_streams',
        'replay_batches', 'replay_observations', 'predictions', 'work_order_counters',
        'work_orders', 'work_order_transitions', 'work_order_assignments', 'work_order_notes',
        'work_order_idempotency', 'models', 'model_deployments', 'ml_monitoring_runs'
    }
    assert set(inspect(database.engine).get_table_names()) == expected
    assert database.ready()
    assets(database)
    database.close()
    command.downgrade(config, 'base')
    assert set(inspect(database.engine).get_table_names()) == {'alembic_version'}
    assert not database.ready()
    command.upgrade(config, 'head')
    assert database.ready()
    assert set(inspect(database.engine).get_table_names()) == expected


def test_persistence_across_new_connections(db):
    database, config = db
    tid, machine, _ = assets(database)
    database.close()
    other = Database(config.attributes['database_url'])
    try:
        with other.transaction() as s:
            assert RegistryRepository(s, tenant_id=tid).get('machines', machine)['asset_code'] == 'A'
    finally:
        other.close()


def test_failed_transaction_rolls_back(db):
    database, _ = db
    with pytest.raises(IntegrityError):
        with database.transaction() as s:
            tid = tenant(s)
            r = RegistryRepository(s, tenant_id=tid)
            r.add('machines', asset_code='A', name='Test', machine_type='test', location='test')
            r.add('machines', asset_code='A', name='duplicate', machine_type='test', location='test')
    with database.transaction() as s:
        assert s.execute(text('SELECT count(*) FROM tenants')).scalar_one() == 0
        assert s.execute(text('SELECT count(*) FROM machines')).scalar_one() == 0


def test_tenant_scoped_reads_writes_and_uniqueness(db):
    database, _ = db
    first, machine, _ = assets(database)
    second, _, _ = assets(database)  # Same asset/sensor codes allowed in another tenant.
    with database.transaction() as s:
        r = RegistryRepository(s, tenant_id=second)
        assert r.get('machines', machine) is None
        assert not r.retire_machine(machine)
        assert all(row['tenant_id'] == second for row in r.list('machines'))
        with pytest.raises(ValueError):
            r.add('machines', tenant_id=first)
        assert RegistryRepository(s, tenant_id=first).get('machines', machine)['operating_status'] == 'stopped'
    with database.transaction() as s:
        assert RegistryRepository(s, tenant_id=first).retire_machine(machine)


@pytest.mark.parametrize('foreign', ['machine','sensor','verifier'])
def test_cross_tenant_associations_rejected_by_database(db, foreign):
    database, _ = db
    tid, machine, sensor = assets(database)
    other, other_machine, other_sensor = assets(database)
    extra = {}
    if foreign == 'machine': machine = other_machine
    if foreign == 'sensor': sensor = other_sensor
    if foreign == 'verifier':
        with database.transaction() as s:
            user = s.execute(text("INSERT INTO users(oidc_issuer,oidc_subject,display_name) VALUES ('test','test','test') RETURNING id")).scalar_one()
            RegistryRepository(s, tenant_id=other).add('memberships', user_id=user, roles=['admin'])
        extra = {'verified_by': user, 'verified_at': datetime.now(timezone.utc)}
    with pytest.raises(IntegrityError):
        with database.transaction() as s:
            install(RegistryRepository(s, tenant_id=tid), machine, sensor, datetime.now(timezone.utc), **extra)


@pytest.mark.parametrize('roles', [[], ['owner'], [None]])
def test_invalid_roles(db, roles):
    database, _ = db
    with pytest.raises(IntegrityError):
        with database.transaction() as s:
            tid = tenant(s)
            user = s.execute(text("INSERT INTO users(oidc_issuer,oidc_subject,display_name) VALUES ('test','test','test') RETURNING id")).scalar_one()
            RegistryRepository(s, tenant_id=tid).add('memberships', user_id=user, roles=roles)


def test_missing_foreign_key_and_required_values(db):
    database, _ = db
    tid, machine, sensor = assets(database)
    for values in ({'sensor_code':'S2','kind':'test'}, {'sensor_code':'S','kind':'test','canonical_unit':'test'}):
        with pytest.raises(IntegrityError):
            with database.transaction() as s:
                RegistryRepository(s, tenant_id=tid).add('sensors', **values)
    with pytest.raises(IntegrityError):
        with database.transaction() as s:
            install(RegistryRepository(s, tenant_id=tid), uuid4(), sensor, datetime.now(timezone.utc))


def test_installation_ranges_and_overlap(db):
    database, _ = db
    tid, machine, sensor = assets(database)
    start = datetime(2026,1,1,tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    with database.transaction() as s:
        install(RegistryRepository(s, tenant_id=tid), machine, sensor, start, end)
    for a,b in [(start,start), (end,start), (start,end), (start,None)]:
        with pytest.raises(IntegrityError):
            with database.transaction() as s:
                install(RegistryRepository(s, tenant_id=tid), machine, sensor, a, b)
    with database.transaction() as s:
        install(RegistryRepository(s, tenant_id=tid), machine, sensor, end)  # Adjacent [start,end) allowed.
    with pytest.raises(IntegrityError):
        with database.transaction() as s:
            install(RegistryRepository(s, tenant_id=tid), machine, sensor, end + timedelta(days=1))


def test_seed_is_idempotent(db):
    database, _ = db
    seed_demo(database)
    seed_demo(database)
    with database.transaction() as s:
        for table in ('tenants','users','memberships','machines','sensors','installations'):
            assert s.execute(text('SELECT count(*) FROM ' + table)).scalar_one() == 1
        assert s.execute(text('SELECT active FROM memberships')).scalar_one() is False


def test_overlapping_concurrent_transactions(db):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    database, _ = db
    tid, machine, sensor = assets(database)
    start = datetime(2026,1,1,tzinfo=timezone.utc)
    entered = Event()
    def competing_write():
        with pytest.raises(IntegrityError):
            with database.transaction() as s:
                r = RegistryRepository(s, tenant_id=tid)
                # Reflect before signalling; the insert must contend with the first transaction.
                r._table('installations')
                entered.set()
                install(r, machine, sensor, start)
    with ThreadPoolExecutor(max_workers=1) as executor:
        with database.transaction() as s:
            install(RegistryRepository(s, tenant_id=tid), machine, sensor, start)
            future = executor.submit(competing_write)
            assert entered.wait(timeout=2)
        future.result(timeout=10)


def test_external_identity_and_membership_uniqueness(db):
    database, _ = db
    with database.transaction() as s:
        tid = tenant(s)
        user = s.execute(text("INSERT INTO users(oidc_issuer,oidc_subject,display_name) VALUES ('issuer','subject','Test') RETURNING id")).scalar_one()
        RegistryRepository(s, tenant_id=tid).add('memberships', user_id=user, roles=['viewer','technician'])
    with pytest.raises(IntegrityError):
        with database.transaction() as s:
            s.execute(text("INSERT INTO users(oidc_issuer,oidc_subject,display_name) VALUES ('issuer','subject','Duplicate')"))
    with pytest.raises(IntegrityError):
        with database.transaction() as s:
            RegistryRepository(s, tenant_id=tid).add('memberships', user_id=user, roles=['admin'])
