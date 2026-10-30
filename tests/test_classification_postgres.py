from uuid import uuid4
import pytest
from tests.test_postgres import db
from tests.test_auth_postgres import setup, client_for, login
from tests.test_ingestion_postgres import registered, post
from tests.test_ingestion import payload
from sentinel.config import ROOT

pytestmark = pytest.mark.postgres

def test_classification_auth_cutoff_and_tenant_isolation(setup):
    with client_for(setup, classifier_dir=ROOT/'runs/all-subsets-20261030-v1/COMBINED') as c:
        h = login(c, setup)
        path = registered(c, setup, h)
        assert post(c, path, h, payload((1,3))).status_code == 200
        endpoint = path+'/lifetime-classification'
        r = c.get(endpoint)
        assert r.status_code == 200, r.text
        assert r.json()['source_cycle'] == 3 and r.json()['persisted'] is False
        assert 'rul' not in r.json() and 'failure_probability' not in r.json()
        assert c.get(endpoint+'?cutoff_cycle=2').json()['source_cycle'] == 1
        assert c.get(endpoint+'?cutoff_cycle=0').status_code == 422
        assert c.get(endpoint.replace(str(setup['a']), str(setup['b']))).status_code == 404
        login(c, setup, 'viewer@example.com')
        assert c.get(endpoint).status_code == 200
        login(c, setup, 'admin-b@example.com')
        assert c.get(endpoint).status_code == 404
        c.cookies.clear()
        assert c.get(endpoint).status_code == 401
