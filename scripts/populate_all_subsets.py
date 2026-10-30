"""Populate test engines from FD002, FD003, and FD004 into the organization database."""
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from sentinel.config import ROOT, read_env
from sentinel.db import Database
from sentinel.registry.replay import register_replay
from sentinel.ingestion.importer import load_selection
from sentinel.ingestion.schemas import Batch, MAX_BATCH
from sentinel.ingestion.service import ingest
from sentinel.inference import load_multi_predictor
from sentinel.predictions.service import compute_and_persist


def main():
    import os
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        env_file = ROOT / '.runtime/postgres.env'
        env_vars = read_env(env_file)
        db_url = env_vars['DATABASE_URL']
    db = Database(db_url)
    data_dir = ROOT / 'data/raw'
    tenant_slug = 'meridian-a'

    with db.transaction() as s:
        tenant_id = s.execute(text('SELECT id FROM tenants WHERE slug=:slug'), dict(slug=tenant_slug)).scalar_one()
        admin_id = s.execute(text("SELECT id FROM users WHERE email='admin@meridian.example.com'")).scalar_one()

    print(f"[POPULATE] Connecting to tenant {tenant_slug}...")
    predictor = load_multi_predictor('runs/fd001-v1', '06d46a9c4f5f71aeb220ade135e52e713a0bd41f362e7caf00eda743442e7cfd', project_root=ROOT)
    print(f"[POPULATE] MultiPredictor loaded with subsets: {list(predictor.predictors.keys())}")

    # Subsets to add: FD002, FD003, FD004
    subsets_to_add = ['FD002', 'FD003', 'FD004']
    engines_per_subset = 20  # Ingest 20 engines per subset (60 additional engines total)

    for subset in subsets_to_add:
        print(f"\n=======================================================")
        print(f"[SUBSET {subset}] Registering engines 1 to {engines_per_subset}...")
        engine_ids = list(range(1, engines_per_subset + 1))
        
        reg_result = register_replay(db, tenant_id, admin_id, subset, engine_ids, data_dir, split='test')
        print(f"[SUBSET {subset}] Registered: {len(reg_result['results'])} engines.")

        for engine_id in engine_ids:
            asset_code = f'NASA-{subset}-TEST-{engine_id}'
            with db.transaction() as s:
                machine = s.execute(
                    text('SELECT id FROM machines WHERE tenant_id=:t AND asset_code=:c'),
                    dict(t=tenant_id, c=asset_code)
                ).mappings().one()
                m_id = machine['id']

            # Ingest observations
            try:
                source, rows = load_selection(data_dir, subset, 'test', engine_id)
                for offset in range(0, len(rows), MAX_BATCH):
                    batch_rows = rows[offset:offset + MAX_BATCH]
                    batch = Batch.model_validate(dict(source=source, observations=batch_rows))
                    with db.transaction() as s:
                        ingest(s, tenant_id, m_id, admin_id, uuid4(), batch, f'seed-{subset.lower()}-e{engine_id}-b{offset}')

                # Predict with multi-predictor
                with db.transaction() as s:
                    pred = compute_and_persist(s, tenant_id, m_id, admin_id, uuid4(), predictor)
                    rul = f"{pred.get('rul_cycles', 0):.1f} cycles" if pred.get('rul_cycles') is not None else 'N/A'
                    print(f"  {asset_code}: {len(rows):3d} cycles | RUL = {rul:>12} | Priority = {pred.get('priority_band'):<7}")
            except Exception as e:
                print(f"  {asset_code}: Failed ({e})")

    print("\n[COMPLETE] Successfully populated and predicted test engines for FD002, FD003, and FD004!")


if __name__ == '__main__':
    main()

