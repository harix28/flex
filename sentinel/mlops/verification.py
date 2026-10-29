"""Trust and artifact verification for model bundles."""
import json
from pathlib import Path
from xgboost import XGBRegressor
from sentinel.data import SUBSETS, sha256
from sentinel.features import SCHEMA, feature_names


class ModelVerificationError(ValueError):
    """Raised when a model bundle is tampered, incompatible, or invalid."""


def verify_model_bundle(model_dir: Path | str, expected_manifest_sha256: str | None = None) -> dict:
    """Rigorous verification of an offline model bundle and its artifacts.
    
    Validates manifest structure, artifact hashes, feature schema compatibility,
    training provenance, and safe model loading without unconstrained pickle.
    """
    root = Path(model_dir)
    if not root.is_dir():
        raise ModelVerificationError(f"Model directory does not exist or is not a directory: {root}")

    bundle_path = root / 'bundle.json'
    if not bundle_path.is_file():
        raise ModelVerificationError(f"Missing required manifest bundle.json in {root}")

    actual_bundle_sha = sha256(bundle_path)
    if expected_manifest_sha256 is not None:
        if actual_bundle_sha.lower() != expected_manifest_sha256.lower():
            raise ModelVerificationError(
                f"Bundle manifest hash mismatch: expected {expected_manifest_sha256}, got {actual_bundle_sha}"
            )

    try:
        meta = json.loads(bundle_path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise ModelVerificationError(f"Failed to parse bundle.json as valid JSON: {exc}") from exc

    # Validate required manifest fields
    required_meta_fields = [
        'version', 'subset', 'window', 'feature_schema',
        'feature_names', 'model_type', 'model_sha256', 'report_sha256', 'status'
    ]
    for key in required_meta_fields:
        if key not in meta:
            raise ModelVerificationError(f"bundle.json missing required field: {key}")

    if meta['subset'] not in SUBSETS:
        raise ModelVerificationError(f"Unsupported model subset: {meta['subset']}. Must be one of {SUBSETS}")

    if type(meta['window']) is not int or not (2 <= meta['window'] <= 1000):
        raise ModelVerificationError(f"Invalid window configuration: {meta.get('window')}")

    if meta['feature_schema'] != SCHEMA:
        raise ModelVerificationError(
            f"Incompatible feature schema: expected {SCHEMA}, got {meta.get('feature_schema')}"
        )

    expected_names = feature_names()
    if meta['feature_names'] != expected_names:
        raise ModelVerificationError("Incompatible feature names or ordering in bundle manifest")

    if meta['model_type'] not in ('xgboost', 'ridge', 'constant'):
        raise ModelVerificationError(f"Unsupported model loader type: {meta['model_type']}")

    # Verify model artifact
    model_path = root / 'model.json'
    if not model_path.is_file():
        raise ModelVerificationError(f"Missing required model artifact model.json in {root}")

    actual_model_sha = sha256(model_path)
    if actual_model_sha.lower() != meta['model_sha256'].lower():
        raise ModelVerificationError(
            f"Model artifact SHA256 mismatch: manifest specifies {meta['model_sha256']}, got {actual_model_sha}"
        )

    # Verify report artifact
    report_path = root / 'report.json'
    if not report_path.is_file():
        raise ModelVerificationError(f"Missing required report artifact report.json in {root}")

    actual_report_sha = sha256(report_path)
    if actual_report_sha.lower() != meta['report_sha256'].lower():
        raise ModelVerificationError(
            f"Report artifact SHA256 mismatch: manifest specifies {meta['report_sha256']}, got {actual_report_sha}"
        )

    try:
        report = json.loads(report_path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise ModelVerificationError(f"Failed to parse report.json as valid JSON: {exc}") from exc

    # Validate report provenance fields
    required_report_fields = ['subset', 'window', 'seed', 'target', 'split', 'validation', 'official_test']
    for key in required_report_fields:
        if key not in report:
            raise ModelVerificationError(f"report.json missing required field: {key}")

    split = report.get('split')
    if not isinstance(split, dict) or 'train' not in split or not isinstance(split['train'], list) or not split['train']:
        raise ModelVerificationError("report.json missing valid training partition split.train")

    # Verify model file can be safely loaded
    if meta['model_type'] == 'xgboost':
        try:
            clf = XGBRegressor()
            clf.load_model(str(model_path))
        except Exception as exc:
            raise ModelVerificationError(f"Failed to load XGBoost model from model.json: {exc}") from exc
    elif meta['model_type'] in ('ridge', 'constant'):
        try:
            m_dict = json.loads(model_path.read_text(encoding='utf-8'))
            if meta['model_type'] == 'ridge':
                if not all(k in m_dict for k in ('coef', 'intercept', 'mean', 'scale')):
                    raise ModelVerificationError("Ridge model missing coefficients or normalization vectors")
            elif meta['model_type'] == 'constant':
                if 'constant' not in m_dict:
                    raise ModelVerificationError("Constant model missing 'constant' key")
        except Exception as exc:
            raise ModelVerificationError(f"Failed to load linear/constant model: {exc}") from exc

    training_provenance = {
        'source_sha256': report.get('source_sha256', {}),
        'split': {
            'train_engines_count': len(split['train']),
            'train_engine_ids': split['train'],
            'validation_engines_count': len(split.get('validation', [])),
            'calibration_engines_count': len(split.get('calibration_reserved', []))
        },
        'seed': report.get('seed'),
        'target': report.get('target'),
        'output_clipping': report.get('output_clipping'),
        'selection_metric': report.get('selection_metric'),
        'validation_protocol': report.get('validation_protocol'),
        'python_version': report.get('python'),
        'dependencies': report.get('dependencies', {})
    }

    evaluation_metrics = {
        'validation': report.get('validation', {}),
        'official_test': report.get('official_test', {}),
        'official_test_constant_baseline': report.get('official_test_constant_baseline', {})
    }

    return {
        'model_version': meta['version'],
        'model_family': meta['model_type'],
        'bundle_digest': actual_bundle_sha,
        'model_digest': actual_model_sha,
        'report_digest': actual_report_sha,
        'feature_schema': meta['feature_schema'],
        'feature_count': len(expected_names),
        'window_size': meta['window'],
        'target_subset': meta['subset'],
        'target_machine_type': 'cmapss_engine',
        'target_data_source': 'nasa_replay',
        'training_provenance': training_provenance,
        'evaluation_metrics': evaluation_metrics,
        'review_status': meta.get('status', 'experiment_only'),
        'meta': meta,
        'report': report
    }
