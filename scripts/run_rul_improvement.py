"""Frozen, bounded validation-only search followed by independent interval audit.
python scripts/run_rul_improvement.py --out runs/rul-improvement-20261027
"""
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sentinel.data import read_data, sha256
from sentinel.features import feature_names
from sentinel.train import weights
from sentinel.mlops.verification import verify_model_bundle
from sentinel.rul_experiments import (SCHEMA, MIN_CUTOFF, PointModel, ExperimentPredictor,
    fit_transform, windows, fit_model, scores, qualifies, split_reserved, calibrate, interval_audit)


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def save_predictions(path, y, pred, ids, cycles, calibration=None):
    table=pd.DataFrame({'engine_id':ids,'cutoff_cycle':cycles,'true_rul_cycles':y,'predicted_rul_cycles':pred})
    if calibration and calibration['radius_cycles'] is not None:
        table['lower_cycles']=np.maximum(0,pred-calibration['radius_cycles'])
        table['upper_cycles']=pred+calibration['radius_cycles']
    table.to_csv(path,index=False)


def run_subset(record, directory, protocol):
    subset=record['subset']; directory.mkdir()
    baseline_dir=ROOT/record['run']
    verified=verify_model_bundle(baseline_dir, record['bundle_sha256'])
    original=verified['report']; split=original['split']
    train_path=ROOT/'data/raw'/f'train_{subset}.txt'
    if sha256(train_path)!=original['source_sha256'][train_path.name]:
        raise ValueError('Training source hash mismatch')
    frame=read_data(train_path)
    train=frame[frame.engine_id.isin(split['train'])]
    valid=frame[frame.engine_id.isin(split['validation'])]
    raw=fit_transform(train)
    vx,vy,vi,vc=windows(valid,30,raw)
    baseline=PointModel.load(baseline_dir/'model.json', verified['model_family'])
    baseline_pred=baseline.predict(vx); baseline_scores=scores(vy,baseline_pred,vi)
    candidate_results=[]; winner=None
    transforms={'raw':raw}
    if subset in ('FD002','FD004'):
        transforms['condition_normalized']=fit_transform(train,True)
    for mode, transform in transforms.items():
        for window in protocol['windows']:
            tx,ty,ti,_=windows(train,window,transform,'train')
            x,y,ids,cycles=windows(valid,window,transform)
            assert np.array_equal(y,vy) and np.array_equal(ids,vi) and np.array_equal(cycles,vc)
            for family in protocol['families']:
                key=f'{mode}-w{window}-{family}'
                model=fit_model(tx,ty,ti,family)
                pred=model.predict(x); summary=scores(y,pred,ids)
                accepted=qualifies(summary,baseline_scores)
                candidate_results.append({'name':key,'mode':mode,'window':window,'family':family,
                    'metrics':summary,'passes_development_gate':accepted})
                print(f"{subset} {key}: MAE={summary['mae']:.2f} RMSE={summary['rmse']:.2f} near-miss={summary['near_miss_percent']:.1f}% gate={accepted}",flush=True)
                if accepted and (winner is None or summary['rmse']<winner['metrics']['rmse']):
                    winner={'name':key,'mode':mode,'window':window,'model':model,'transform':transform,
                            'metrics':summary,'validation_prediction':pred}
    if winner is None:
        winner={'name':'retained_baseline','mode':'raw','window':30,'model':baseline,'transform':raw,
                'metrics':baseline_scores,'validation_prediction':baseline_pred}
    # Freeze identity/parameters before opening reserved calibration or official test partitions.
    winner['model'].save(directory/'model.json')
    dump(directory/'transform.json',winner['transform'])
    selection={'subset':subset,'name':winner['name'],'window':winner['window'],
        'mode':winner['mode'],'family':winner['model'].family,'metrics':winner['metrics'],
        'baseline_metrics':baseline_scores,'candidates':candidate_results,
        'model_sha256':sha256(directory/'model.json'),'transform_sha256':sha256(directory/'transform.json'),
        'test_or_calibration_used_for_selection':False}
    dump(directory/'selection.json',selection)
    frozen=sha256(directory/'selection.json')
    save_predictions(directory/'validation_predictions.csv',vy,winner['validation_prediction'],vi,vc)
    constant=np.full(len(vy),np.average(ty,weights=weights(ti)))
    # ty/ti always come from the final fixed training-window candidate, recorded explicitly.
    constant_metrics=scores(vy,constant,vi)
    calibration_ids,audit_ids=split_reserved(split['calibration_reserved'])
    assert not set(calibration_ids)&set(audit_ids)
    assert not (set(calibration_ids)|set(audit_ids)) & (set(split['train'])|set(split['validation']))
    cal_frame=frame[frame.engine_id.isin(calibration_ids)]
    cx,cy,ci,cc=windows(cal_frame,winner['window'],winner['transform'])
    cp=winner['model'].predict(cx)
    calibration=calibrate(cy,cp,ci,protocol['alpha'])
    if set(calibration['calibration_engine_ids']) != set(calibration_ids):
        raise ValueError('Some calibration engines lack eligible history')
    dump(directory/'interval.json',calibration)
    ax,ay,ai,ac=windows(frame[frame.engine_id.isin(audit_ids)],winner['window'],winner['transform'])
    ap=winner['model'].predict(ax)
    audit=interval_audit(ay,ap,ai,calibration)
    save_predictions(directory/'audit_predictions.csv',ay,ap,ai,ac,calibration)
    # No adjustment to winner, alpha or intervals is allowed after the audit.
    test_path=ROOT/'data/raw'/f'test_{subset}.txt'; label_path=ROOT/'data/raw'/f'RUL_{subset}.txt'
    for path in (test_path,label_path):
        if sha256(path)!=original['source_sha256'][path.name]:
            raise ValueError('Official benchmark source hash mismatch')
    test=read_data(test_path); truth=np.loadtxt(label_path,ndmin=1)
    test_ids=sorted(map(int,test.engine_id.unique()))
    if test_ids!=list(range(1,len(truth)+1)) or not np.isfinite(truth).all() or (truth<0).any():
        raise ValueError('Invalid official test label alignment')
    ex,_,ei,ec=windows(test,winner['window'],winner['transform'],'last',min_cutoff=MIN_CUTOFF)
    ey=truth[ei-1]; ep=winner['model'].predict(ex)
    bx,_,bi,bc=windows(test,30,raw,'last',min_cutoff=MIN_CUTOFF)
    assert np.array_equal(ei,bi) and np.array_equal(ec,bc)
    test_scores=scores(ey,ep,ei); test_baseline=scores(ey,baseline.predict(bx),bi)
    test_interval=interval_audit(ey,ep,ei,calibration)
    save_predictions(directory/'official_test_common_predictions.csv',ey,ep,ei,ec,calibration)
    fx,_,fi,fc=windows(test,winner['window'],winner['transform'],'last',min_cutoff=winner['window'])
    fy=truth[fi-1]; fp=winner['model'].predict(fx)
    # Point predictions with <60 cycles have no calibrated interval.
    save_predictions(directory/'official_test_point_predictions.csv',fy,fp,fi,fc)
    natural_test=scores(fy,fp,fi)
    manifest={'schema':SCHEMA,'subset':subset,'window':winner['window'],'family':winner['model'].family,
        'features':feature_names(),'status':'offline_experiment_only',
        'sha256':{name:sha256(directory/name) for name in ('model.json','transform.json','interval.json')}}
    dump(directory/'experiment.json',manifest)
    digest=sha256(directory/'experiment.json')
    reloaded=ExperimentPredictor(directory,digest)
    max_parity_error=0.0
    # Verify actual artifact loading on every eligible official test engine, not only in-memory fit.
    for i,engine in enumerate(fi):
        history=test[test.engine_id==engine]
        response=reloaded.predict(subset,history.to_dict('records'))
        max_parity_error=max(max_parity_error,abs(response['rul_cycles']-float(fp[i])))
        assert abs(response['rul_cycles']-float(fp[i]))<1e-4
        if history.cycle.iloc[-1]<MIN_CUTOFF:
            assert response['interval'] is None
        else:
            assert response['interval'] is not None
    assert sha256(directory/'selection.json')==frozen
    result={'subset':subset,'selected':winner['name'],'window':winner['window'],
        'improved_on_validation':winner['name']!='retained_baseline',
        'baseline_validation':baseline_scores,'selected_validation':winner['metrics'],
        'constant_validation_window60':constant_metrics,'candidate_count':len(candidate_results),
        'split':split,'interval_calibration_ids':calibration_ids,'interval_audit_ids':audit_ids,
        'interval':calibration,'independent_audit':audit,'audit_point_metrics':scores(ay,ap,ai),
        'official_test_common':test_scores,'baseline_official_test_common':test_baseline,
        'official_test_interval':test_interval,'official_test_natural_point':natural_test,
        'test_total_engines':len(test_ids),'point_unavailable_engines':sorted(set(test_ids)-set(map(int,fi))),
        'interval_unavailable_engines':sorted(set(test_ids)-set(map(int,ei))),
        'experiment_manifest_sha256':digest,'source_sha256':original['source_sha256'],
        'max_reload_prediction_difference':max_parity_error,'selection_sha256':frozen,
        'model_release':'not_deployed','official_test_is_reused_benchmark':True}
    dump(directory/'results.json',result)
    print(f"DONE {subset}: {winner['name']}; audit engine coverage={audit.get('engine_simultaneous_coverage_percent')}%, width={audit.get('mean_width_cycles'):.1f}",flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists(): parser.error('Output exists; never overwrite an experiment')
    source=json.loads((ROOT/'reports/ALL_SUBSETS_TRAINING_20261027.json').read_text())
    protocol={'date':'2026-10-27','windows':[30,50,60],'families':['ridge','xgboost_1','xgboost_2'],
        'modes':{'FD001':['raw'],'FD002':['raw','condition_normalized'],'FD003':['raw'],'FD004':['raw','condition_normalized']},
        'max_fits':54,'training_cutoffs':'up to 100 evenly spaced per engine, cycle >=60',
        'validation_cutoffs':'every observed cycle >=60, identical across candidates',
        'gate':'MAE and RMSE strictly lower; within20 not lower; overall over20, near-failure miss and near-failure over20 not higher; select lowest eligible RMSE or retain baseline',
        'near_failure':'actual RUL 1..30; diagnostic miss predicted RUL>30',
        'metric_weighting':'equal total weight per engine; near-failure subset reweighted within engines',
        'normalizer':'KMeans6 on training settings only, sensor normalization within learned condition; no fit outside training engines',
        'alpha':.1,'reserved_split':'seed43 shuffle, first max(9,ceil(.6*n)) calibration; rest untouched audit',
        'interval_score':'max absolute residual per calibration engine over all eligible cycles >=60',
        'interval_audit':'all eligible cycles >=60 from disjoint audit engines; no refit after audit',
        'test_policy':'official test read after selection/calibration; descriptive reused benchmark only',
        'code_sha256':{'runner':sha256(__file__),'module':sha256(ROOT/'sentinel/rul_experiments.py')}}
    protected=[]
    for folder in [ROOT/'runs/fd001-v1']+[ROOT/r['run'] for r in source['results']]:
        protected.extend(p for p in folder.iterdir() if p.is_file())
    protected += [p for p in (ROOT/'.env',ROOT/'.runtime/active_release.json') if p.exists()]
    before={p:sha256(p) for p in protected}
    args.out.mkdir(parents=True)
    dump(args.out/'protocol.json',protocol)
    results=[]
    for record in source['results']:
        results.append(run_subset(record,args.out/record['subset'],protocol))
    assert all(sha256(path)==digest for path,digest in before.items())
    dump(args.out/'results.json',{'protocol':protocol,'results':results,'protected_files_unchanged':True})
    print('All subsets completed; existing artifacts and release configuration preserved.',flush=True)


if __name__=='__main__': main()
