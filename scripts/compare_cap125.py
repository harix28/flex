"""One predeclared FD001 single-row Cap-125 candidate; never promote or overwrite."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost
from xgboost import XGBRegressor
from sklearn.metrics import r2_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sentinel.data import VALUES, read_data, sha256
from sentinel.rul_experiments import ExperimentPredictor, windows, scores, qualifies
from sentinel.train import weights

FEATURES = ['cycle'] + VALUES


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def metrics(y, p, ids):
    result = scores(y, p, ids)
    result['r2'] = float(r2_score(y, p, sample_weight=weights(ids)))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Output already exists; use a new experiment version')
    baseline_dir = ROOT/'runs/rul-improvement-20261027/FD001'
    reference = json.loads((baseline_dir/'results.json').read_text())
    baseline = ExperimentPredictor(baseline_dir, reference['experiment_manifest_sha256'])
    protected = {p: sha256(p) for p in (ROOT/'runs').rglob('*') if p.is_file()}
    if (ROOT/'.env').exists():
        protected[ROOT/'.env'] = sha256(ROOT/'.env')
    source = ROOT/'data/raw'
    for name, digest in reference['source_sha256'].items():
        if sha256(source/name) != digest:
            raise ValueError('Source checksum mismatch: ' + name)
    split = reference['split']
    assert not set(split['train']) & set(split['validation'])
    assert not (set(split['train']) | set(split['validation'])) & set(reference['interval_audit_ids'])
    params = dict(n_estimators=500, max_depth=5, learning_rate=.05,
                  min_child_weight=1, subsample=.8, colsample_bytree=.8,
                  objective='reg:squarederror', eval_metric='rmse', random_state=42,
                  n_jobs=2, early_stopping_rounds=30, tree_method='hist')
    args.out.mkdir(parents=True)
    protocol = {'date': '2026-10-28', 'candidate_count': 1, 'cap': 125,
                'features': FEATURES, 'params': params, 'split': split,
                'source_sha256': reference['source_sha256'],
                'baseline_manifest_sha256': reference['experiment_manifest_sha256'],
                'code_sha256': sha256(Path(__file__)), 'xgboost_version': xgboost.__version__,
                'differences_from_user_code': 'Existing 70/15/reserved engine split replaces 80/20; canonical strict parser; two threads and explicit hist; JSON instead of pickle. Same single-row inputs, all train rows, capped targets and validation early stopping.',
                'evaluation': 'Uncapped targets primary; capped targets secondary. Common dense cycles >=60; same last-cycle test engines. Engine-balanced evaluation. Previously inspected audit/test are reused, not fresh blind evidence.',
                'decision': 'Existing validation gate: lower MAE/RMSE, no worse within20, over20, near miss or near over20. No automatic deployment.'}
    dump(args.out/'protocol.json', protocol)
    frame = read_data(source/'train_FD001.txt')
    target = frame.groupby('engine_id').cycle.transform('max') - frame.cycle
    train = frame.engine_id.isin(split['train'])
    valid = frame.engine_id.isin(split['validation'])
    model = XGBRegressor(**params)
    model.fit(frame.loc[train, FEATURES], target[train].clip(upper=125),
              eval_set=[(frame.loc[valid, FEATURES], target[valid].clip(upper=125))], verbose=False)
    model.save_model(args.out/'model.json')
    frozen = sha256(args.out/'model.json')
    reloaded = XGBRegressor()
    reloaded.load_model(args.out/'model.json')

    def predict(x):
        p = np.clip(model.predict(x), 0, 125)
        assert np.isfinite(p).all()
        np.testing.assert_allclose(p, np.clip(reloaded.predict(x), 0, 125), atol=1e-6)
        return p

    results = {}

    def compare(name, data, mode='dense', truth=None):
        bx, y, ids, cycles = windows(data, 60, baseline.transform, mode)
        if truth is not None:
            y = truth[ids-1]
        rows = data.set_index(['engine_id', 'cycle'], drop=False).loc[list(zip(ids, cycles)), FEATURES]
        candidate_p = predict(rows)
        baseline_p = baseline.model.predict(bx)
        result = {'baseline': metrics(y, baseline_p, ids),
                  'cap125': metrics(y, candidate_p, ids),
                  'capped_target_baseline': metrics(np.minimum(y,125), baseline_p, ids),
                  'capped_target_cap125': metrics(np.minimum(y,125), candidate_p, ids)}
        pd.DataFrame({'engine_id': ids, 'cycle': cycles, 'actual_rul': y,
                      'baseline_rul': baseline_p, 'cap125_rul': candidate_p}).to_csv(args.out/(name+'.csv'), index=False)
        results[name] = result
        print(name, json.dumps(result), flush=True)

    compare('validation_common', frame[valid])
    # Freeze model before reusing previously inspected audit and official benchmark.
    dump(args.out/'selection.json', {'model_sha256': frozen, 'best_iteration': model.best_iteration,
         'validation_gate_passed': qualifies(results['validation_common']['cap125'], results['validation_common']['baseline'])})
    compare('reused_audit_common', frame[frame.engine_id.isin(reference['interval_audit_ids'])])
    test = read_data(source/'test_FD001.txt')
    truth = np.loadtxt(source/'RUL_FD001.txt', ndmin=1)
    assert sorted(test.engine_id.unique()) == list(range(1,len(truth)+1))
    assert np.isfinite(truth).all() and (truth >= 0).all()
    compare('official_test_common', test, 'last', truth)
    last = test.groupby('engine_id', sort=True).tail(1).sort_values('engine_id')
    all_pred = predict(last[FEATURES])
    results['cap125_all_test_engines'] = metrics(truth, all_pred, last.engine_id.to_numpy())
    results['cap125_all_test_capped_labels'] = metrics(np.minimum(truth,125), all_pred, last.engine_id.to_numpy())
    pd.DataFrame({'engine_id':last.engine_id.to_numpy(), 'actual_rul':truth, 'cap125_rul':all_pred}).to_csv(args.out/'all_test_predictions.csv',index=False)
    assert sha256(args.out/'model.json') == frozen
    assert all(sha256(p) == digest for p,digest in protected.items())
    dump(args.out/'results.json', {'protocol': protocol, 'results': results,
         'model_sha256': frozen, 'best_iteration': model.best_iteration,
         'existing_artifacts_unchanged': True, 'deployed': False})
    print('Completed: existing artifacts unchanged; candidate not deployed.', flush=True)


if __name__ == '__main__':
    main()
