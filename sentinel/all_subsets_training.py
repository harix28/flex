"""Offline all-subset RF classification and XGBoost RUL study; never deploys."""
import argparse
import datetime
import importlib.metadata
import json
from pathlib import Path
import platform
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from xgboost import XGBRegressor

from .data import SUBSETS, VALUES, read_data, split_engines, sha256, validate_frame
from .train import metrics as regression_metrics

RAW_FEATURES = ['cycle'] + VALUES
SEED = 42


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False), encoding='utf-8')


def features(frame):
    """97 causal features, one row per cycle. No engine ID or labels in X."""
    df = validate_frame(frame)
    blocks = [df[RAW_FEATURES].astype(float)]
    g = df.groupby('engine_id', sort=False)[VALUES]
    for name, block in [
        ('mean10', g.rolling(10, min_periods=1).mean().reset_index(level=0, drop=True)),
        ('std10', g.rolling(10, min_periods=1).std(ddof=0).reset_index(level=0, drop=True)),
        ('delta5', g.diff(5).fillna(0.0)),
    ]:
        blocks.append(block.add_suffix('__' + name))
    result = pd.concat(blocks, axis=1).astype(np.float32)
    if not np.isfinite(result.to_numpy()).all():
        raise ValueError('Nonfinite features')
    return result


def targets(frame, final_rul=None):
    """Future lifetime is used for labels ONLY, never passed to features()."""
    df = validate_frame(frame)
    ids = sorted(df.engine_id.unique())
    end = df.groupby('engine_id').cycle.transform('max').to_numpy(dtype=float)
    if final_rul is not None:
        truth = np.asarray(final_rul, dtype=float)
        if ids != list(range(1, len(ids) + 1)) or truth.shape != (len(ids),):
            raise ValueError('Invalid official label alignment')
        if not np.isfinite(truth).all() or (truth < 0).any() or (truth != np.floor(truth)).any():
            raise ValueError('Invalid RUL labels')
        end += truth[df.engine_id.to_numpy() - 1]
    cycle = df.cycle.to_numpy()
    # Integer comparisons avoid floating ambiguity at 60% and 80%.
    label = np.where(5 * cycle <= 3 * end, 0, np.where(5 * cycle <= 4 * end, 1, 2))
    return label, end - cycle


def weights(ids):
    _, inv, counts = np.unique(np.asarray(ids), return_inverse=True, return_counts=True)
    w = 1.0 / counts[inv]
    return w / w.mean()


def classification_metrics(y, pred, ids):
    w = weights(ids)
    return {
        'observations': len(y), 'engines': len(np.unique(ids)),
        'row_accuracy': float(accuracy_score(y, pred)),
        'row_macro_f1': float(f1_score(y, pred, labels=[0, 1, 2], average='macro', zero_division=0)),
        'engine_balanced_accuracy': float(accuracy_score(y, pred, sample_weight=w)),
        'engine_balanced_macro_f1': float(f1_score(y, pred, labels=[0, 1, 2], average='macro', sample_weight=w, zero_division=0)),
        'report': classification_report(y, pred, labels=[0, 1, 2], output_dict=True, zero_division=0),
        'engine_balanced_report': classification_report(y, pred, labels=[0, 1, 2], sample_weight=w, output_dict=True, zero_division=0),
        'confusion_matrix': confusion_matrix(y, pred, labels=[0, 1, 2]).tolist(),
    }


def select_features(X, y, ids):
    """Train-only constant/correlation removal and tree-importance top 40."""
    nonconstant = X.columns[X.nunique() > 1].tolist()
    corr = X[nonconstant].corr().abs()
    retained, removed = [], []
    for c in nonconstant:
        if any(corr.loc[c, k] > .995 for k in retained):
            removed.append(c)
        else:
            retained.append(c)
    if not retained:
        raise ValueError('No varying features')
    selector = ExtraTreesClassifier(n_estimators=64, max_depth=12, min_samples_leaf=3,
                                    random_state=SEED, n_jobs=2)
    selector.fit(X[retained], y, sample_weight=weights(ids))
    ranked = sorted(zip(retained, selector.feature_importances_), key=lambda x: (-x[1], x[0]))
    selected = [name for name, _ in ranked[:40]]
    return selected, {'method': 'train-only variance/correlation then ExtraTrees impurity importance top40',
                     'constant_removed': [c for c in X if c not in nonconstant],
                     'correlated_removed': removed, 'ranking': [[n, float(v)] for n, v in ranked],
                     'selected': selected, 'fit_engine_ids': sorted(set(map(str, ids)))}


def save_forest(model, columns, directory):
    """Numeric NPZ + JSON only. No pickle/joblib deserialization required."""
    arrays = {}
    for i, estimator in enumerate(model.estimators_):
        tree = estimator.tree_
        for name, value in [('left', tree.children_left), ('right', tree.children_right),
                            ('feature', tree.feature), ('threshold', tree.threshold),
                            ('value', tree.value[:, 0, :])]:
            arrays[f'{i}_{name}'] = value
    path = directory / 'forest.npz'
    np.savez_compressed(path, **arrays)
    meta = {'schema': 'meridian-offline-forest-v1', 'classes': model.classes_.tolist(),
            'trees': len(model.estimators_), 'features': columns,
            'forest_sha256': sha256(path), 'parameters': model.get_params(),
            'serving_integration': 'offline only; not an application model bundle'}
    write_json(directory / 'forest.json', meta)


def forest_predict(directory, X, expected_manifest_hash):
    """Load our numeric export with an independently supplied manifest hash."""
    if sha256(directory / 'forest.json') != expected_manifest_hash:
        raise ValueError('Manifest hash mismatch')
    meta = json.loads((directory / 'forest.json').read_text())
    if sha256(directory / 'forest.npz') != meta['forest_sha256']:
        raise ValueError('Forest hash mismatch')
    if list(X.columns) != meta['features'] or not np.isfinite(X.to_numpy()).all():
        raise ValueError('Feature contract mismatch')
    a = X.to_numpy(dtype=np.float32)
    proba = np.zeros((len(a), len(meta['classes'])))
    with np.load(directory / 'forest.npz', allow_pickle=False) as bundle:
        for i in range(meta['trees']):
            left, right, feature, threshold, value = [bundle[f'{i}_{n}'] for n in ['left','right','feature','threshold','value']]
            nodes = np.zeros(len(a), dtype=int)
            for _ in range(len(left)):
                active = np.flatnonzero(left[nodes] != -1)
                if not len(active):
                    break
                n = nodes[active]
                nodes[active] = np.where(a[active, feature[n]] <= threshold[n], left[n], right[n])
            else:
                raise ValueError('Cyclic tree')
            v = value[nodes]
            proba += v / v.sum(axis=1, keepdims=True)
    return np.asarray(meta['classes'])[np.argmax(proba, axis=1)]


def audit_eda(df, subset, directory):
    """Development EDA only, using training-partition engines."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    labels, rul = targets(df)
    stats = df[RAW_FEATURES].describe(percentiles=[.01, .25, .5, .75, .99])
    stats.to_csv(directory / f'{subset}_statistics.csv')
    df[VALUES].corr().to_csv(directory / f'{subset}_correlations.csv')
    lengths = df.groupby('engine_id').size()
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.5))
    axes[0].hist(lengths, bins=15, color='#2563eb'); axes[0].set_title('Training engine lifetime'); axes[0].set_xlabel('Cycles')
    axes[1].bar(['Early','Middle','Late'], np.bincount(labels, minlength=3), color=['#087f8c','#e3a008','#c0392b']); axes[1].set_title('Training label balance'); axes[1].set_ylabel('Observations')
    first = df[df.engine_id == df.engine_id.iloc[0]]
    axes[2].plot(first.cycle, first.sensor_11, color='#2563eb'); axes[2].set_title('Example training sensor_11'); axes[2].set_xlabel('Cycle')
    fig.suptitle(subset + ' training-engine EDA'); fig.tight_layout(); fig.savefig(directory / f'{subset}_eda.png', dpi=150); plt.close(fig)
    q = df[VALUES].quantile([.25,.75]); iqr = q.loc[.75] - q.loc[.25]
    return {'rows': len(df), 'engines': int(df.engine_id.nunique()), 'missing': int(df.isna().sum().sum()),
            'duplicate_engine_cycles': int(df.duplicated(['engine_id','cycle']).sum()),
            'lifetime_min': int(lengths.min()), 'lifetime_max': int(lengths.max()),
            'class_counts': np.bincount(labels, minlength=3).tolist(),
            'constant_channels': df[VALUES].columns[df[VALUES].nunique() == 1].tolist(),
            'iqr_outlier_counts_retained': ((df[VALUES] < q.loc[.25]-1.5*iqr) | (df[VALUES] > q.loc[.75]+1.5*iqr)).sum().to_dict(),
            'cleaning': 'strict finite numeric/schema/duplicate/gap checks; sorted by engine/cycle; no imputation or outlier deletion'}


def run(data_dir, out):
    # Require every subset. No silent partial training.
    paths = [data_dir / f'{part}_{sub}.txt' for sub in SUBSETS for part in ['train','test','RUL']]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    out.mkdir(parents=True, exist_ok=False)
    eda = out / 'eda'; eda.mkdir()
    raw_hashes = {p.name: sha256(p) for p in paths}
    protected = {str(p): sha256(p) for p in Path('runs/fd001-v1').glob('*') if p.is_file()}
    config = {'seed': SEED, 'subsets': list(SUBSETS), 'splits': {}, 'data_sha256': raw_hashes,
              'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'label_policy': 'lifetime fraction: class0 <=60%, class1 <=80%, class2 >80%; not physical health',
              'feature_policy': 'raw25 or training-selected top40 of97; trailing mean/std10 and delta5; no scaling',
              'selection': 'highest validation engine-balanced macro F1; RF 300 trees depth15 max_samples0.4, seed42',
              'search_budget': '2 RF candidates per scope; 5 scopes. 2 XGB candidates per subset; 4 subsets',
              'test_policy': 'load official test histories/labels only after all model selections frozen; benchmark previously inspected',
              'versions': {n: importlib.metadata.version(n) for n in ['numpy','pandas','scikit-learn','xgboost']},
              'python': platform.python_version(), 'protected_existing_artifacts': protected}
    train, validation, cleaning = {}, {}, {}
    for sub in SUBSETS:
        df = read_data(data_dir / f'train_{sub}.txt')
        split = split_engines(df, SEED); config['splits'][sub] = split
        tr = df[df.engine_id.isin(split['train'])].copy().reset_index(drop=True)
        va = df[df.engine_id.isin(split['validation'])].copy().reset_index(drop=True)
        train[sub], validation[sub] = tr, va
        cleaning[sub] = {'source_training_rows': len(df), 'source_training_engines': int(df.engine_id.nunique()), 'rows_removed':0}
    write_json(out / 'config.json', config)
    # Freeze configuration before fitting or feature-selection.
    for sub, tr in train.items():
        cleaning[sub]['training_eda'] = audit_eda(tr, sub, eda)
    write_json(out / 'cleaning_eda.json', cleaning)
    def prepare(frames):
        blocks, ys, rs, ids, subsets, cycles = [], [], [], [], [], []
        for sub, df in frames.items():
            y,r=targets(df); blocks.append(features(df)); ys.extend(y);rs.extend(r)
            ids.extend([f'{sub}:{i}' for i in df.engine_id]); subsets.extend([sub]*len(df)); cycles.extend(df.cycle)
        return pd.concat(blocks,ignore_index=True), np.asarray(ys), np.asarray(rs), np.asarray(ids), np.asarray(subsets), np.asarray(cycles)
    fitted, results = {}, {}
    for scope in list(SUBSETS)+['COMBINED']:
        print('TRAIN', scope, flush=True); start=time.monotonic()
        a = prepare(train if scope=='COMBINED' else {scope:train[scope]})
        b = prepare(validation if scope=='COMBINED' else {scope:validation[scope]})
        X,y,r,ids,_,_=a; V,vy,vr,vids,_,_=b
        selected,selection=select_features(X,y,ids)
        directory=out/scope;directory.mkdir();write_json(directory/'feature_selection.json',selection)
        candidates, val = {}, {}
        for name,cols in [('raw25',RAW_FEATURES),('engineered_selected',selected)]:
            model=RandomForestClassifier(n_estimators=300,max_samples=.4,max_depth=15,random_state=SEED,n_jobs=2)
            model.fit(X[cols],y,sample_weight=weights(ids))
            val[name]=classification_metrics(vy,model.predict(V[cols]),vids)
            candidates[name]=(model,cols)
        chosen=max(val,key=lambda n:val[n]['engine_balanced_macro_f1'])
        model,cols=candidates[chosen]
        save_forest(model,cols,directory)
        sample=V[cols].iloc[np.linspace(0,len(V)-1,min(256,len(V))).astype(int)]
        np.testing.assert_array_equal(model.predict(sample),forest_predict(directory,sample,sha256(directory/'forest.json')))
        selected_reg=None; reg_validation={}
        if scope!='COMBINED':
            regressors={}
            for name,rc in [('raw25',RAW_FEATURES),('engineered_selected',selected)]:
                reg=XGBRegressor(n_estimators=300,max_depth=5,learning_rate=.05,subsample=.8,colsample_bytree=.8,
                                 objective='reg:squarederror',tree_method='hist',random_state=SEED,n_jobs=2)
                reg.fit(X[rc],r,sample_weight=weights(ids))
                reg_validation[name]=regression_metrics(vr,reg.predict(V[rc]),vids)
                regressors[name]=(reg,rc)
            selected_reg=min(reg_validation,key=lambda n:reg_validation[n]['engine_balanced_rmse_cycles'])
            reg,rc=regressors[selected_reg];reg.save_model(directory/'rul_model.json')
            write_json(directory/'rul_features.json',{'features':rc,'selection':selected_reg,'target':'uncapped RUL cycles','note':'selected feature ranking comes from lifetime classification target'})
            reload=XGBRegressor();reload.load_model(directory/'rul_model.json')
            np.testing.assert_allclose(reg.predict(V[rc].iloc[:100]),reload.predict(V[rc].iloc[:100]))
        else:
            reg,rc=None,None
        fitted[scope]=(model,cols,reg,rc)
        results[scope]={'selected_classifier':chosen,'validation':val,'rul_validation':reg_validation,'selected_rul':selected_reg,'fit_seconds':time.monotonic()-start,'forest_reload_parity_rows':len(sample)}
        write_json(directory/'validation.json',results[scope])
        print('FROZEN',scope,chosen,round(val[chosen]['engine_balanced_macro_f1'],4),flush=True)
    write_json(out/'frozen_selections.json',results)
    # Official test files enter only after ALL fitting and selections finish.
    tests={};test_audit={}
    for sub in SUBSETS:
        df=read_data(data_dir/f'test_{sub}.txt');truth=np.loadtxt(data_dir/f'RUL_{sub}.txt',ndmin=1)
        y,r=targets(df,truth);tests[sub]=(features(df),y,r,np.asarray([f'{sub}:{i}' for i in df.engine_id]),df.cycle.to_numpy(),df.groupby('engine_id').tail(1).index.to_numpy())
        test_audit[sub]={'rows':len(df),'engines':int(df.engine_id.nunique()),'rows_removed':0,'all_rows_validated':True}
    for scope,(model,cols,reg,rc) in fitted.items():
        per_sub={}
        all_y=[];all_p=[];all_ids=[]
        for sub in (SUBSETS if scope=='COMBINED' else [scope]):
            X,y,r,ids,cycles,last=tests[sub];pred=model.predict(X[cols]);proba=model.predict_proba(X[cols])
            metrics=classification_metrics(y,pred,ids);metrics['final_cycle']=classification_metrics(y[last],pred[last],ids[last])
            data={'engine':ids,'cycle':cycles,'true_lifetime_stage':y,'predicted_lifetime_stage':pred}
            for i,c in enumerate(model.classes_):data[f'class_{c}_score_uncalibrated']=proba[:,i]
            if reg is not None:
                rp=np.maximum(0,reg.predict(X[rc]));data['true_rul']=r;data['predicted_rul']=rp
                metrics['rul_final_cycle']=regression_metrics(r[last],rp[last],ids[last])
                metrics['rul_all_cycles']=regression_metrics(r,rp,ids)
            pd.DataFrame(data).to_csv(out/scope/f'{sub}_test_predictions.csv',index=False)
            per_sub[sub]=metrics;all_y.extend(y);all_p.extend(pred);all_ids.extend(ids)
        results[scope]['test_by_subset']=per_sub
        results[scope]['test_pooled']=classification_metrics(np.asarray(all_y),np.asarray(all_p),np.asarray(all_ids))
        print('TEST',scope,round(results[scope]['test_pooled']['row_accuracy'],4),flush=True)
    write_json(out/'results.json',results);write_json(out/'test_audit.json',test_audit)
    assert all(sha256(Path(k))==v for k,v in protected.items()),'Existing model changed'
    assert all(sha256(data_dir/k)==v for k,v in raw_hashes.items()),'Raw data changed'
    manifest={str(p.relative_to(out)):sha256(p) for p in out.rglob('*') if p.is_file() and p.name!='manifest.json'}
    write_json(out/'manifest.json',manifest)
    print('COMPLETE',out,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',type=Path,default=Path('data/raw'))
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();run(args.data_dir,args.out)


if __name__=='__main__':
    main()
