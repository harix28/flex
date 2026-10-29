"""Replay contract validation independent of PostgreSQL."""
from copy import deepcopy
import pytest
from pydantic import ValidationError
from sentinel.ingestion.schemas import Batch
from sentinel.ingestion.importer import load_selection,origin_for
from sentinel.ingestion.service import payload_digest
from sentinel.config import ROOT


def payload(cycles=(1,)):
    return dict(source=dict(dataset='C-MAPSS',subset='FD001',partition='test',engine_id=1,file_sha256='a'*64),
                observations=[dict(cycle=c,settings=[1.,2.,3.],sensors=[float(i) for i in range(21)]) for c in cycles])


@pytest.mark.parametrize('field,value',[
    ('cycle',0),('cycle',-1),('cycle',2147483648),('cycle',True),('cycle',1.5),('cycle','1'),
    ('settings',[1,2]),('settings',[1,2,3,4]),('settings',[1,float('nan'),3]),
    ('settings',[1,float('inf'),3]),('settings',[1,float('-inf'),3]),('settings',[1,True,3]),
    ('sensors',[1]*20),('sensors',[1]*22),('sensors',[None]*21),('sensors',['1']*21),
    ('observed_at','2026-01-01T00:00:00Z'),('rul',10)])
def test_invalid_observations(field,value):
    body=payload();body['observations'][0][field]=value
    with pytest.raises(ValidationError): Batch.model_validate(body)


@pytest.mark.parametrize('field,value', [('engine_id',0),('engine_id',2147483648),('engine_id',True),
    ('partition','validation'),('file_sha256','x'*64),('schema_version',True),('schema_version',2),('rul',1)])
def test_invalid_source(field,value):
    body=payload();body['source'][field]=value
    with pytest.raises(ValidationError): Batch.model_validate(body)


def test_bounds_duplicates_and_canonical_order():
    for cycles in ((),(1,1),tuple(range(1,502))):
        with pytest.raises(ValidationError): Batch.model_validate(payload(cycles))
    assert payload_digest(Batch.model_validate(payload((2,1))))==payload_digest(Batch.model_validate(payload((1,2))))
    assert Batch.model_validate(payload((2147483647,))).observations[0].cycle==2147483647


def test_real_file_selection_and_no_labels():
    source,rows=load_selection(ROOT/'data/raw','FD001','test',1)
    assert len(rows)==31 and source['partition']=='test'
    assert set(rows[0])=={'cycle','settings','sensors'}
    assert len(rows[0]['settings'])==3 and len(rows[0]['sensors'])==21
    assert rows[0]['sensors'][0]==518.67
    with pytest.raises(ValueError): load_selection(ROOT/'data/raw','FD001','test',2147483648)


@pytest.mark.parametrize('url',['http://example.com','https://user:pass@example.com','https://example.com/path','ftp://example.com'])
def test_secure_import_origin(url):
    with pytest.raises(ValueError): origin_for(url,True)
