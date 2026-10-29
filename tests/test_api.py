import json
from pathlib import Path
import shutil
import pytest
from fastapi.testclient import TestClient
from sentinel.api import create_app
from sentinel.inference import Predictor
from sentinel.data import sha256
from tests.test_pipeline import frame

KEY='unit-test-only-not-a-deployment-secret'
ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def bundle(tmp_path):
    # Native JSON constant artifact for hermetic API contract testing, never a trained model.
    (tmp_path/'model.json').write_text(json.dumps({'type':'constant','constant':50}))
    (tmp_path/'report.json').write_text('{}')
    from sentinel.features import SCHEMA,feature_names
    meta={'version':'test','subset':'FD001','window':30,'feature_schema':SCHEMA,
          'feature_names':feature_names(),'model_type':'constant',
          'model_sha256':sha256(tmp_path/'model.json'),'report_sha256':sha256(tmp_path/'report.json')}
    (tmp_path/'bundle.json').write_text(json.dumps(meta))
    return tmp_path


def payload(n=30):
    return {'subset':'FD001','engine_id':1,'data_mode':'replay','observations':[
        {'cycle':i,'settings':[0.,0.,0.],'sensors':[1.]*21} for i in range(1,n+1)]}


@pytest.fixture
def client(bundle):
    return TestClient(create_app(Predictor(bundle,sha256(bundle/'bundle.json')),KEY))


def test_auth_required(client):
    assert client.post('/api/v1/experimental/predict',json=payload()).status_code==401


def test_prediction_and_unknown(client):
    headers={'X-API-Key':KEY}
    r=client.post('/api/v1/experimental/predict',json=payload(),headers=headers)
    assert r.status_code==200 and r.json()['rul_cycles']==50
    assert r.json()['failure_probability'] is None
    r=client.post('/api/v1/experimental/predict',json=payload(29),headers=headers)
    assert r.json()['reason']=='insufficient_history' and r.json()['rul_cycles'] is None
    p=payload();p['subset']='FD004'
    assert client.post('/api/v1/experimental/predict',json=p,headers=headers).json()['reason']=='incompatible_subset'


@pytest.mark.parametrize('case',['missing','gap','live','extra','infinite'])
def test_bad_inputs(client,case):
    p=payload()
    if case=='missing':p['observations'][0]['sensors'].pop()
    if case=='gap':p['observations'][1]['cycle']=100
    if case=='live':p['data_mode']='live'
    if case=='extra':p['true_rul']=50
    if case=='infinite':p['observations'][0]['sensors'][0]='Infinity'
    r=client.post('/api/v1/experimental/predict',json=p,headers={'X-API-Key':KEY})
    assert r.status_code==422
    assert 'observations' not in r.text


def test_size_limit(client):
    assert client.post('/api/v1/experimental/predict',content=b' '*1048577,headers={'X-API-Key':KEY}).status_code==413


def test_absent_model():
    c=TestClient(create_app(api_key=KEY))
    assert c.post('/api/v1/experimental/predict',json=payload(),headers={'X-API-Key':KEY}).status_code==503


def test_tampered_bundle_rejected(bundle):
    manifest=sha256(bundle/'bundle.json')
    (bundle/'model.json').write_text('{}')
    with pytest.raises(ValueError,match='Artifact hash'):Predictor(bundle,manifest)


def test_wrong_manifest_hash(bundle):
    with pytest.raises(ValueError,match='manifest hash'):Predictor(bundle,'wrong')
