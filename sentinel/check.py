"""Verify saved artifacts/data and generate a real FD001 engine-1 replay."""
import argparse
import json
from pathlib import Path
from .config import ROOT, ConfigurationError, load_settings
from .data import read_data, sha256, SETTINGS, SENSORS
from .inference import Predictor


def verify_and_prepare(settings, data_dir, request_path):
    settings.require_model()
    predictor = Predictor(settings.model_dir, settings.bundle_sha256)
    if predictor.meta['subset'] != 'FD001':
        raise ValueError('This check requires the FD001 model')
    expected = predictor.report['source_sha256']
    for name in ('train_FD001.txt', 'test_FD001.txt', 'RUL_FD001.txt'):
        if sha256(data_dir / name) != expected[name]:
            raise ValueError('FD001 source checksum mismatch; preserve existing data and investigate')
    # Validate both histories, in addition to comparing all three source hashes.
    read_data(data_dir / 'train_FD001.txt')
    test = read_data(data_dir / 'test_FD001.txt')
    history = test[test.engine_id == 1].tail(predictor.meta['window'])
    if len(history) < predictor.meta['window']:
        raise ValueError('Insufficient engine-1 history')
    payload = {'subset': 'FD001', 'engine_id': 1, 'data_mode': 'replay', 'observations': [
        {'cycle': int(row.cycle), 'settings': row[SETTINGS].tolist(), 'sensors': row[SENSORS].tolist()}
        for _, row in history.iterrows()]}
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return {'bundle_verified': True, 'model_report_verified': True, 'fd001_files_verified': 3,
            'engine_id': 1, 'observed_cycle': int(history.cycle.iloc[-1]),
            'observations': len(history), 'data_mode': 'replay'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data/raw')
    parser.add_argument('--request', type=Path, default=ROOT / '.runtime/replay-engine1.json')
    args = parser.parse_args()
    try:
        result = verify_and_prepare(load_settings(), args.data_dir, args.request)
    except (ConfigurationError, ValueError, OSError, KeyError):
        parser.error('Verification failed: check configuration, trusted bundle and FD001 data hashes. No model or data was overwritten.')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
