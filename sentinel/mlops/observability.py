"""Inference observability and operational telemetry aggregation."""
from uuid import UUID
from sqlalchemy import text


def get_tenant_observability(session, tenant_id: UUID) -> dict:
    """Aggregates operational inference telemetry strictly scoped to a tenant."""
    # 1. Total and status counts
    status_rows = session.execute(
        text("""SELECT status, reason, count(*) as count
                FROM predictions
                WHERE tenant_id = :t
                GROUP BY status, reason"""),
        {'t': tenant_id}
    ).mappings().all()

    total = sum(r['count'] for r in status_rows)
    available = sum(r['count'] for r in status_rows if r['status'] == 'available')
    unavailable = sum(r['count'] for r in status_rows if r['status'] == 'unavailable')
    reasons = {r['reason']: r['count'] for r in status_rows if r['status'] == 'unavailable' and r['reason']}

    # 2. Latency statistics for available predictions
    latency_row = session.execute(
        text("""SELECT
                min(inference_ms) as min_inf,
                max(inference_ms) as max_inf,
                avg(inference_ms) as avg_inf,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY inference_ms) as p50_inf,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY inference_ms) as p95_inf,
                min(pipeline_ms) as min_pipe,
                max(pipeline_ms) as max_pipe,
                avg(pipeline_ms) as avg_pipe
                FROM predictions
                WHERE tenant_id = :t AND status = 'available' AND inference_ms IS NOT NULL"""),
        {'t': tenant_id}
    ).mappings().one_or_none()

    latencies = {
        'inference_ms': {
            'min': float(round(latency_row['min_inf'], 2)) if latency_row and latency_row['min_inf'] is not None else None,
            'max': float(round(latency_row['max_inf'], 2)) if latency_row and latency_row['max_inf'] is not None else None,
            'mean': float(round(latency_row['avg_inf'], 2)) if latency_row and latency_row['avg_inf'] is not None else None,
            'p50': float(round(latency_row['p50_inf'], 2)) if latency_row and latency_row['p50_inf'] is not None else None,
            'p95': float(round(latency_row['p95_inf'], 2)) if latency_row and latency_row['p95_inf'] is not None else None,
        },
        'pipeline_ms': {
            'min': float(round(latency_row['min_pipe'], 2)) if latency_row and latency_row['min_pipe'] is not None else None,
            'max': float(round(latency_row['max_pipe'], 2)) if latency_row and latency_row['max_pipe'] is not None else None,
            'mean': float(round(latency_row['avg_pipe'], 2)) if latency_row and latency_row['avg_pipe'] is not None else None,
        }
    }

    # 3. Model versions used
    model_rows = session.execute(
        text("""SELECT model_version, count(*) as count
                FROM predictions
                WHERE tenant_id = :t
                GROUP BY model_version"""),
        {'t': tenant_id}
    ).mappings().all()
    models_used = {r['model_version']: r['count'] for r in model_rows}

    # 4. Outdated predictions count
    outdated_count = session.execute(
        text("""SELECT count(DISTINCT p.id) as count
                FROM predictions p
                JOIN replay_observations o
                  ON o.tenant_id = p.tenant_id
                 AND o.machine_id = p.machine_id
                 AND o.stream_id = p.stream_id
                WHERE p.tenant_id = :t
                  AND p.status = 'available'
                  AND o.cycle > p.requested_cutoff_cycle"""),
        {'t': tenant_id}
    ).scalar_one()

    return {
        'tenant_id': str(tenant_id),
        'total_predictions': total,
        'available_predictions': available,
        'unavailable_predictions': unavailable,
        'unavailable_reasons': reasons,
        'latency': latencies,
        'models_used': models_used,
        'outdated_predictions_count': outdated_count
    }
