"""Script to populate all 100 test engines of FD001 into the organization database."""
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
    env_vars = read_env(env_file)
    db = Database(env_vars['DATABASE_URL'])
    data_dir = ROOT / 'data/raw'
    tenant_slug = 'meridian-a'

    with db.transaction() as s:
        tenant_id = s.execute(text('SELECT id FROM tenants WHERE slug=:slug'), dict(slug=tenant_slug)).scalar_one()
        admin_id = s.execute(text("SELECT id FROM users WHERE email='admin@meridian.example.com'")).scalar_one()

    print(f'Starting full population for {tenant_slug}...')
    
    # Register all 100 FD001 test engines in batches of 20 (governed by registry validation)
    for batch_start in range(1, 101, 20):
        engines = list(range(batch_start, min(batch_start + 20, 101)))
        print(f'Registering FD001 engines {engines[0]} to {engines[-1]}...')
        register_replay(db, tenant_id, admin_id, 'FD001', engines, data_dir)

    predictor = Predictor('runs/fd001-v1', '06d46a9c4f5f71aeb220ade135e52e713a0bd41f362e7caf00eda743442e7cfd')

    # Ingest and predict for each of the 100 engines
    for engine_id in range(1, 101):
        asset_code = f'NASA-FD001-TEST-{engine_id}'
        with db.transaction() as s:
            machine = s.execute(text('SELECT id FROM machines WHERE tenant_id=:t AND asset_code=:c'),
                                dict(t=tenant_id, c=asset_code)).mappings().one()
            m_id = machine['id']

        source, rows = load_selection(data_dir, 'FD001', 'test', engine_id)
        for offset in range(0, len(rows), MAX_BATCH):
            batch_rows = rows[offset:offset + MAX_BATCH]
            batch = Batch.model_validate(dict(source=source, observations=batch_rows))
            with db.transaction() as s:
                ingest(s, tenant_id, m_id, admin_id, uuid4(), batch, f'seed-fd001-e{engine_id}-b{offset}')

        with db.transaction() as s:
            pred = compute_and_persist(s, tenant_id, m_id, admin_id, uuid4(), predictor)
            rul = f"{pred.get('rul_cycles', 0):.1f} cycles" if pred.get('rul_cycles') is not None else 'N/A'
            print(f'Engine {engine_id:3d}/100: RUL = {rul:>12} | Priority = {pred.get("priority_band"):<7}')

    print('\nSuccessfully ingested and predicted all 100 test engines of FD001!')


if __name__ == '__main__':
    main()

