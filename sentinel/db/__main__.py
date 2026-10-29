"""Safe operator commands: python -m sentinel.db check|upgrade|seed-demo."""
import argparse
from alembic import command
from alembic.config import Config
from sentinel.config import ROOT, load_database_url
from sentinel.db import Database
from sentinel.db.seed import seed_demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'upgrade', 'seed-demo'])
    parser.add_argument('--env-file', help='Private environment file; defaults to project .env')
    args = parser.parse_args()
    database = None
    try:
        url = load_database_url(args.env_file)
        if args.action == 'upgrade':
            config = Config(str(ROOT / 'alembic.ini'))
            config.attributes['database_url'] = url
            command.upgrade(config, 'head')
        else:
            database = Database(url)
            if not database.ready():
                raise RuntimeError()
            if args.action == 'seed-demo':
                seed_demo(database)
    except Exception:
        raise SystemExit('Database operation failed: check private configuration, server availability and migration state; no credentials printed.') from None
    finally:
        if database:
            database.close()
    print('Database ' + args.action + ' succeeded.')


if __name__ == '__main__':
    main()
