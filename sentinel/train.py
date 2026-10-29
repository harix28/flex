"""python -m sentinel.train --data-dir data/raw --subset FD001 --out runs/fd001-v1"""
import argparse
import datetime
import importlib.metadata
import json
from pathlib import Path
import platform
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor
from .data import SUBSETS, read_data, split_engines, sha256
from .features import SCHEMA, feature_names, make_windows


def weights(ids):
    _, inv, counts = np.unique(ids, return_inverse=True, return_counts=True)
    w = 1 / counts[inv]
    return w / w.mean()


def metrics(y, pred, ids):
    pred = np.maximum(0, pred)
    error = pred-y
    w = weights(ids)
    return {"mae_cycles": float(np.mean(np.abs(error))),
            "rmse_cycles": float(np.sqrt(np.mean(error**2))),
            "engine_balanced_mae_cycles": float(np.average(np.abs(error), weights=w)),
            "engine_balanced_rmse_cycles": float(np.sqrt(np.average(error**2, weights=w))),
            "bias_cycles": float(np.mean(error)), "windows": len(y),
            "engines": len(np.unique(ids))}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--subset", choices=SUBSETS, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--window", type=int, default=30)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    if args.window < 2:
        p.error("window must be >=2")
    if args.out.exists():
        p.error("Output exists. Choose a new version directory; never overwrite a run.")
    train_path = args.data_dir/f"train_{args.subset}.txt"
    df = read_data(train_path)
    split = split_engines(df, args.seed)
    tr = make_windows(df[df.engine_id.isin(split['train'])], args.window)
    va = make_windows(df[df.engine_id.isin(split['validation'])], args.window, 'validation')
    X, y, ids, _ = tr
    V, vy, vids, _ = va
    if X.empty or V.empty:
        raise ValueError("Insufficient history for chosen window")
    w = weights(ids)
    constant = float(np.average(y, weights=w))
    reports = {"constant": metrics(vy, np.full(len(vy), constant), vids)}
    scaler = StandardScaler().fit(X, sample_weight=w)
    ridge = Ridge(alpha=100).fit(scaler.transform(X), y, sample_weight=w)
    reports['ridge'] = metrics(vy, ridge.predict(scaler.transform(V)), vids)
    candidates = {}
    configs = [{"max_depth": 3, "n_estimators": 250}, {"max_depth": 5, "n_estimators": 350}]
    for i, config in enumerate(configs):
        m = XGBRegressor(**config, learning_rate=.04, subsample=.9, colsample_bytree=.9,
                         objective='reg:squarederror', tree_method='hist', n_jobs=2, random_state=args.seed)
        m.fit(X, y, sample_weight=w)
        name = f"xgboost_{i+1}"
        candidates[name] = m
        reports[name] = metrics(vy, m.predict(V), vids)
        print(name, reports[name], flush=True)
    chosen = min(reports, key=lambda n: reports[n]['engine_balanced_rmse_cycles'])
    # Frozen selection happens BEFORE reading official test histories or labels.
    test_path = args.data_dir/f"test_{args.subset}.txt"
    rul_path = args.data_dir/f"RUL_{args.subset}.txt"
    test = read_data(test_path)
    test_ids = sorted(test.engine_id.unique().tolist())
    if test_ids != list(range(1,len(test_ids)+1)):
        raise ValueError("Official label alignment requires consecutive engine IDs")
    truth = np.loadtxt(rul_path, ndmin=1)
    if truth.ndim != 1 or len(truth) != len(test_ids) or not np.isfinite(truth).all() or (truth < 0).any():
        raise ValueError("Invalid official test RUL labels")
    T, _, tids, tcycles = make_windows(test, args.window, 'last')
    if T.empty:
        raise ValueError("No eligible official test windows")
    ty = truth[tids-1]
    def predict(name, frame):
        if name == 'constant':
            return np.full(len(frame), constant)
        if name == 'ridge':
            return ridge.predict(scaler.transform(frame))
        return candidates[name].predict(frame)
    tp = np.maximum(0, predict(chosen,T))
    report = {"created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "subset": args.subset, "window": args.window, "seed": args.seed,
              "target": "uncapped RUL in cycles", "output_clipping": "max(0, prediction)",
              "validation_protocol": "6 fixed evenly spaced causal cutoffs per held-out training engine; not the official-test truncation distribution",
              "selection_metric": "engine_balanced_rmse_cycles", "selected": chosen,
              "validation": reports, "official_test": metrics(ty,tp,tids),
              "official_test_constant_baseline": metrics(ty,predict('constant',T),tids),
              "test_unavailable_engine_ids": sorted(set(test_ids)-set(tids.tolist())),
              "test_protocol": "One final observed trailing window per eligible engine; selection frozen before test read",
              "calibration": "Reserved engine IDs unused; no probability or interval implemented",
              "release_status": "experiment_only_not_approved_for_plant_use",
              "source_sha256": {f.name:sha256(f) for f in (train_path,test_path,rul_path)},
              "split": split, "python": platform.python_version(),
              "dependencies": {n: importlib.metadata.version(n) for n in ['numpy','pandas','scikit-learn','xgboost']}}
    args.out.mkdir(parents=True)
    if chosen.startswith('xgboost'):
        candidates[chosen].save_model(args.out/'model.json')
        model_type = 'xgboost'
    else:
        payload = {"type":chosen,"constant":constant}
        if chosen == 'ridge':
            payload.update(mean=scaler.mean_.tolist(),scale=scaler.scale_.tolist(),
                           coef=ridge.coef_.tolist(),intercept=float(ridge.intercept_))
        (args.out/'model.json').write_text(json.dumps(payload))
        model_type = chosen
    (args.out/'report.json').write_text(json.dumps(report,indent=2))
    import pandas as pd
    pd.DataFrame({'engine_id':tids,'observed_cycle':tcycles,'true_rul_cycles':ty,
                  'predicted_rul_cycles':tp}).to_csv(args.out/'test_predictions.csv',index=False)
    metadata = {'version':args.out.name,'subset':args.subset,'window':args.window,
                'feature_schema':SCHEMA,'feature_names':feature_names(),'model_type':model_type,
                'model_sha256':sha256(args.out/'model.json'),
                'report_sha256':sha256(args.out/'report.json'),
                'status':'experiment_only','probability_available':False,'interval_available':False}
    (args.out/'bundle.json').write_text(json.dumps(metadata,indent=2))
    print(json.dumps({'selected':chosen,'official_test':report['official_test'],
                      'bundle_manifest_sha256':sha256(args.out/'bundle.json')},indent=2))


if __name__ == '__main__':
    main()
