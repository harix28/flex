import json
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text


class DriftPayload(BaseModel):
    # Model paths, credentials and model promotion are deliberately not job inputs.
    model_config = ConfigDict(extra='forbid')


def enqueue(session, tenant_id: UUID, source_event_id: str, payload: dict, *, event_type='drift.evaluate'):
    """Use the caller's transaction so domain writes and enqueue commit together."""
    tenant_id = UUID(str(tenant_id))
    if (not isinstance(source_event_id, str) or not 1 <= len(source_event_id) <= 128
            or source_event_id != source_event_id.strip()):
        raise ValueError('Invalid source event ID')
    from .fleet import FleetPayload
    schemas = {'drift.evaluate': DriftPayload, 'fleet.score': FleetPayload}
    if event_type not in schemas:
        raise ValueError('Unsupported event type')
    body = json.dumps(schemas[event_type].model_validate(payload).model_dump(mode='json'))
    row = session.execute(text("""INSERT INTO outbox_events
        (tenant_id,event_type,source_event_id,payload)
        VALUES (:t,:event_type,:key,CAST(:body AS jsonb))
        ON CONFLICT (tenant_id,event_type,source_event_id) DO NOTHING RETURNING id"""),
        dict(t=tenant_id, key=source_event_id, body=body, event_type=event_type)).scalar_one_or_none()
    if row is not None:
        return row
    previous = session.execute(text("""SELECT id,payload FROM outbox_events WHERE tenant_id=:t
        AND event_type=:event_type AND source_event_id=:key"""),
        dict(t=tenant_id, key=source_event_id, event_type=event_type)).mappings().one()
    if previous['payload'] != json.loads(body):
        raise ValueError('Source event ID reused with a different payload')
    return previous['id']


def claim(database):
    with database.transaction() as s:
        row = s.execute(text("""SELECT * FROM outbox_events
            WHERE (status='pending' AND next_attempt_at<=clock_timestamp())
               OR (status='claimed' AND lease_until<=clock_timestamp())
            ORDER BY next_attempt_at,created_at FOR UPDATE SKIP LOCKED LIMIT 1""")).mappings().one_or_none()
        if row is None:
            return None
        row = dict(row)
        if row['attempts'] >= row['max_attempts']:
            s.execute(text("""UPDATE outbox_events SET status='dead_letter',lease_token=NULL,
                lease_until=NULL,error_code='attempts_exhausted',completed_at=clock_timestamp()
                WHERE id=:id"""), row)
            return None
        row['lease_token'] = uuid4()
        s.execute(text("""UPDATE outbox_events SET status='claimed',attempts=attempts+1,
            lease_token=:lease_token,lease_until=clock_timestamp()+interval '5 minutes'
            WHERE id=:id"""), row)
        return row


def drift_handler(session, job):
    from sentinel.mlops.drift import evaluate_input_drift
    DriftPayload.model_validate(job['payload'])
    result = evaluate_input_drift(session, job['tenant_id'], actor='worker:drift')
    if result.get('status') in ('failed', 'incompatible_reference'):
        raise ValueError('Drift reference unavailable')


def dispatch(session, job):
    if job['event_type'] == 'drift.evaluate':
        return drift_handler(session, job)
    if job['event_type'] == 'fleet.score':
        from sentinel.config import load_settings
        from sentinel.inference import Predictor
        from .fleet import fleet_handler
        settings = load_settings().require_model()
        predictor = Predictor(settings.model_dir, settings.bundle_sha256)
        return fleet_handler(session, job, predictor)
    raise ValueError('Unsupported event')


def run_once(database, handler=dispatch):
    job = claim(database)
    if job is None:
        return False
    with database.transaction() as s:
        # Hold the row lock through handler and acknowledgement: a stale lease cannot
        # commit effects while another worker owns the job. DB-only handlers share s.
        row = s.execute(text("""SELECT * FROM outbox_events WHERE id=:id AND tenant_id=:tenant_id
            AND status='claimed' AND lease_token=:lease_token FOR UPDATE"""), job).mappings().one_or_none()
        if row is None:
            return True
        try:
            with s.begin_nested():
                result = handler(s, dict(row))
                result_json = json.dumps(result, allow_nan=False)
        except Exception:
            # Never persist exception strings: drivers and adapters may include secrets.
            s.execute(text("""UPDATE outbox_events SET
                status=CASE WHEN attempts>=max_attempts THEN 'dead_letter' ELSE 'pending' END,
                completed_at=CASE WHEN attempts>=max_attempts THEN clock_timestamp() ELSE NULL END,
                next_attempt_at=clock_timestamp()+make_interval(secs=>LEAST(3600, power(2,attempts)::int)),
                error_code='handler_failed',lease_token=NULL,lease_until=NULL WHERE id=:id"""), job)
        else:
            s.execute(text("""UPDATE outbox_events SET status='delivered',completed_at=clock_timestamp(),
                error_code=NULL,lease_token=NULL,lease_until=NULL,result=CAST(:result AS jsonb) WHERE id=:id"""),
                dict(job, result=result_json if result is not None else None))
    return True
