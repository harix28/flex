"""Prepare cleanly labelled demonstration data for Phase 8 web portal walkthrough."""
import os
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text
from sentinel.config import ROOT, read_env
from sentinel.db import Database
from sentinel.auth.service import bootstrap, create_user
from sentinel.registry.replay import register_replay
from sentinel.ingestion.importer import load_selection
from sentinel.ingestion.schemas import Batch
from sentinel.ingestion.service import ingest


def prepare_demo():
    env_file = ROOT / '.runtime/postgres.env'
    if not env_file.exists():
        raise SystemExit('Missing .runtime/postgres.env')
    
    env_vars = read_env(env_file)
    db_url = env_vars['DATABASE_URL']
    db = Database(db_url)

    data_dir = ROOT / 'data/raw'
    tenant_slug = 'meridian-a'
    admin_email = 'admin@meridian.example.com'
    tech_email = 'tech@meridian.example.com'
    password = 'Password12345!'

    tenant_id = None
    admin_id = None
    tech_id = None

    # 1. Setup tenant & admin
    with db.transaction() as s:
        existing_tenant = s.execute(text('SELECT id FROM tenants WHERE slug=:slug'), dict(slug=tenant_slug)).scalar_one_or_none()
        existing_admin = s.execute(text('SELECT id FROM users WHERE email=:email'), dict(email=admin_email)).scalar_one_or_none()

    if not existing_tenant or not existing_admin:
        print(f'Bootstrapping organization {tenant_slug} with admin {admin_email}...')
        tenant_id, admin_id = bootstrap(db, tenant_slug, 'Meridian Turbofan Maintenance', admin_email, password, 'Chief Maintenance Inspector')
    else:
        tenant_id = existing_tenant
        admin_id = existing_admin
        print(f'Organization {tenant_slug} ({tenant_id}) and admin ({admin_id}) already exist.')

    # 2. Setup technician
    with db.transaction() as s:
        existing_tech = s.execute(text('SELECT id FROM users WHERE email=:email'), dict(email=tech_email)).scalar_one_or_none()
        if not existing_tech:
            print(f'Creating technician user {tech_email}...')
            tech_id = create_user(s, tech_email, password, 'Lead Turbofan Technician')
            s.execute(text("INSERT INTO memberships(tenant_id,user_id,roles) VALUES (:t,:u,ARRAY['technician'])"),
                      dict(t=tenant_id, u=tech_id))
        else:
            tech_id = existing_tech
            # ensure membership
            mem = s.execute(text('SELECT 1 FROM memberships WHERE tenant_id=:t AND user_id=:u'),
                            dict(t=tenant_id, u=tech_id)).scalar_one_or_none()
            if not mem:
                s.execute(text("INSERT INTO memberships(tenant_id,user_id,roles) VALUES (:t,:u,ARRAY['technician'])"),
                          dict(t=tenant_id, u=tech_id))
            print(f'Technician user ({tech_id}) ready.')

    # 3. Register engine 1 replay
    print('Registering NASA C-MAPSS FD001 Engine 1 replay...')
    reg_res = register_replay(db, tenant_id, admin_id, 'FD001', [1], data_dir)
    print('Registration result:', reg_res)

    # Find machine_id
    with db.transaction() as s:
        machine = s.execute(text("SELECT id, asset_code FROM machines WHERE tenant_id=:t AND asset_code='NASA-FD001-TEST-1'"),
                            dict(t=tenant_id)).mappings().one()
        machine_id = machine['id']
        print(f'Machine {machine["asset_code"]} ID: {machine_id}')

    # 4. Ingest 31 cycles of engine 1
    print('Ingesting telemetry cycles 1 to 31...')
    source, rows = load_selection(data_dir, 'FD001', 'test', 1, 1, 31)
    batch = Batch.model_validate(dict(source=source, observations=rows))

    with db.transaction() as s:
        ingest_res = ingest(s, tenant_id, machine_id, admin_id, uuid4(), batch, 'demo-seed-engine-1-batch-1')
        print('Ingestion completed:', ingest_res['batch']['inserted_count'], 'cycles inserted,',
              ingest_res['batch']['existing_count'], 'existing.')

    print('\nDemo preparation successfully complete!')
    print(f'Tenant ID: {tenant_id}')
    print(f'Admin Email: {admin_email} | Password: {password}')
    print(f'Tech Email: {tech_email} | Password: {password}')
    print(f'Machine Code: NASA-FD001-TEST-1 | ID: {machine_id}')


if __name__ == '__main__':
    prepare_demo()
