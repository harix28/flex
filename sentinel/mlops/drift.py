"""Input drift monitoring against verified training partition reference profile."""
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
import numpy as np
from sqlalchemy import text
from sentinel.data import VALUES, read_data, sha256
from sentinel.features import feature_names, window_features
from sentinel.config import TRUSTED_FD001_SHA256
from sentinel.mlops.verification import verify_model_bundle

DEFAULT_REFERENCE_CACHE = Path(__file__).resolve().parents[2] / '.runtime' / 'drift_reference_fd001-v1.json'
RAW_DATA_DIR = Path(__file__).resolve().parents[2] / 'data' / 'raw'
MODEL_DIR = Path(__file__).resolve().parents[2] / 'runs' / 'fd001-v1'


def build_or_load_reference_profile(
    model_dir: Path | str = MODEL_DIR,
    raw_data_dir: Path | str = RAW_DATA_DIR,
    cache_path: Path = DEFAULT_REFERENCE_CACHE,
    trusted_manifest_sha256: str = TRUSTED_FD001_SHA256
) -> dict:
    """Builds or loads verified reference profile for training partition engines only."""
    verified = verify_model_bundle(model_dir, trusted_manifest_sha256)
    model_dir = Path(model_dir)
    report = verified['report']
    train_ids = set(report.get('split', {}).get('train', []))
    if not train_ids:
        raise ValueError("Training partition engine IDs missing from report")

    train_file = Path(raw_data_dir) / 'train_FD001.txt'
    if not train_file.exists():
        raise ValueError(f"Training dataset file missing: {train_file}")

    actual_train_sha = sha256(train_file)
    expected_train_sha = report.get('source_sha256', {}).get('train_FD001.txt')
    if not expected_train_sha or actual_train_sha.lower() != expected_train_sha.lower():
        raise ValueError("Training data checksum mismatch against model provenance")

    identity = {
        'bundle_digest': verified['bundle_digest'],
        'report_digest': verified['report_digest'],
        'source_sha256': actual_train_sha,
        'train_engine_ids': sorted(train_ids),
        'feature_names': feature_names(),
        'window_size': verified['window_size'],
    }
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding='utf-8'))
            stats = cached['feature_stats']
            if (cached.get('identity') == identity
                    and cached.get('model_version') == verified['model_version']
                    and [item['name'] for item in stats] == feature_names()
                    and all(np.isfinite(item[key]) for item in stats
                            for key in ('mean', 'std', 'min', 'max', 'p50'))
                    and all(item['std'] >= 0 for item in stats)):
                return cached
        except (ValueError, KeyError, TypeError):
            pass

    df = read_data(str(train_file))
    df_train = df[df.engine_id.isin(train_ids)]

    windows = []
    window_size = report.get('window', 30)
    for _, group in df_train.groupby('engine_id'):
        vals = group[VALUES].to_numpy()
        for end in range(window_size, len(vals) + 1):
            windows.append(window_features(vals[end - window_size:end]))

    windows = np.asarray(windows, dtype=np.float64)
    names = feature_names()
    means = np.mean(windows, axis=0)
    stds = np.std(windows, axis=0)

    stats = []
    for idx, name in enumerate(names):
        std_val = float(stds[idx])
        is_const = bool(std_val < 1e-6)
        stats.append({
            'name': name,
            'mean': float(round(means[idx], 5)),
            'std': float(round(std_val, 5)),
            'is_constant': is_const,
            'min': float(round(np.min(windows[:, idx]), 5)),
            'max': float(round(np.max(windows[:, idx]), 5)),
            'p50': float(round(np.percentile(windows[:, idx], 50), 5))
        })

    profile = {
        'model_version': verified['model_version'],
        'identity': identity,
        'reference_provenance': {
            'source_file': 'train_FD001.txt',
            'source_sha256': actual_train_sha,
            'partition': 'training_partition_only',
            'engine_count': len(train_ids),
            'window_count': len(windows),
            'window_size': window_size,
            'feature_count': len(names),
            'constant_features_count': int(sum(1 for s in stats if s['is_constant']))
        },
        'feature_stats': stats,
        'built_at': datetime.now(timezone.utc).isoformat()
    }

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(profile, indent=2), encoding='utf-8')
    return profile


def evaluate_input_drift(
    session,
    tenant_id: UUID,
    model_version: str = 'fd001-v1',
    actor: str = 'operator:monitoring',
    min_samples: int = 5,
    drift_threshold_z: float = 3.0,
    model_dir: Path | str = MODEL_DIR,
    trusted_manifest_sha256: str = TRUSTED_FD001_SHA256,
    cache_path: Path = DEFAULT_REFERENCE_CACHE
) -> dict:
    """Evaluates statistical drift of recent unique inputs against training partition profile."""
    try:
        ref_profile = build_or_load_reference_profile(model_dir=model_dir, cache_path=cache_path,
            trusted_manifest_sha256=trusted_manifest_sha256)
        if ref_profile['model_version'] != model_version:
            raise ValueError('Requested model version does not match verified drift reference')
    except Exception as exc:
        run_id = uuid4()
        err_metrics = {
            'error': str(exc),
            'disclaimer': 'Drift monitoring unavailable because training partition reference could not be verified.'
        }
        session.execute(
            text("""INSERT INTO ml_monitoring_runs (
                id, tenant_id, model_version, run_type, status, sample_count, engine_count, metrics, actor
            ) VALUES (
                :id, :t, :ver, 'drift', 'incompatible_reference', 0, 0, :metrics, :actor
            )"""),
            {'id': run_id, 't': tenant_id, 'ver': model_version, 'metrics': json.dumps(err_metrics), 'actor': actor}
        )
        return {
            'run_id': str(run_id),
            'status': 'incompatible_reference',
            'sample_count': 0,
            'message': str(exc)
        }

    # Query distinct recent predictions for this tenant and model version
    # Deduplicate by input_digest to prevent repeated predictions from inflating samples
    pred_rows = session.execute(
        text("""SELECT DISTINCT ON (input_digest)
                  id, machine_id, stream_id, input_start_cycle, input_end_cycle, input_digest
                FROM predictions
                WHERE tenant_id = :t AND model_version = :ver AND status = 'available'
                  AND input_start_cycle IS NOT NULL AND input_end_cycle IS NOT NULL
                ORDER BY input_digest, created_at DESC"""),
        {'t': tenant_id, 'ver': model_version}
    ).mappings().all()

    unique_inputs_count = len(pred_rows)
    run_id = uuid4()

    if unique_inputs_count < min_samples:
        insufficient_metrics = {
            'status': 'insufficient_data',
            'sample_count': unique_inputs_count,
            'min_samples_threshold': min_samples,
            'message': f"Insufficient unique input windows ({unique_inputs_count}/{min_samples} required) to evaluate statistical drift.",
            'disclaimer': 'Drift requires a minimum sample of unique operating windows to calculate valid distribution shifts.'
        }
        session.execute(
            text("""INSERT INTO ml_monitoring_runs (
                id, tenant_id, model_version, run_type, status, sample_count, engine_count, metrics, actor
            ) VALUES (
                :id, :t, :ver, 'drift', 'insufficient_data', :cnt, 0, :metrics, :actor
            )"""),
            {
                'id': run_id, 't': tenant_id, 'ver': model_version,
                'cnt': unique_inputs_count, 'metrics': json.dumps(insufficient_metrics),
                'actor': actor
            }
        )
        return {
            'run_id': str(run_id),
            'status': 'insufficient_data',
            'sample_count': unique_inputs_count,
            'min_samples_threshold': min_samples,
            'metrics': insufficient_metrics
        }

    # Extract windows from replay_observations for each unique input
    feature_vectors = []
    distinct_machines = set()

    for p in pred_rows:
        distinct_machines.add(p['machine_id'])
        obs_rows = session.execute(
            text("""SELECT cycle, settings, sensors FROM replay_observations
                    WHERE tenant_id = :t AND machine_id = :m AND stream_id = :s
                      AND cycle BETWEEN :start AND :end
                    ORDER BY cycle ASC"""),
            {
                't': tenant_id,
                'm': p['machine_id'],
                's': p['stream_id'],
                'start': p['input_start_cycle'],
                'end': p['input_end_cycle']
            }
        ).mappings().all()

        if len(obs_rows) == 30:
            matrix = np.array([list(r['settings']) + list(r['sensors']) for r in obs_rows], dtype=np.float64)
            feature_vectors.append(window_features(matrix))

    if len(feature_vectors) < min_samples:
        # Some observation windows were partial or missing
        insufficient_metrics = {
            'status': 'insufficient_data',
            'sample_count': len(feature_vectors),
            'min_samples_threshold': min_samples,
            'message': f"Insufficient complete 30-cycle observation windows ({len(feature_vectors)}/{min_samples} required).",
            'disclaimer': 'Drift requires valid, complete trailing feature windows.'
        }
        session.execute(
            text("""INSERT INTO ml_monitoring_runs (
                id, tenant_id, model_version, run_type, status, sample_count, engine_count, metrics, actor
            ) VALUES (
                :id, :t, :ver, 'drift', 'insufficient_data', :cnt, :ecnt, :metrics, :actor
            )"""),
            {
                'id': run_id, 't': tenant_id, 'ver': model_version,
                'cnt': len(feature_vectors), 'ecnt': len(distinct_machines),
                'metrics': json.dumps(insufficient_metrics), 'actor': actor
            }
        )
        return {
            'run_id': str(run_id),
            'status': 'insufficient_data',
            'sample_count': len(feature_vectors),
            'metrics': insufficient_metrics
        }

    curr_matrix = np.asarray(feature_vectors, dtype=np.float64)
    ref_stats = {s['name']: s for s in ref_profile['feature_stats']}
    names = feature_names()

    feature_drift_results = []
    drifted_varying_count = 0
    total_varying_count = 0

    for idx, name in enumerate(names):
        r_stat = ref_stats[name]
        col = curr_matrix[:, idx]
        c_mean = float(np.mean(col))
        c_std = float(np.std(col))

        if r_stat['is_constant']:
            max_dev = float(np.max(np.abs(col - r_stat['mean'])))
            drifted = bool(max_dev > 1e-4)
            feature_drift_results.append({
                'name': name,
                'is_constant': True,
                'ref_mean': r_stat['mean'],
                'curr_mean': round(c_mean, 5),
                'max_deviation': round(max_dev, 5),
                'statistic_name': 'max_abs_deviation',
                'statistic_value': round(max_dev, 5),
                'drifted': drifted
            })
        else:
            total_varying_count += 1
            z_score = float(abs(c_mean - r_stat['mean']) / (r_stat['std'] if r_stat['std'] > 1e-8 else 1.0))
            drifted = bool(z_score >= drift_threshold_z)
            if drifted:
                drifted_varying_count += 1
            feature_drift_results.append({
                'name': name,
                'is_constant': False,
                'ref_mean': r_stat['mean'],
                'ref_std': r_stat['std'],
                'curr_mean': round(c_mean, 5),
                'curr_std': round(c_std, 5),
                'statistic_name': 'z_score',
                'statistic_value': round(z_score, 3),
                'threshold': drift_threshold_z,
                'drifted': drifted
            })

    # Overall determination: drift flagged if >= 10% of varying features exceed threshold
    drift_rate = (drifted_varying_count / total_varying_count) if total_varying_count > 0 else 0.0
    drift_detected = bool(drift_rate >= 0.10)

    top_drifted = sorted(
        [f for f in feature_drift_results if f['drifted']],
        key=lambda x: x['statistic_value'],
        reverse=True
    )[:10]

    run_metrics = {
        'status': 'available',
        'drift_detected': drift_detected,
        'drift_rate': round(drift_rate, 4),
        'drifted_varying_count': drifted_varying_count,
        'total_varying_count': total_varying_count,
        'drift_threshold_z': drift_threshold_z,
        'sample_count': len(feature_vectors),
        'engine_count': len(distinct_machines),
        'reference_provenance': ref_profile['reference_provenance'],
        'top_drifted_features': top_drifted,
        'disclaimer': 'Drift indicates a statistical shift in sensor input distributions relative to training data. It is NOT proof that predictions are inaccurate or that a component has failed.'
    }

    session.execute(
        text("""INSERT INTO ml_monitoring_runs (
            id, tenant_id, model_version, run_type, status, sample_count, engine_count, metrics, actor
        ) VALUES (
            :id, :t, :ver, 'drift', 'available', :cnt, :ecnt, :metrics, :actor
        )"""),
        {
            'id': run_id, 't': tenant_id, 'ver': model_version,
            'cnt': len(feature_vectors), 'ecnt': len(distinct_machines),
            'metrics': json.dumps(run_metrics), 'actor': actor
        }
    )

    # Emit audit event
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
                'run_type': 'drift',
                'status': 'available',
                'sample_count': len(feature_vectors),
                'drift_detected': drift_detected,
                'actor': actor
            })
        }
    )

    return {
        'run_id': str(run_id),
        'status': 'available',
        'sample_count': len(feature_vectors),
        'engine_count': len(distinct_machines),
        'metrics': run_metrics
    }
