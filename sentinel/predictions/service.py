"""Service layer for persistent predictions, causal window extraction, idempotency, and maintenance priority evaluation."""
import hashlib
import json
import time
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sentinel.data import COLUMNS
from .policy import DEFAULT_POLICY, PriorityPolicy, PriorityBand

MAX_PAGE_LIMIT = 100


def compute_input_digest(records: list) -> str:
    """Computes deterministic SHA-256 hex digest of trailing input observations."""
    serialized = json.dumps(records, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def prediction_view(row, idempotency_replayed: bool = False, priority_rule: str | None = None) -> dict:
    d = dict(row)
    d['idempotency_replayed'] = idempotency_replayed
    d['rul_units'] = 'cycles'
    d['failure_probability'] = None
    d['interval'] = None
    d['diagnosis_basis'] = 'unavailable'
    d['release_status'] = 'experiment_only'
    d['input_window_start_cycle'] = d.get('input_start_cycle')
    d['input_window_end_cycle'] = d.get('input_end_cycle')
    if priority_rule is not None:
        d['priority_rule'] = priority_rule
    elif 'priority_rule' not in d or d['priority_rule'] is None:
        rule_band, rule_text = DEFAULT_POLICY.evaluate(d['status'], d.get('rul_cycles'), d.get('reason'))
        d['priority_rule'] = rule_text
    return d


def get_machine(s, tenant: UUID, machine_id: UUID, for_update: bool = False):
    query = 'SELECT * FROM machines WHERE tenant_id=:t AND id=:m' + (' FOR UPDATE' if for_update else '')
    row = s.execute(text(query), dict(t=tenant, m=machine_id)).mappings().one_or_none()
    if row is None:
        raise HTTPException(404, 'not_found')
    return row


def compute_and_persist(
    s,
    tenant: UUID,
    machine_id: UUID,
    actor_id: UUID,
    request_id: UUID,
    predictor,
    cutoff_cycle: int | None = None,
    policy: PriorityPolicy = DEFAULT_POLICY,
) -> dict:
    """Extracts trailing window from stored observations, runs inference, and atomically persists provenance."""
    pipeline_start = time.perf_counter()
    machine = get_machine(s, tenant, machine_id)

    # Validate model availability
    if predictor is None:
        raise HTTPException(503, 'model_not_loaded')

    model_meta = predictor.meta
    model_version = str(model_meta['version'])
    model_digest = str(model_meta['model_sha256'])
    bundle_digest = str(hashlib.sha256(json.dumps(model_meta, sort_keys=True, separators=(',', ':')).encode()).hexdigest()) if 'bundle_sha256' not in model_meta else str(model_meta['bundle_sha256'])
    if 'bundle_sha256' in predictor.report:
        bundle_digest = str(predictor.report['bundle_sha256'])
    window_size = int(model_meta['window'])

    # Reject unsupported machine types or subsets
    if machine['data_source'] != 'nasa_replay' or machine['machine_type'] != 'cmapss_engine':
        status = 'unavailable'
        reason = 'unsupported_machine'
        requested_cutoff = cutoff_cycle if cutoff_cycle is not None else 1
        input_digest = hashlib.sha256(b'[]').hexdigest()
        stream_id = None
        band, rule = policy.evaluate(status, None, reason)
        return _persist_or_get_existing(
            s, tenant, machine_id, stream_id, actor_id, request_id, status, reason,
            requested_cutoff, None, None, None, 0, input_digest,
            model_version, model_digest, bundle_digest, 1, 1, None, policy.version, band, rule
        )

    if machine['source_subset'] != model_meta['subset']:
        status = 'unavailable'
        reason = 'unsupported_subset'
        requested_cutoff = cutoff_cycle if cutoff_cycle is not None else 1
        input_digest = hashlib.sha256(b'[]').hexdigest()
        stream_id = None
        band, rule = policy.evaluate(status, None, reason)
        return _persist_or_get_existing(
            s, tenant, machine_id, stream_id, actor_id, request_id, status, reason,
            requested_cutoff, None, None, None, 0, input_digest,
            model_version, model_digest, bundle_digest, 1, 1, None, policy.version, band, rule
        )

    # Resolve replay stream
    stream = s.execute(
        text('SELECT * FROM replay_streams WHERE tenant_id=:t AND machine_id=:m'),
        dict(t=tenant, m=machine_id)
    ).mappings().one_or_none()

    if stream is None:
        status = 'unavailable'
        reason = 'no_observations'
        requested_cutoff = cutoff_cycle if cutoff_cycle is not None else 1
        input_digest = hashlib.sha256(b'[]').hexdigest()
        band, rule = policy.evaluate(status, None, reason)
        return _persist_or_get_existing(
            s, tenant, machine_id, None, actor_id, request_id, status, reason,
            requested_cutoff, None, None, None, 0, input_digest,
            model_version, model_digest, bundle_digest, 1, 1, None, policy.version, band, rule
        )

    stream_id = stream['id']

    # Resolve cutoff cycle
    max_stored_cycle = s.execute(
        text('SELECT max(cycle) FROM replay_observations WHERE tenant_id=:t AND machine_id=:m AND stream_id=:s'),
        dict(t=tenant, m=machine_id, s=stream_id)
    ).scalar_one_or_none()

    if max_stored_cycle is None:
        status = 'unavailable'
        reason = 'no_observations'
        requested_cutoff = cutoff_cycle if cutoff_cycle is not None else 1
        input_digest = hashlib.sha256(b'[]').hexdigest()
        band, rule = policy.evaluate(status, None, reason)
        return _persist_or_get_existing(
            s, tenant, machine_id, stream_id, actor_id, request_id, status, reason,
            requested_cutoff, None, None, None, 0, input_digest,
            model_version, model_digest, bundle_digest, 1, 1, None, policy.version, band, rule
        )

    requested_cutoff = cutoff_cycle if cutoff_cycle is not None else max_stored_cycle

    # Check sufficient history
    if requested_cutoff < window_size:
        # Retrieve whatever is available at or before cutoff
        partial_rows = s.execute(
            text("""SELECT cycle, settings, sensors FROM replay_observations
                    WHERE tenant_id=:t AND machine_id=:m AND stream_id=:s AND cycle <= :c
                    ORDER BY cycle ASC"""),
            dict(t=tenant, m=machine_id, s=stream_id, c=requested_cutoff)
        ).mappings().all()
        obs_data = [[r['cycle'], list(r['settings']), list(r['sensors'])] for r in partial_rows]
        input_digest = compute_input_digest(obs_data)
        observed_cutoff = max([r['cycle'] for r in partial_rows]) if partial_rows else None
        start_c = min([r['cycle'] for r in partial_rows]) if partial_rows else None
        band, rule = policy.evaluate('unavailable', None, 'insufficient_history')
        return _persist_or_get_existing(
            s, tenant, machine_id, stream_id, actor_id, request_id, 'unavailable', 'insufficient_history',
            requested_cutoff, observed_cutoff, start_c, observed_cutoff, len(partial_rows), input_digest,
            model_version, model_digest, bundle_digest, 1, 1, None, policy.version, band, rule
        )

    # Window selection: strictly trailing window ending at requested_cutoff
    expected_start = requested_cutoff - window_size + 1
    window_rows = s.execute(
        text("""SELECT cycle, settings, sensors FROM replay_observations
                WHERE tenant_id=:t AND machine_id=:m AND stream_id=:s
                  AND cycle BETWEEN :start AND :end
                ORDER BY cycle ASC"""),
        dict(t=tenant, m=machine_id, s=stream_id, start=expected_start, end=requested_cutoff)
    ).mappings().all()

    obs_data = [[r['cycle'], list(r['settings']), list(r['sensors'])] for r in window_rows]
    input_digest = compute_input_digest(obs_data)
    observed_cutoff = max([r['cycle'] for r in window_rows]) if window_rows else None
    start_c = min([r['cycle'] for r in window_rows]) if window_rows else None

    # Check for gaps or missing observations
    if len(window_rows) < window_size:
        # Determine whether it's insufficient history or gaps
        cycles = [r['cycle'] for r in window_rows]
        has_gaps = any(b - a != 1 for a, b in zip(cycles, cycles[1:])) if len(cycles) > 1 else False
        reason = 'gaps_in_history' if (has_gaps or (observed_cutoff is not None and observed_cutoff < requested_cutoff)) else 'insufficient_history'
        band, rule = policy.evaluate('unavailable', None, reason)
        return _persist_or_get_existing(
            s, tenant, machine_id, stream_id, actor_id, request_id, 'unavailable', reason,
            requested_cutoff, observed_cutoff, start_c, observed_cutoff, len(window_rows), input_digest,
            model_version, model_digest, bundle_digest, 1, 1, None, policy.version, band, rule
        )

    cycles = [r['cycle'] for r in window_rows]
    if cycles != list(range(expected_start, requested_cutoff + 1)):
        band, rule = policy.evaluate('unavailable', None, 'gaps_in_history')
        return _persist_or_get_existing(
            s, tenant, machine_id, stream_id, actor_id, request_id, 'unavailable', 'gaps_in_history',
            requested_cutoff, observed_cutoff, start_c, observed_cutoff, len(window_rows), input_digest,
            model_version, model_digest, bundle_digest, 1, 1, None, policy.version, band, rule
        )

    # Valid contiguous trailing window: reconstruct canonical 26-column records
    records = [
        dict(zip(COLUMNS, [stream['engine_id'], r['cycle']] + list(r['settings']) + list(r['sensors'])))
        for r in window_rows
    ]

    infer_ms = None
    try:
        infer_start = time.perf_counter()
        pred_result = predictor.predict(model_meta['subset'], records)
        infer_ms = (time.perf_counter() - infer_start) * 1000.0
        if pred_result['status'] == 'available':
            status = 'available'
            reason = None
            rul_cycles = float(pred_result['rul_cycles'])
        else:
            status = 'unavailable'
            reason = pred_result.get('reason', 'nonfinite_model_output')
            rul_cycles = None
    except ValueError:
        status = 'unavailable'
        reason = 'invalid_stored_input'
        rul_cycles = None

    pipeline_ms = (time.perf_counter() - pipeline_start) * 1000.0
    band, rule = policy.evaluate(status, rul_cycles, reason)

    return _persist_or_get_existing(
        s, tenant, machine_id, stream_id, actor_id, request_id, status, reason,
        requested_cutoff, requested_cutoff, expected_start, requested_cutoff, len(window_rows), input_digest,
        model_version, model_digest, bundle_digest, 1, 1, rul_cycles, policy.version, band, rule,
        inference_ms=infer_ms, pipeline_ms=pipeline_ms
    )


def _persist_or_get_existing(
    s, tenant_id, machine_id, stream_id, actor_id, request_id, status, reason,
    requested_cutoff, observed_cutoff, input_start, input_end, input_count, input_digest,
    model_version, model_digest, bundle_digest, inference_version, feature_schema_version,
    rul_cycles, policy_version, priority_band, priority_rule,
    inference_ms: float | None = None, pipeline_ms: float | None = None
) -> dict:
    """Atomic idempotent persistence with concurrent duplicate safety."""
    # Check if identical prediction record already exists
    existing = s.execute(
        text("""SELECT * FROM predictions
                WHERE tenant_id=:t AND machine_id=:m
                  AND stream_id IS NOT DISTINCT FROM CAST(:s AS uuid)
                  AND requested_cutoff_cycle=:c AND input_digest=:d
                  AND model_digest=:md AND inference_version=:iv"""),
        dict(t=tenant_id, m=machine_id, s=stream_id, c=requested_cutoff,
             d=input_digest, md=model_digest, iv=inference_version)
    ).mappings().one_or_none()

    if existing is not None:
        return prediction_view(existing, idempotency_replayed=True, priority_rule=priority_rule)

    prediction_id = uuid4()
    try:
        with s.begin_nested():
            s.execute(
                text("""INSERT INTO predictions(
                    id, tenant_id, machine_id, stream_id, actor_id, request_id,
                    status, reason, requested_cutoff_cycle, observed_cutoff_cycle,
                    input_start_cycle, input_end_cycle, input_observation_count,
                    input_digest, model_version, model_digest, bundle_digest,
                    inference_version, feature_schema_version, rul_cycles,
                    policy_version, priority_band, inference_ms, pipeline_ms
                ) VALUES (
                    :id, :tenant_id, :machine_id, :stream_id, :actor_id, :request_id,
                    :status, :reason, :requested_cutoff, :observed_cutoff,
                    :input_start, :input_end, :input_count,
                    :input_digest, :model_version, :model_digest, :bundle_digest,
                    :inference_version, :feature_schema_version, :rul_cycles,
                    :policy_version, :priority_band, :inference_ms, :pipeline_ms
                )"""),
                dict(
                    id=prediction_id, tenant_id=tenant_id, machine_id=machine_id, stream_id=stream_id,
                    actor_id=actor_id, request_id=request_id, status=status, reason=reason,
                    requested_cutoff=requested_cutoff, observed_cutoff=observed_cutoff,
                    input_start=input_start, input_end=input_end, input_count=input_count,
                    input_digest=input_digest, model_version=model_version, model_digest=model_digest,
                    bundle_digest=bundle_digest, inference_version=inference_version,
                    feature_schema_version=feature_schema_version, rul_cycles=rul_cycles,
                    policy_version=policy_version, priority_band=priority_band,
                    inference_ms=inference_ms, pipeline_ms=pipeline_ms
                )
            )

            # Audit event
            audit_action = 'prediction_completed' if status == 'available' else 'prediction_failed'
            s.execute(
                text("""INSERT INTO auth_audit_events(
                    action, actor_id, tenant_id, target_type, target_id, request_id
                ) VALUES (:action, :actor, :tenant, 'prediction', :target_id, :req)"""),
                dict(action=audit_action, actor=actor_id, tenant=tenant_id, target_id=prediction_id, req=request_id)
            )
    except IntegrityError:
        # Concurrent request inserted the same record
        existing = s.execute(
            text("""SELECT * FROM predictions
                    WHERE tenant_id=:t AND machine_id=:m
                      AND stream_id IS NOT DISTINCT FROM CAST(:s AS uuid)
                      AND requested_cutoff_cycle=:c AND input_digest=:d
                      AND model_digest=:md AND inference_version=:iv"""),
            dict(t=tenant_id, m=machine_id, s=stream_id, c=requested_cutoff,
                 d=input_digest, md=model_digest, iv=inference_version)
        ).mappings().one_or_none()
        if existing is not None:
            return prediction_view(existing, idempotency_replayed=True, priority_rule=priority_rule)
        raise

    inserted = s.execute(text('SELECT * FROM predictions WHERE id=:id'), dict(id=prediction_id)).mappings().one()
    return prediction_view(inserted, idempotency_replayed=False, priority_rule=priority_rule)


def list_machine_predictions(s, tenant: UUID, machine_id: UUID, limit: int = 25, offset: int = 0, status_filter: str | None = None) -> dict:
    get_machine(s, tenant, machine_id)
    where_status = ' AND status = :st' if status_filter else ''
    params = dict(t=tenant, m=machine_id, limit=limit, offset=offset)
    if status_filter:
        params['st'] = status_filter

    total = s.execute(
        text(f'SELECT count(*) FROM predictions WHERE tenant_id=:t AND machine_id=:m{where_status}'),
        params
    ).scalar_one()

    rows = s.execute(
        text(f"""SELECT * FROM predictions
                WHERE tenant_id=:t AND machine_id=:m{where_status}
                ORDER BY requested_cutoff_cycle DESC, created_at DESC, id DESC
                LIMIT :limit OFFSET :offset"""),
        params
    ).mappings().all()

    return {
        'items': [prediction_view(r) for r in rows],
        'total': total,
        'limit': limit,
        'offset': offset,
    }


def get_latest_prediction(s, tenant: UUID, machine_id: UUID) -> dict:
    get_machine(s, tenant, machine_id)
    row = s.execute(
        text("""SELECT * FROM predictions
                WHERE tenant_id=:t AND machine_id=:m
                ORDER BY requested_cutoff_cycle DESC, created_at DESC, id DESC
                LIMIT 1"""),
        dict(t=tenant, m=machine_id)
    ).mappings().one_or_none()

    if row is None:
        raise HTTPException(404, 'no_predictions_found')

    latest_obs = s.execute(
        text('SELECT max(cycle) FROM replay_observations WHERE tenant_id=:t AND machine_id=:m'),
        dict(t=tenant, m=machine_id)
    ).scalar_one_or_none()

    pred = prediction_view(row)
    is_outdated = (latest_obs is not None and latest_obs > pred['requested_cutoff_cycle'])
    pred['is_outdated'] = is_outdated
    pred['is_current'] = not is_outdated
    pred['latest_observation_cycle'] = latest_obs
    return pred


def get_prediction_by_id(s, tenant: UUID, prediction_id: UUID) -> dict:
    row = s.execute(
        text('SELECT * FROM predictions WHERE tenant_id=:t AND id=:id'),
        dict(t=tenant, id=prediction_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(404, 'not_found')
    return prediction_view(row)


def get_maintenance_priorities(
    s,
    tenant: UUID,
    limit: int = 50,
    offset: int = 0,
    priority_band_filter: PriorityBand | None = None,
    policy: PriorityPolicy = DEFAULT_POLICY,
) -> dict:
    """Ranks all active machines by maintenance priority and ascending RUL with transparent rule explanations."""
    machines = s.execute(
        text("""SELECT id, asset_code, name, machine_type, data_source, lifecycle_status
                FROM machines
                WHERE tenant_id=:t AND lifecycle_status != 'archived'
                ORDER BY asset_code ASC"""),
        dict(t=tenant)
    ).mappings().all()

    items = []
    summary = {'urgent': 0, 'high': 0, 'medium': 0, 'low': 0, 'outdated': 0, 'unknown': 0}

    for m in machines:
        m_id = m['id']
        latest_pred = s.execute(
            text("""SELECT * FROM predictions
                    WHERE tenant_id=:t AND machine_id=:m
                    ORDER BY requested_cutoff_cycle DESC, created_at DESC, id DESC
                    LIMIT 1"""),
            dict(t=tenant, m=m_id)
        ).mappings().one_or_none()

        latest_obs = s.execute(
            text('SELECT max(cycle) FROM replay_observations WHERE tenant_id=:t AND machine_id=:m'),
            dict(t=tenant, m=m_id)
        ).scalar_one_or_none()

        if latest_pred is None:
            item = {
                'machine_id': m_id,
                'asset_code': m['asset_code'],
                'machine_name': m['name'],
                'machine_type': m['machine_type'],
                'priority_band': 'unknown',
                'rul_cycles': None,
                'rul_units': 'cycles',
                'status': 'no_predictions',
                'reason': 'no_prediction_attempt',
                'is_current': False,
                'is_outdated': False,
                'prediction_cutoff_cycle': None,
                'latest_observation_cycle': latest_obs,
                'explanation': 'No predictions recorded for machine; priority unknown',
                'prediction_id': None,
                'model_version': None,
                'model_digest': None,
                'predicted_at': None,
                '_rank_group': 6,
                '_rul_sort': float('inf'),
            }
            summary['unknown'] += 1
        elif latest_pred['status'] == 'unavailable':
            is_outdated = (latest_obs is not None and latest_obs > latest_pred['requested_cutoff_cycle'])
            item = {
                'machine_id': m_id,
                'asset_code': m['asset_code'],
                'machine_name': m['name'],
                'machine_type': m['machine_type'],
                'priority_band': 'unknown',
                'rul_cycles': None,
                'rul_units': 'cycles',
                'status': 'unavailable',
                'reason': latest_pred['reason'],
                'is_current': not is_outdated,
                'is_outdated': is_outdated,
                'prediction_cutoff_cycle': latest_pred['requested_cutoff_cycle'],
                'latest_observation_cycle': latest_obs,
                'explanation': f"Latest prediction attempt unavailable ({latest_pred['reason']}); priority unknown",
                'prediction_id': latest_pred['id'],
                'model_version': latest_pred['model_version'],
                'model_digest': latest_pred['model_digest'],
                'predicted_at': latest_pred['created_at'],
                '_rank_group': 5 if not is_outdated else 4,
                '_rul_sort': float('inf'),
            }
            summary['unknown'] += 1
            if is_outdated:
                summary['outdated'] += 1
        else:
            # available
            rul = float(latest_pred['rul_cycles'])
            is_outdated = (latest_obs is not None and latest_obs > latest_pred['requested_cutoff_cycle'])
            p_band = latest_pred['priority_band']

            if is_outdated:
                item = {
                    'machine_id': m_id,
                    'asset_code': m['asset_code'],
                    'machine_name': m['name'],
                    'machine_type': m['machine_type'],
                    'priority_band': p_band,
                    'rul_cycles': rul,
                    'rul_units': 'cycles',
                    'status': 'outdated',
                    'reason': None,
                    'is_current': False,
                    'is_outdated': True,
                    'prediction_cutoff_cycle': latest_pred['requested_cutoff_cycle'],
                    'latest_observation_cycle': latest_obs,
                    'explanation': f"Outdated prediction (cutoff cycle {latest_pred['requested_cutoff_cycle']} behind current stored cycle {latest_obs}); priority {p_band} based on historical cutoff",
                    'prediction_id': latest_pred['id'],
                    'model_version': latest_pred['model_version'],
                    'model_digest': latest_pred['model_digest'],
                    'predicted_at': latest_pred['created_at'],
                    '_rank_group': 4,
                    '_rul_sort': rul,
                }
                summary['outdated'] += 1
            else:
                band_rank = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}.get(p_band, 5)
                item = {
                    'machine_id': m_id,
                    'asset_code': m['asset_code'],
                    'machine_name': m['name'],
                    'machine_type': m['machine_type'],
                    'priority_band': p_band,
                    'rul_cycles': rul,
                    'rul_units': 'cycles',
                    'status': 'available',
                    'reason': None,
                    'is_current': True,
                    'is_outdated': False,
                    'prediction_cutoff_cycle': latest_pred['requested_cutoff_cycle'],
                    'latest_observation_cycle': latest_obs,
                    'explanation': policy.evaluate('available', rul)[1],
                    'prediction_id': latest_pred['id'],
                    'model_version': latest_pred['model_version'],
                    'model_digest': latest_pred['model_digest'],
                    'predicted_at': latest_pred['created_at'],
                    '_rank_group': band_rank,
                    '_rul_sort': rul,
                }
                summary[p_band] += 1

        items.append(item)

    # Sort deterministically:
    # 1. Rank group: current urgent (0) -> current high (1) -> current medium (2) -> current low (3) -> outdated (4) -> unavailable (5) -> no_predictions (6)
    # 2. Ascending RUL
    # 3. Deterministic tie-breaking by asset_code ASC, machine_id ASC
    items.sort(key=lambda x: (x['_rank_group'], x['_rul_sort'], x['asset_code'], str(x['machine_id'])))

    # Clean internal sorting keys
    for it in items:
        del it['_rank_group']
        del it['_rul_sort']

    # Filter by priority_band if requested
    if priority_band_filter:
        filtered = [it for it in items if it['priority_band'] == priority_band_filter]
    else:
        filtered = items

    total_count = len(filtered)
    paged = filtered[offset:offset + limit]

    return {
        'policy_version': policy.version,
        'policy_thresholds': policy.as_dict(),
        'summary': summary,
        'items': paged,
        'limit': limit,
        'offset': offset,
        'total': total_count,
    }
