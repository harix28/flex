import json
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier
from sentinel.data import COLUMNS, sha256, split_engines
from sentinel.all_subsets_training import (
    features, targets, select_features, classification_metrics, save_forest, forest_predict, run,
)


def frame(engines=2, length=20):
    rng=np.random.default_rng(7)
    rows=[]
    for e in range(1,engines+1):
        for c in range(1,length+1):
            rows.append([e,c,*rng.normal(size=24)])
    return pd.DataFrame(rows,columns=COLUMNS)


def test_causality_and_engine_isolation():
    df=frame();alone=df[df.engine_id==1].copy()
    pd.testing.assert_frame_equal(features(alone),features(df).iloc[:20])
    pd.testing.assert_frame_equal(features(alone.iloc[:12]),features(alone).iloc[:12])
    assert len(features(df).columns)==97
    assert not any(x in features(df) for x in ['engine_id','rul','label'])


def test_short_history_and_missing_raw_distinct():
    df=frame(1,1);X=features(df)
    assert np.isfinite(X.to_numpy()).all()
    assert X.filter(like='__delta5').eq(0).all().all()
    assert X.filter(like='__std10').eq(0).all().all()
    df.loc[0,'sensor_01']=np.nan
    with pytest.raises(ValueError):features(df)


@pytest.mark.parametrize('kind',['nan','inf','duplicate','gap','fractional','negative','columns'])
def test_strict_cleaning(kind):
    df=frame()
    if kind=='nan':df.loc[0,'sensor_01']=np.nan
    elif kind=='inf':df.loc[0,'setting_1']=np.inf
    elif kind=='duplicate':df=pd.concat([df,df.iloc[[0]]])
    elif kind=='gap':df=df.drop(index=4)
    elif kind=='fractional':
        df['cycle']=df['cycle'].astype(float)
        df.loc[0,'cycle']=.5
    elif kind=='negative':df.loc[0,'engine_id']=-1
    else:df=df.drop(columns='sensor_01')
    with pytest.raises(ValueError):features(df)


def test_label_boundaries_and_official_cutoffs():
    df=frame(1,10);y,r=targets(df)
    assert y.tolist()==[0]*6+[1]*2+[2]*2
    np.testing.assert_array_equal(r,np.arange(9,-1,-1))
    test=df.iloc[:6];y,r=targets(test,np.array([4]))
    assert y.tolist()==[0]*6
    assert r[-1]==4 and r[0]==9
    for bad in [np.array([1,2]),np.array([np.nan]),np.array([-1]),np.array([.5])]:
        with pytest.raises(ValueError):targets(test,bad)


def test_feature_selection_removes_constants_and_duplicate_columns():
    X=features(frame());X['constant']=1;X['duplicate']=X['sensor_01']
    y=np.tile([0,1,2,1],10);ids=np.repeat([1,2],20)
    selected,audit=select_features(X,y,ids)
    assert 'constant' in audit['constant_removed']
    assert 'duplicate' in audit['correlated_removed']
    assert len(selected)<=40
    assert audit['fit_engine_ids']==['1','2']
    assert set(selected)<=set(X.columns)


def test_metrics_hand_calculation_and_engine_balance():
    m=classification_metrics(np.array([0,1,2,2]),np.array([0,0,2,1]),np.array(['a','a','a','b']))
    assert m['row_accuracy']==.5
    assert m['engine_balanced_accuracy']==pytest.approx(1/3)
    assert m['confusion_matrix']==[[1,0,0],[1,0,0],[0,1,1]]
    assert m['report']['2']['recall']==.5


def test_numeric_forest_roundtrip_and_tamper(tmp_path):
    X=features(frame());y=np.tile([0,1,2,1],10)
    model=RandomForestClassifier(n_estimators=7,max_depth=4,random_state=2).fit(X,y)
    save_forest(model,list(X.columns),tmp_path)
    digest=sha256(tmp_path/'forest.json')
    np.testing.assert_array_equal(forest_predict(tmp_path,X,digest),model.predict(X))
    with pytest.raises(ValueError):forest_predict(tmp_path,X.iloc[:,::-1],digest)
    with pytest.raises(ValueError):forest_predict(tmp_path,X,'0'*64)
    with (tmp_path/'forest.npz').open('ab') as f:f.write(b'tampered')
    with pytest.raises(ValueError):forest_predict(tmp_path,X,digest)


def test_split_preserves_engines_and_missing_files_fail(tmp_path):
    split=split_engines(frame(20,10))
    sets=[set(v) for v in split.values()]
    assert all(not sets[i]&sets[j] for i in range(3) for j in range(i))
    with pytest.raises(FileNotFoundError):run(tmp_path,tmp_path/'output')
    assert not (tmp_path/'output').exists()


def test_output_overwrite_refused_before_loading(tmp_path):
    for sub in ['FD001','FD002','FD003','FD004']:
        for part in ['train','test','RUL']:(tmp_path/f'{part}_{sub}.txt').touch()
    out=tmp_path/'output';out.mkdir();(out/'keep').write_text('unchanged')
    with pytest.raises(FileExistsError):run(tmp_path,out)
    assert (out/'keep').read_text()=='unchanged'
