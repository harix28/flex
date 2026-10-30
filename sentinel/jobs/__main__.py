"""Operator-only drift/fleet producers and durable worker. No public HTTP surface."""
import argparse
import json
import time
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from sentinel.config import load_database_url
from sentinel.db import Database
from .queue import enqueue, run_once


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    producer = commands.add_parser('enqueue-drift')
    producer.add_argument('--tenant', type=UUID, required=True)
    producer.add_argument('--source-event-id', required=True)
    fleet = commands.add_parser('enqueue-fleet')
    fleet.add_argument('--tenant', type=UUID, required=True)
    fleet.add_argument('--actor', type=UUID, required=True)
    fleet.add_argument('--source-event-id', required=True)
    status = commands.add_parser('status')
    status.add_argument('--tenant', type=UUID, required=True)
    status.add_argument('--job', type=UUID, required=True)
    worker = commands.add_parser('work')
    worker.add_argument('--once', action='store_true')
    args = parser.parse_args()
    db = Database(load_database_url())
    try:
        if not db.ready():
            raise SystemExit('Database migration required before starting jobs')
        if args.command == 'enqueue-drift':
            with db.transaction() as s:
                job_id = enqueue(s, args.tenant, args.source_event_id, {})
            print(job_id)
        elif args.command == 'enqueue-fleet':
            from sentinel.config import load_settings
            from sentinel.inference import Predictor
            from .fleet import enqueue_fleet
            settings = load_settings().require_model()
            predictor = Predictor(settings.model_dir, settings.bundle_sha256)
            with db.transaction() as s:
                job_id = enqueue_fleet(s, args.tenant, args.actor, args.source_event_id, predictor)
            print(job_id)
        elif args.command == 'status':
            with db.transaction() as s:
                row = s.execute(text('''SELECT id,event_type,status,attempts,max_attempts,error_code,result
                    FROM outbox_events WHERE tenant_id=:t AND id=:id'''),
                    dict(t=args.tenant, id=args.job)).mappings().one_or_none()
            if row is None:
                raise SystemExit('Job not found in this tenant')
            print(json.dumps(dict(row), default=str))
        else:
            while True:
                worked = run_once(db)
                if args.once:
                    break
                if not worked:
                    time.sleep(2)
    except KeyboardInterrupt:
        pass
    except SQLAlchemyError:
        raise SystemExit('Job database operation failed; check database availability, permissions and tenant ID') from None
    except (ValueError, OSError, HTTPException):
        raise SystemExit('Job rejected; check input, requester permissions, fleet size and verified model configuration') from None
    finally:
        db.close()


if __name__ == '__main__':
    main()
