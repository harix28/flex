"""Causal feature, engine-group uncertainty, and artifact safeguards."""
import json
import numpy as np
import pandas as pd
import pytest
from sentinel.data import COLUMNS, VALUES, sha256
from sentinel.features import feature_names
from sentinel.rul_experiments import (SCHEMA, windows, fit_transform, transform_frame, calibrate,
    interval_audit, split_reserved, scores, qualifies, ExperimentPredictor)


def frame(engines=2, cycles=80):
    return pd.DataFrame([[engine,cycle]+[float(cycle+j+engine) for j in range(24)]
        for engine in range(1,engines+1) for cycle in range(1,cycles+1)],columns=COLUMNS)


def test_dense_common_cutoffs_and_future_independence():
    data=frame(); transform=fit_transform(data)
    a=windows(data,30,transform); b=windows(data,60,transform)
    assert len(a[0])==42
    for index in (1,2,3): np.testing.assert_array_equal(a[index],b[index])
    modified=data.copy(); modified.loc[modified.cycle>60,VALUES]=99999
    changed=windows(modified,30,transform)
    np.testing.assert_allclose(a[0][0],changed[0][0])
    np.testing.assert_allclose(a[0][21],changed[0][21])
    assert a[1][0]==20 and a[3][0]==60


def test_normalizer_fitted_on_training_engines_and_serializable():
    data=frame(); data.loc[:, 'setting_1']=np.arange(len(data))%6*100.
    transform=fit_transform(data[data.engine_id==1],True)
    assert transform['training_engine_ids']==[1]
    restored=json.loads(json.dumps(transform))
    before=transform_frame(data[data.engine_id==2],restored)
    first=before.iloc[0][VALUES].to_numpy(float)
    data.loc[(data.engine_id==2)&(data.cycle>1),VALUES]=99999
    after=transform_frame(data[data.engine_id==2],restored)
    np.testing.assert_allclose(first,after.iloc[0][VALUES].to_numpy(float))
    assert np.isfinite(after[VALUES].to_numpy()).all()


def test_calibration_counts_engines_not_correlated_windows():
    y=np.zeros(100); predictions=np.ones(100); ids=np.ones(100,dtype=int)
    result=calibrate(y,predictions,ids)
    assert result['calibration_engine_count']==1
    assert result['radius_cycles'] is None
    assert result['status']=='insufficient_calibration_engines'


def test_correct_group_quantile_and_disjoint_audit_coverage():
    ids=np.repeat(np.arange(1,10),2)
    pred=np.repeat(np.arange(1,10,dtype=float),2)
    result=calibrate(np.zeros(18),pred,ids)
    assert result['order_statistic_rank']==9 and result['radius_cycles']==9
    audit=interval_audit(np.array([1.,1.,1.,1.]),np.array([1.,10.,1.,11.]),np.array([20,20,21,21]),result)
    assert audit['engine_simultaneous_coverage_percent']==50
    assert audit['engine_balanced_window_coverage_percent']==75


def test_reserved_partition_is_reproducible_and_disjoint():
    a,b=split_reserved(list(range(1,16)))
    assert len(a)==9 and len(b)==6 and not set(a)&set(b)
    assert set(a)|set(b)==set(range(1,16))
    assert (a,b)==split_reserved(list(range(1,16)))


def test_selection_rejects_improvement_that_worsens_near_failure():
    baseline=scores(np.array([10.,20.,100.]),np.array([15.,25.,150.]),np.array([1,1,1]))
    candidate={**baseline,'mae':baseline['mae']-1,'rmse':baseline['rmse']-1,'near_miss_percent':100.}
    assert not qualifies(candidate,baseline)
    candidate['near_miss_percent']=baseline['near_miss_percent']
    assert qualifies(candidate,baseline)


def test_offline_loader_verifies_artifacts_and_interval_history(tmp_path):
    files={'model.json':{'constant':20.},'transform.json':{'mode':'raw'},
           'interval.json':{'radius_cycles':12.,'nominal_coverage':.9}}
    for name,value in files.items(): (tmp_path/name).write_text(json.dumps(value))
    manifest={'schema':SCHEMA,'subset':'FD001','family':'constant','features':feature_names(),
              'window':30,'sha256':{name:sha256(tmp_path/name) for name in files}}
    (tmp_path/'experiment.json').write_text(json.dumps(manifest))
    digest=sha256(tmp_path/'experiment.json')
    model=ExperimentPredictor(tmp_path,digest)
    data=frame(1)
    short=model.predict('FD001',data[data.cycle<=30].to_dict('records'))
    assert short['interval'] is None and short['rul_cycles']==20
    full=model.predict('FD001',data.to_dict('records'))
    assert full['interval']['lower_cycles']==8 and full['interval']['upper_cycles']==32
    assert full['failure_probability'] is None
    assert model.predict('FD002',data.to_dict('records'))['reason']=='incompatible_subset'
    (tmp_path/'interval.json').write_text('{}')
    with pytest.raises(ValueError,match='artifact checksum'):
        ExperimentPredictor(tmp_path,digest)


def test_nonfinite_calibration_is_rejected():
    with pytest.raises(ValueError): calibrate(np.zeros(9),np.array([np.nan]*9),np.arange(9))
