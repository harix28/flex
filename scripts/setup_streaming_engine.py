"""Register a dedicated streaming engine (NASA-FD001-TRAIN-1) with full 192-cycle degradation trajectory."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sentinel.config import ROOT, read_env
from sentinel.db import Database
from sentinel.registry.replay import register_replay
from sqlalchemy import text


def main():
    env_file = ROOT / '.runtime/postgres.env'
    env = read_env(env_file)
    db = Database(env['DATABASE_URL'])

    with db.transaction() as s:
        tenant_id = s.execute(text("SELECT id FROM tenants WHERE slug='meridian-a'")).scalar_one()
        admin_id = s.execute(text("SELECT id FROM users WHERE email='admin@meridian.example.com'")).scalar_one()

    print("Registering training engine 1 for live streaming telemetry...")
    result = register_replay(db, tenant_id, admin_id, 'FD001', [1], ROOT / 'data/raw', split='train')
    print("Registration completed:")
    print(result)


if __name__ == '__main__':
    main()
