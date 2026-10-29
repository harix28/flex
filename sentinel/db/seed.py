"""Explicit sample-only seed; no passwords or login bypass."""
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5
from sqlalchemy import MetaData, Table
from sqlalchemy.dialects.postgresql import insert


def demo_id(label):
    return uuid5(NAMESPACE_URL, 'meridian-sentinel:phase2:sample:' + label)


def seed_demo(database):
    with database.transaction() as session:
        metadata = MetaData()

        def add(table, label, **values):
            t = Table(table, metadata, autoload_with=session.connection())
            session.execute(insert(t).values(id=demo_id(label), **values).on_conflict_do_nothing(index_elements=['id']))

        tenant = demo_id('tenant')
        add('tenants', 'tenant', name='SAMPLE — Meridian replay organization')
        add('users', 'user', oidc_issuer='https://sample.invalid', oidc_subject='sample-viewer', display_name='SAMPLE — inactive identity')
        add('memberships', 'membership', tenant_id=tenant, user_id=demo_id('user'), roles=['viewer'], active=False)
        add('machines', 'machine', tenant_id=tenant, asset_code='SAMPLE-FD001-1', name='SAMPLE — replay engine', machine_type='NASA-FD001', location='SAMPLE — simulated')
        add('sensors', 'sensor', tenant_id=tenant, sensor_code='SAMPLE-S1', kind='replay-channel', canonical_unit='dataset-native')
        add('installations', 'installation', tenant_id=tenant, sensor_id=demo_id('sensor'), machine_id=demo_id('machine'), gateway_channel='SAMPLE-replay-s1', valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc))
