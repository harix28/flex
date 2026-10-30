"""Populate an operational fleet of turbofan engines for the web portal.

Registers engines from NASA C-MAPSS test sets into the organization, ingests their telemetry,
and computes initial causal RUL predictions and maintenance priority bands.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uuid import uuid4
from sqlalchemy import text
from sentinel.config import ROOT, read_env
from sentinel.db import Database
from sentinel.registry.replay import register_replay
from sentinel.ingestion.importer import load_selection
from sentinel.ingestion.schemas import Batch, MAX_BATCH
from sentinel.ingestion.service import ingest
from sentinel.inference import Predictor
from sentinel.predictions.service import compute_and_persist


def main():
    env_file = ROOT / '.runtime/postgres.env'
    if not env_file.exists():
        raise SystemExit('Missing .runtime/postgres.env')
    
    env_vars = read_env(env_file)
    db = Database(env_vars['DATABASE_URL'])
    data_dir = ROOT / 'data/raw'
    tenant_slug = 'meridian-a'

    with db.transaction() as s:
        tenant_id = s.execute(text('SELECT id FROM tenants WHERE slug=:slug'), dict(slug=tenant_slug)).scalar_one()
        admin_id = s.execute(text("SELECT id FROM users WHERE email='admin@meridian.example.com'")).scalar_one()

    print(f'Populating fleet for organization {tenant_slug} ({tenant_id})...')

    # 1. Register FD001 engines (batches of up to 20)
    fd001_engines = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 24, 31, 34, 37]
    print(f'Registering {len(fd001_engines)} FD001 test engines in registry...')
    register_replay(db, tenant_id, admin_id, 'FD001', fd001_engines, data_dir)

    # 2. Register FD003 engines
    fd003_engines = [1, 2, 3]
    print(f'Registering {len(fd003_engines)} FD003 test engines in registry...')
    register_replay(db, tenant_id, admin_id, 'FD003', fd003_engines, data_dir)

    # 3. Load active serving predictor
    predictor = Predictor('runs/fd001-v1', '06d46a9c4f5f71aeb220ade135e52e713a0bd41f362e7caf00eda743442e7cfd')

    # 4. Ingest telemetry and compute predictions for FD001 engines
    for engine_id in fd001_engines:
        asset_code = f'NASA-FD001-TEST-{engine_id}'
        with db.transaction() as s:
            machine = s.execute(text('SELECT id FROM machines WHERE tenant_id=:t AND asset_code=:c'),
                                dict(t=tenant_id, c=asset_code)).mappings().one()
            m_id = machine['id']

        source, rows = load_selection(data_dir, 'FD001', 'test', engine_id)
        # Ingest in chunks
        for offset in range(0, len(rows), MAX_BATCH):
            batch_rows = rows[offset:offset + MAX_BATCH]
            batch = Batch.model_validate(dict(source=source, observations=batch_rows))
            with db.transaction() as s:
                ingest(s, tenant_id, m_id, admin_id, uuid4(), batch, f'seed-fd001-e{engine_id}-b{offset}')

        # Compute and persist latest prediction
        with db.transaction() as s:
            pred = compute_and_persist(s, tenant_id, m_id, admin_id, uuid4(), predictor)
            rul = f"{pred.get('rul_cycles', 0):.1f} cycles" if pred.get('rul_cycles') is not None else 'N/A'
            print(f'  [OK] {asset_code}: Ingested {len(rows)} cycles | RUL: {rul} | Priority: {pred.get("priority_band")}')

    # 5. Ingest telemetry for FD003 engines
    for engine_id in fd003_engines:
        asset_code = f'NASA-FD003-TEST-{engine_id}'
        with db.transaction() as s:
            machine = s.execute(text('SELECT id FROM machines WHERE tenant_id=:t AND asset_code=:c'),
                                dict(t=tenant_id, c=asset_code)).mappings().one()
            m_id = machine['id']

        source, rows = load_selection(data_dir, 'FD003', 'test', engine_id)
        for offset in range(0, len(rows), MAX_BATCH):
            batch_rows = rows[offset:offset + MAX_BATCH]
            batch = Batch.model_validate(dict(source=source, observations=batch_rows))
            with db.transaction() as s:
                ingest(s, tenant_id, m_id, admin_id, uuid4(), batch, f'seed-fd003-e{engine_id}-b{offset}')

        with db.transaction() as s:
            pred = compute_and_persist(s, tenant_id, m_id, admin_id, uuid4(), predictor)
            print(f'  [OK] {asset_code}: Ingested {len(rows)} cycles | Status: {pred.get("status")} ({pred.get("reason")}) | Priority: {pred.get("priority_band")}')

    print('\nFleet successfully populated!')


if __name__ == '__main__':
    main()
