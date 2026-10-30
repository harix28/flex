"""Bounded, explicit fleet runs against frozen observation windows and model identity."""
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from sentinel.auth.permissions import permits
from sentinel.auth.service import lock_tenant
from sentinel.predictions.policy import DEFAULT_POLICY
from sentinel.predictions.service import compute_input_digest, compute_and_persist


class MachineSnapshot(BaseModel):
    model_config = ConfigDict(extra='forbid')
    machine_id: UUID
    stream_id: UUID | None
    cutoff_cycle: int = Field(strict=True, ge=1, le=2147483647)
    input_digest: str = Field(pattern=r'^[0-9a-f]{64}$')


class FleetPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    actor_id: UUID
    bundle_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    policy_version: str
    machines: list[MachineSnapshot] = Field(max_length=100)


def authorize(session, tenant, actor):
    lock_tenant(session, tenant)
    member = session.execute(text("""SELECT m.roles FROM memberships m JOIN users u ON u.id=m.user_id
        WHERE m.tenant_id=:t AND m.user_id=:u AND m.active AND u.active
        FOR SHARE OF m,u"""), dict(t=tenant, u=actor)).mappings().one_or_none()
    if member is None or not permits(member['roles'], 'predictions.create'):
        raise ValueError('Fleet scoring permission unavailable')


def snapshot(session, tenant, machine, predictor, cutoff=None):
    stream = session.execute(text('SELECT id FROM replay_streams WHERE tenant_id=:t AND machine_id=:m'),
                             dict(t=tenant, m=machine)).scalar_one_or_none()
    if cutoff is None:
        cutoff = session.execute(text('SELECT max(cycle) FROM replay_observations WHERE tenant_id=:t AND machine_id=:m AND stream_id=:s'),
                                 dict(t=tenant, m=machine, s=stream)).scalar_one_or_none() or 1
    rows = session.execute(text("""SELECT cycle,settings,sensors FROM replay_observations
        WHERE tenant_id=:t AND machine_id=:m AND stream_id=:s AND cycle BETWEEN :start AND :end ORDER BY cycle"""),
        dict(t=tenant, m=machine, s=stream, start=max(1, cutoff-predictor.meta['window']+1), end=cutoff)).mappings().all()
    return MachineSnapshot(machine_id=machine, stream_id=stream, cutoff_cycle=cutoff,
                           input_digest=compute_input_digest([[r['cycle'], list(r['settings']), list(r['sensors'])] for r in rows]))


def enqueue_fleet(session, tenant, actor, source_event_id, predictor, machine_ids=None):
    from .queue import enqueue
    tenant, actor = UUID(str(tenant)), UUID(str(actor))
    authorize(session, tenant, actor)
    # Retry returns the originally frozen fleet even when telemetry has advanced.
    previous = session.execute(text("""SELECT id,payload FROM outbox_events WHERE tenant_id=:t
        AND event_type='fleet.score' AND source_event_id=:key"""), dict(t=tenant, key=source_event_id)).mappings().one_or_none()
    if previous:
        if previous['payload']['actor_id'] != str(actor):
            raise ValueError('Source event ID belongs to another requester')
        return previous['id']
    if machine_ids is not None:
        machines = session.execute(text("""SELECT id FROM machines WHERE tenant_id=:t
            AND id=ANY(CAST(:mids AS uuid[])) AND lifecycle_status='active' ORDER BY id LIMIT 101 FOR SHARE"""),
            dict(t=tenant, mids=[UUID(str(m)) for m in machine_ids])).scalars().all()
    else:
        machines = session.execute(text("""SELECT id FROM machines WHERE tenant_id=:t
            AND lifecycle_status='active' ORDER BY id LIMIT 101 FOR SHARE"""), dict(t=tenant)).scalars().all()
    if len(machines) > 100:
        raise ValueError('Fleet exceeds the 100-machine limit')
    payload = FleetPayload(actor_id=actor, bundle_sha256=predictor.bundle_sha256,
                           policy_version=DEFAULT_POLICY.version,
                           machines=[snapshot(session, tenant, m, predictor) for m in machines])
    return enqueue(session, tenant, source_event_id, payload.model_dump(mode='json'), event_type='fleet.score')


def fleet_handler(session, job, predictor):
    payload = FleetPayload.model_validate(job['payload'])
    authorize(session, job['tenant_id'], payload.actor_id)
    if predictor.bundle_sha256 != payload.bundle_sha256 or payload.policy_version != DEFAULT_POLICY.version:
        raise ValueError('Queued model or policy no longer matches worker')
    results = []
    for target in payload.machines:
        active = session.execute(text("""SELECT id FROM machines WHERE tenant_id=:t AND id=:m
            AND lifecycle_status='active' FOR SHARE"""), dict(t=job['tenant_id'], m=target.machine_id)).scalar_one_or_none()
        if active is None:
            raise ValueError('Queued machine no longer available')
        if snapshot(session, job['tenant_id'], target.machine_id, predictor, target.cutoff_cycle) != target:
            raise ValueError('Queued input window changed')
        prediction = compute_and_persist(session, job['tenant_id'], target.machine_id, payload.actor_id,
                                         job['id'], predictor, cutoff_cycle=target.cutoff_cycle)
        if (prediction['reason'] not in ('unsupported_machine', 'unsupported_subset')
                and prediction['input_digest'] != target.input_digest):
            raise ValueError('Prediction did not use frozen input')
        results.append(dict(machine_id=str(target.machine_id), prediction_id=str(prediction['id']),
                            status=prediction['status'], reason=prediction['reason']))
    return dict(machines=results, total=len(results), available=sum(r['status']=='available' for r in results),
                unavailable=sum(r['status']=='unavailable' for r in results))
