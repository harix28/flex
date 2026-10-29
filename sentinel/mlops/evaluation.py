"""Offline performance evaluation joining predictions against verified ground-truth outcomes."""
import json
import math
from pathlib import Path
from uuid import UUID, uuid4
from sqlalchemy import text
from sentinel.data import sha256, read_data
from sentinel.config import ROOT, TRUSTED_FD001_SHA256
from sentinel.mlops.verification import verify_model_bundle


class GroundTruthEvaluationError(ValueError):
    """Raised when ground truth evaluation inputs are missing, mismatched, or ambiguous."""


def load_verified_rul_labels(labels_path: Path | str, expected_sha256: str | None = None) -> dict[int, float]:
    """Loads and verifies official NASA C-MAPSS RUL ground truth file.
    
    Returns 1-indexed mapping from engine_id -> final RUL cycles.
    """
    path = Path(labels_path)
    if not path.is_file():
        raise GroundTruthEvaluationError(f"Ground-truth labels file not found: {path}")

    actual_sha = sha256(path)
    if expected_sha256 and actual_sha.lower() != expected_sha256.lower():
        raise GroundTruthEvaluationError(
            f"Ground-truth label SHA256 mismatch: expected {expected_sha256}, got {actual_sha}"
        )

    lines = [line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    labels = {}
    for idx, line in enumerate(lines, start=1):
        try:
            if len(line.split()) != 1:
                raise ValueError('Expected one label')
            value = float(line)
            if not math.isfinite(value) or value < 0 or not value.is_integer():
                raise ValueError('Invalid RUL')
            labels[idx] = value
        except (ValueError, IndexError):
            raise GroundTruthEvaluationError(f"Invalid numeric ground truth format on line {idx}: '{line}'")
    return labels


def evaluate_predictions_performance(
    session,
    tenant_id: UUID,
    labels_path: Path | str,
    subset: str = 'FD001',
    partition: str = 'test',
    model_version: str = 'fd001-v1',
    actor: str = 'operator:evaluation',
    expected_labels_sha256: str | None = None,
    model_dir: Path | str = ROOT / "runs/fd001-v1",
    trusted_manifest_sha256: str = TRUSTED_FD001_SHA256
) -> dict:
    """Joins stored predictions for a tenant against verified reference ground-truth labels.
    
    Strictly keeps labels external to inference. Disallows work-order-derived ground truth.
    Separates official-test final cutoff evaluation from multi-cutoff trajectory evaluation.
    """
    verified = verify_model_bundle(model_dir, trusted_manifest_sha256)
    if partition != 'test' or verified['target_subset'] != subset or verified['model_version'] != model_version:
        raise GroundTruthEvaluationError('Evaluation requires a matching verified test reference and model')
    provenance = verified['training_provenance']['source_sha256']
    expected_label_hash = provenance.get(f'RUL_{subset}.txt')
    expected_source_hash = provenance.get(f'test_{subset}.txt')
    if not expected_label_hash or not expected_source_hash:
        raise GroundTruthEvaluationError('Verified reference hashes are missing')
    if expected_labels_sha256 and expected_labels_sha256 != expected_label_hash:
        raise GroundTruthEvaluationError('Label hash disagrees with verified model provenance')
    labels = load_verified_rul_labels(labels_path, expected_label_hash)
    source_path = Path(labels_path).parent / f'test_{subset}.txt'
    if not source_path.is_file() or sha256(source_path) != expected_source_hash:
        raise GroundTruthEvaluationError('Complete test source is missing or its checksum mismatches')
    reference = read_data(str(source_path))
    endpoints = reference.groupby('engine_id')['cycle'].max().to_dict()
    labels_sha = sha256(labels_path)

    # Query machines and their streams for this tenant matching subset
    machines = session.execute(
        text("""SELECT m.id, m.asset_code, s.id as stream_id, s.engine_id, s.subset, s.partition, s.file_sha256
                FROM machines m
                JOIN replay_streams s ON s.tenant_id = m.tenant_id AND s.machine_id = m.id
                WHERE m.tenant_id = :t AND s.subset = :sub AND s.partition = :part"""),
        {'t': tenant_id, 'sub': subset, 'part': partition}
    ).mappings().all()

    if not machines:
        run_id = uuid4()
        metrics = {
            'status': 'insufficient_data',
            'reason': 'no_matching_machines_in_partition',
            'message': f"No machines found for tenant matching subset '{subset}' and partition '{partition}'"
        }
        session.execute(
            text("""INSERT INTO ml_monitoring_runs (
                id, tenant_id, model_version, run_type, status, sample_count, engine_count, metrics, actor
            ) VALUES (
                :id, :t, :ver, 'evaluation', 'insufficient_data', 0, 0, :metrics, :actor
            )"""),
            {'id': run_id, 't': tenant_id, 'ver': model_version, 'metrics': json.dumps(metrics), 'actor': actor}
        )
        return {
            'run_id': str(run_id),
            'status': 'insufficient_data',
            'reason': 'no_matching_machines_in_partition',
            'sample_count': 0,
            'metrics': metrics
        }

    machine_by_id = {m['id']: m for m in machines}
    for machine in machines:
        if machine['file_sha256'] != expected_source_hash or machine['engine_id'] not in endpoints:
            raise GroundTruthEvaluationError('Registered stream does not match verified evaluation source')

    # Query available predictions for these machines
    pred_rows = session.execute(
        text("""SELECT p.id, p.machine_id, p.stream_id, p.requested_cutoff_cycle, p.rul_cycles, p.input_digest
                FROM predictions p
                WHERE p.tenant_id = :t AND p.model_version = :ver AND p.status = 'available'
                  AND p.machine_id = ANY(:m_ids)
                ORDER BY p.requested_cutoff_cycle ASC"""),
        {'t': tenant_id, 'ver': model_version, 'm_ids': list(machine_by_id.keys())}
    ).mappings().all()

    if not pred_rows:
        run_id = uuid4()
        metrics = {
            'status': 'insufficient_data',
            'reason': 'no_available_predictions',
            'message': f"No available predictions found for model version '{model_version}' in this partition"
        }
        session.execute(
            text("""INSERT INTO ml_monitoring_runs (
                id, tenant_id, model_version, run_type, status, sample_count, engine_count, metrics, actor
            ) VALUES (
                :id, :t, :ver, 'evaluation', 'insufficient_data', 0, 0, :metrics, :actor
            )"""),
            {'id': run_id, 't': tenant_id, 'ver': model_version, 'metrics': json.dumps(metrics), 'actor': actor}
        )
        return {
            'run_id': str(run_id),
            'status': 'insufficient_data',
            'sample_count': 0,
            'metrics': metrics
        }

    # Evaluate errors
    matched_evaluations = []
    distinct_engines = set()
    is_all_final_cutoff = True

    for p in pred_rows:
        m_info = machine_by_id.get(p['machine_id'])
        if not m_info:
            continue

        engine_id = m_info['engine_id']
        cutoff = p['requested_cutoff_cycle']
        t_max = int(endpoints[engine_id])
        if p['stream_id'] != m_info['stream_id'] or cutoff > t_max:
            raise GroundTruthEvaluationError('Prediction is incompatible with verified source trajectory')

        if engine_id not in labels:
            continue

        base_rul = labels[engine_id]
        # Exact RUL-at-cutoff formula:
        # At final cutoff t_max, true RUL is base_rul.
        # At earlier cutoff c < t_max, true RUL is base_rul + (t_max - c).
        true_rul_at_cutoff = float(base_rul + (t_max - cutoff))
        pred_rul = float(p['rul_cycles'])
        error = pred_rul - true_rul_at_cutoff
        abs_error = abs(error)
        squared_error = error ** 2
        is_overestimated = bool(error > 0)

        if cutoff != t_max:
            is_all_final_cutoff = False

        distinct_engines.add(engine_id)
        matched_evaluations.append({
            'prediction_id': str(p['id']),
            'engine_id': engine_id,
            'cutoff_cycle': cutoff,
            'max_observed_cycle': t_max,
            'predicted_rul_cycles': round(pred_rul, 2),
            'true_rul_cycles': round(true_rul_at_cutoff, 2),
            'error_cycles': round(error, 2),
            'abs_error_cycles': round(abs_error, 2),
            'is_overestimated': is_overestimated
        })

    if not matched_evaluations:
        run_id = uuid4()
        metrics = {
            'status': 'insufficient_data',
            'reason': 'no_matched_labels',
            'message': 'No predictions could be matched to verified engine labels'
        }
        session.execute(
            text("""INSERT INTO ml_monitoring_runs (
                id, tenant_id, model_version, run_type, status, sample_count, engine_count, metrics, actor
            ) VALUES (
                :id, :t, :ver, 'evaluation', 'insufficient_data', 0, 0, :metrics, :actor
            )"""),
            {'id': run_id, 't': tenant_id, 'ver': model_version, 'metrics': json.dumps(metrics), 'actor': actor}
        )
        return {
            'run_id': str(run_id),
            'status': 'insufficient_data',
            'sample_count': 0,
            'metrics': metrics
        }

    n_samples = len(matched_evaluations)
    errors = [e['error_cycles'] for e in matched_evaluations]
    abs_errors = [e['abs_error_cycles'] for e in matched_evaluations]
    overestimations = [e['error_cycles'] for e in matched_evaluations if e['is_overestimated']]

    mae = float(sum(abs_errors) / n_samples)
    rmse = float(math.sqrt(sum(e ** 2 for e in errors) / n_samples))
    bias = float(sum(errors) / n_samples)
    overestimate_rate = float(len(overestimations) / n_samples)
    mean_overestimate = float(sum(overestimations) / len(overestimations)) if overestimations else 0.0

    eval_protocol = "official_test_final_cutoff" if is_all_final_cutoff else "multi_cutoff_trajectory"

    metrics = {
        'status': 'available',
        'evaluation_protocol': eval_protocol,
        'mae_cycles': round(mae, 2),
        'rmse_cycles': round(rmse, 2),
        'mean_signed_error_cycles': round(bias, 2),
        'overestimation_frequency': round(overestimate_rate, 4),
        'mean_overestimation_cycles': round(mean_overestimate, 2),
        'sample_count': n_samples,
        'engine_count': len(distinct_engines),
        'labels_provenance': {
            'labels_path': str(labels_path),
            'labels_sha256': labels_sha,
            'subset': subset,
            'partition': partition,
            'total_labels_loaded': len(labels)
        },
        'sample_breakdown': matched_evaluations[:20],
        'disclaimer': 'Accuracy measurement requires verified ground-truth labels. Inspecting official test performance repeatedly does not create a fresh independent benchmark.'
    }

    run_id = uuid4()
    session.execute(
        text("""INSERT INTO ml_monitoring_runs (
            id, tenant_id, model_version, run_type, status, sample_count, engine_count, metrics, actor
        ) VALUES (
            :id, :t, :ver, 'evaluation', 'available', :cnt, :ecnt, :metrics, :actor
        )"""),
        {
            'id': run_id, 't': tenant_id, 'ver': model_version,
            'cnt': n_samples, 'ecnt': len(distinct_engines),
            'metrics': json.dumps(metrics), 'actor': actor
        }
    )

    session.execute(
        text("""INSERT INTO auth_audit_events (
            id, tenant_id, actor_id, action, target_type, target_id, request_id, details
        ) VALUES (
            gen_random_uuid(), :t, NULL, 'model_monitoring_run', 'monitoring_run', :target_id, gen_random_uuid(),
            :details
        )"""),
        {
            't': tenant_id,
            'target_id': run_id,
            'details': json.dumps({
                'run_type': 'evaluation',
                'status': 'available',
                'sample_count': n_samples,
                'mae_cycles': round(mae, 2),
                'rmse_cycles': round(rmse, 2),
                'actor': actor
            })
        }
    )

    return {
        'run_id': str(run_id),
        'status': 'available',
        'sample_count': n_samples,
        'engine_count': len(distinct_engines),
        'metrics': metrics
    }
