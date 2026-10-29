"""Analyze verified RUL bundles without fitting or changing serving configuration.

Run: python scripts/analyze_rul_errors.py --out reports/rul-error-analysis-20261027
Validation findings inform future experiments; official-test tables are descriptive only.
"""
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sentinel.config import TRUSTED_FD001_SHA256
from sentinel.data import read_data, sha256
from sentinel.features import make_windows
from sentinel.inference import Predictor
from sentinel.mlops.verification import verify_model_bundle

BANDS = ['failure_endpoint_0', 'near_failure_1_30', 'remaining_31_60', 'remaining_61_120', 'remaining_over_120']


def band(value):
    if value == 0:
        return BANDS[0]
    return BANDS[1] if value <= 30 else BANDS[2] if value <= 60 else BANDS[3] if value <= 120 else BANDS[4]


def summarize(frame):
    if frame.empty:
        return {'windows': 0, 'engines': 0, 'status': 'no_samples'}
    error = frame.error_cycles.to_numpy()
    absolute = np.abs(error)
    near = frame.true_rul_cycles <= 30
    misses = near & (frame.predicted_rul_cycles > 30)
    return {
        'status': 'available', 'windows': len(frame), 'engines': int(frame.engine_id.nunique()),
        'mae_cycles': float(absolute.mean()), 'rmse_cycles': float(np.sqrt(np.mean(error**2))),
        'bias_cycles': float(error.mean()), 'p90_absolute_error_cycles': float(np.quantile(absolute, .9)),
        'max_absolute_error_cycles': float(absolute.max()),
        'within_10_count': int((absolute <= 10).sum()), 'within_20_count': int((absolute <= 20).sum()),
        'within_10_percent': float((absolute <= 10).mean()*100),
        'within_20_percent': float((absolute <= 20).mean()*100),
        'overestimated_count': int((error > 0).sum()),
        'overestimated_by_more_than_20_count': int((error > 20).sum()),
        'overestimated_by_more_than_20_percent': float((error > 20).mean()*100),
        'near_failure_windows': int(near.sum()), 'near_failure_missed_at_30_count': int(misses.sum()),
        'near_failure_missed_at_30_percent': float(misses.sum()/near.sum()*100) if near.any() else None,
    }


def analyze_run(folder, trusted_digest):
    verified = verify_model_bundle(folder, trusted_digest)
    report = verified['report']
    subset = verified['target_subset']
    model = Predictor(folder, trusted_digest)
    split = report['split']
    groups = [set(split[name]) for name in ('train', 'validation', 'calibration_reserved')]
    assert all(not groups[i] & groups[j] for i in range(3) for j in range(i+1, 3))
    for name, digest in report['source_sha256'].items():
        if sha256(ROOT/'data/raw'/name) != digest:
            raise ValueError(f'{subset}: source checksum mismatch: {name}')
    training = read_data(ROOT/'data/raw'/f'train_{subset}.txt')
    validation = training[training.engine_id.isin(split['validation'])]
    _, targets, ids, cutoffs = make_windows(validation, report['window'], 'validation')
    histories = {engine: frame for engine, frame in validation.groupby('engine_id')}
    rows = []
    for engine, cutoff, target in zip(ids, cutoffs, targets):
        history = histories[engine]
        # Only the trailing causal window is passed to inference. Labels stay external.
        records = history[history.cycle <= cutoff].tail(report['window']).to_dict('records')
        pred = model.predict(subset, records)
        assert pred['status'] == 'available'
        rows.append({'run': folder.name, 'subset': subset, 'partition': 'validation',
                     'engine_id': int(engine), 'cutoff_cycle': int(cutoff),
                     'true_rul_cycles': float(target), 'predicted_rul_cycles': pred['rul_cycles']})
    test = read_data(ROOT/'data/raw'/f'test_{subset}.txt')
    labels = np.loadtxt(ROOT/'data/raw'/f'RUL_{subset}.txt', ndmin=1)
    stored = pd.read_csv(folder/'test_predictions.csv').set_index('engine_id')
    unavailable = []
    for engine, history in test.groupby('engine_id'):
        pred = model.predict(subset, history.tail(report['window']).to_dict('records'))
        if len(history) < report['window']:
            assert pred['reason'] == 'insufficient_history'
            unavailable.append(int(engine))
            continue
        assert pred['status'] == 'available'
        assert abs(pred['rul_cycles'] - stored.loc[engine, 'predicted_rul_cycles']) < 1e-4
        rows.append({'run': folder.name, 'subset': subset, 'partition': 'official_test',
                     'engine_id': int(engine), 'cutoff_cycle': int(history.cycle.iloc[-1]),
                     'true_rul_cycles': float(labels[engine-1]), 'predicted_rul_cycles': pred['rul_cycles']})
    assert unavailable == report['test_unavailable_engine_ids']
    frame = pd.DataFrame(rows)
    frame['error_cycles'] = frame.predicted_rul_cycles - frame.true_rul_cycles
    frame['absolute_error_cycles'] = frame.error_cycles.abs()
    frame['rul_band'] = frame.true_rul_cycles.map(band)
    frame['within_10_cycles'] = frame.absolute_error_cycles <= 10
    frame['within_20_cycles'] = frame.absolute_error_cycles <= 20
    frame['overestimated_by_more_than_20'] = frame.error_cycles > 20
    info = {'run': folder.name, 'subset': subset, 'model_family': verified['model_family'],
            'bundle_sha256': trusted_digest, 'selected': report['selected'],
            'official_test_unavailable_engine_ids': unavailable, 'partitions': {}}
    for partition in ('validation', 'official_test'):
        group = frame[frame.partition == partition]
        result = summarize(group)
        # Existing reports use these exact cutoffs; detect accidental protocol drift.
        original = report['validation'][report['selected']] if partition == 'validation' else report['official_test']
        for key in ('mae_cycles', 'rmse_cycles', 'bias_cycles'):
            assert abs(result[key] - original[key]) < 1e-4, (folder.name, partition, key)
        result['bands'] = {name: summarize(group[group.rul_band == name]) for name in BANDS}
        result['worst_overestimates'] = group.sort_values('error_cycles', ascending=False).head(10).to_dict('records')
        result['worst_underestimates'] = group.sort_values('error_cycles').head(10).to_dict('records')
        info['partitions'][partition] = result
    return frame, info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Output exists; choose a new analysis directory')
    manifest = json.loads((ROOT/'reports/ALL_SUBSETS_TRAINING_20261027.json').read_text())
    runs = [(ROOT/'runs/fd001-v1', TRUSTED_FD001_SHA256)]
    runs += [(ROOT/record['run'], record['bundle_sha256']) for record in manifest['results']]
    protected = [p for folder,_ in runs for p in folder.iterdir() if p.is_file()]
    protected += [p for p in (ROOT/'.runtime/active_release.json', ROOT/'.env') if p.exists()]
    before = {p: sha256(p) for p in protected}
    frames, models = [], []
    for folder, digest in runs:
        frame, info = analyze_run(folder, digest)
        frames.append(frame); models.append(info)
        print(f"Verified {folder.name}: {len(frame)} predictions, matching recorded metrics", flush=True)
    combined = pd.concat(frames, ignore_index=True)
    engine_rows = []
    for (run, subset, partition, engine), group in combined.groupby(['run', 'subset', 'partition', 'engine_id']):
        engine_rows.append({'run': run, 'subset': subset, 'partition': partition,
                            'engine_id': int(engine), **summarize(group)})
    args.out.mkdir(parents=True)
    combined.to_csv(args.out/'cutoff_errors.csv', index=False)
    pd.DataFrame(engine_rows).to_csv(args.out/'engine_errors.csv', index=False)
    payload = {'date': '2026-10-27', 'models': models, 'script_sha256': sha256(__file__),
               'validation_used_for_recommendations': True, 'test_used_for_selection': False,
               'thresholds_cycles': [10,20,30,60,120], 'recomputed_predictions': len(combined)}
    (args.out/'summary.json').write_text(json.dumps(payload, indent=2)+'\n', encoding='utf-8')
    lines = ['# RUL engine-wise error analysis', '', 'Date: 2026-10-27', '',
      'No training, tuning or deployment was performed. Current FD001 and four offline candidates were reloaded with trusted manifest checks. Validation engine IDs were kept disjoint from training and reserved calibration. Official test results are descriptive only; do not use them to select the next experiment.', '',
      'Error = predicted RUL minus actual RUL. Positive means optimistic remaining-life estimation. All errors are cycles. ±10/±20 percentages are tolerance coverage, not classification accuracy. A 30-cycle diagnostic cutoff is illustrative, not an approved maintenance rule or calibrated failure probability.', '',
      '## Validation results — use these to plan experiments', '',
      '| Run | Windows / engines | MAE | RMSE | Bias | Within ±20 | Over by >20 | Missed actual RUL ≤30 |',
      '|---|---|---|---|---|---|---|---|']
    for model in models:
        m = model['partitions']['validation']
        lines.append(f"| {model['run']} | {m['windows']} / {m['engines']} | {m['mae_cycles']:.2f} | {m['rmse_cycles']:.2f} | {m['bias_cycles']:+.2f} | {m['within_20_percent']:.1f}% | {m['overestimated_by_more_than_20_percent']:.1f}% | {m['near_failure_missed_at_30_count']} / {m['near_failure_windows']} |")
    for model in models:
        lines += ['', f"### {model['run']} — validation life-stage breakdown", '',
          '| Actual RUL band | Windows / engines | MAE | Bias | Within ±20 | Over by >20 |',
          '|---|---|---|---|---|---|']
        for name, m in model['partitions']['validation']['bands'].items():
            if m['windows']:
                lines.append(f"| {name} | {m['windows']} / {m['engines']} | {m['mae_cycles']:.2f} | {m['bias_cycles']:+.2f} | {m['within_20_percent']:.1f}% | {m['overestimated_by_more_than_20_percent']:.1f}% |")
            else:
                lines.append(f'| {name} | 0 / 0 | Unavailable | Unavailable | Unavailable | Unavailable |')
        lines += ['', 'Largest validation overestimates:', '', '| Engine | Cutoff | Actual RUL | Predicted RUL | Error |', '|---|---|---|---|---|']
        for row in model['partitions']['validation']['worst_overestimates'][:5]:
            lines.append(f"| {row['engine_id']} | {row['cutoff_cycle']} | {row['true_rul_cycles']:.0f} | {row['predicted_rul_cycles']:.2f} | {row['error_cycles']:+.2f} |")
    lines += ['', '## Official test — descriptive benchmark only', '',
      '| Run | Evaluated | Short histories excluded | MAE | Within ±10 | Within ±20 |', '|---|---|---|---|---|---|']
    for model in models:
        m=model['partitions']['official_test']
        lines.append(f"| {model['run']} | {m['engines']} | {len(model['official_test_unavailable_engine_ids'])} | {m['mae_cycles']:.2f} | {m['within_10_percent']:.1f}% | {m['within_20_percent']:.1f}% |")
    lines += ['', '## Evidence and limits', '',
      f"Recomputed {len(combined)} predictions. Aggregate MAE/RMSE/bias match saved reports within 1e-4; official-test predictions match saved engine-level outputs. No padding, future observations or labels enter inference.",
      'Validation uses the existing six evenly spaced cutoffs per engine. Its coverage is sparse, not every operating cycle; multiple cutoffs of the same engine are correlated. Exact failure endpoints (RUL 0) are shown separately from RUL 1–30. High remaining RUL is not a measured health state.',
      'The validation set already influenced model selection, so it is development evidence rather than an independent generalization claim. Reserved calibration engines remain unused. Official test results have been inspected previously and are not a fresh blind benchmark.',
      'Each engine is identified by run, subset, partition and engine ID. The same numeric engine ID in train/validation and test is a different trajectory. Do not pool these identifiers.',
      'The current FD001 model also appears as a baseline: its examples overlap the FD001 candidate and must not be counted as independent samples in pooled statistics.',
      'Files: cutoff_errors.csv contains every evaluated cutoff; engine_errors.csv contains per-engine aggregates; summary.json contains stage summaries, exclusions, and top over/underestimates.', '',
      'Reproduce with a new output directory:', '', '```powershell',
      '.venv/Scripts/python.exe scripts/analyze_rul_errors.py --out reports/rul-error-analysis-20261027', '```']
    (args.out/'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    assert all(sha256(p)==digest for p,digest in before.items()), 'Protected artifact or configuration changed'
    print(f'Analysis saved to {args.out}; protected artifacts/configuration unchanged.', flush=True)


if __name__ == '__main__':
    main()
