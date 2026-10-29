import numpy as np
import pandas as pd
import pytest
from sentinel.data import COLUMNS, VALUES, validate_frame, read_data, split_engines
from sentinel.features import make_windows, window_features


def frame(n=50,engine=1):
    return pd.DataFrame([[engine,i]+[float(i+j) for j in range(24)] for i in range(1,n+1)],columns=COLUMNS)


@pytest.mark.parametrize('kind',['duplicate','gap','nan','fractional','zero'])
def test_invalid_input_rejected(kind):
    df=frame()
    if kind=='duplicate': df.loc[1,'cycle']=1
    if kind=='gap': df=df.drop(10)
    if kind=='nan': df.loc[1,'sensor_01']=np.nan
    if kind=='fractional': df['engine_id']=1.5
    if kind=='zero': df.loc[0,'cycle']=0
    with pytest.raises(ValueError): validate_frame(df)


def test_wrong_column_count(tmp_path):
    path=tmp_path/'bad.txt';path.write_text('1 2 3\n')
    with pytest.raises(ValueError):read_data(path)


def test_engine_partitions_are_disjoint_and_reproducible():
    df=pd.concat([frame(engine=i) for i in range(1,21)])
    a=split_engines(df)
    assert a==split_engines(df)
    sets=[set(v) for v in a.values()]
    assert len(set.union(*sets))==20
    assert all(not sets[i]&sets[j] for i in range(3) for j in range(i+1,3))


def test_future_changes_do_not_change_past_features():
    df=frame()
    before=make_windows(df,30)[0].iloc[0].to_numpy()
    df.loc[30:,VALUES]=9999
    after=make_windows(df,30)[0].iloc[0].to_numpy()
    np.testing.assert_array_equal(before,after)


def test_no_engine_mixing_and_training_serving_features_match():
    df=frame()
    X,y,ids,cycles=make_windows(pd.concat([df,frame(engine=2)]),30)
    np.testing.assert_allclose(X.iloc[0],window_features(df[VALUES].iloc[:30]))
    np.testing.assert_allclose(X.iloc[0],X[ids==2].iloc[0])
    assert y[0]==20 and cycles[0]==30


def test_insufficient_window_is_not_padded():
    assert make_windows(frame(29),30)[0].empty
