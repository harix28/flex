"""Regression coverage for Phase 8/9 review findings; PostgreSQL only."""
import json
from pathlib import Path
import pytest
from sqlalchemy import text
from tests.test_postgres import db
from tests.test_auth_postgres import setup, client_for, login
from tests.test_predictions_postgres import pred_client, registered_machine, ingest_observations
from sentinel.config import ROOT, TRUSTED_FD001_SHA256, load_settings, ConfigurationError
from sentinel.ingestion.importer import load_selection
from sentinel.mlops import deployment
from sentinel.mlops.registry import register_model
from sentinel.mlops.evaluation import evaluate_predictions_performance, GroundTruthEvaluationError
from sentinel.mlops.drift import build_or_load_reference_profile, evaluate_input_drift

pytestmark = pytest.mark.postgres
MODEL = ROOT / 'runs/fd001-v1'


def configure(database):
    with database.transaction() as s:
        register_model(s, MODEL, TRUSTED_FD001_SHA256, actor='test')
        return deployment.deploy_model(s, 'fd001-v1', 'test', 'Regression release', MODEL)


class PredictorIdentity:
    bundle_sha256 = TRUSTED_FD001_SHA256
    meta = json.loads((MODEL / 'bundle.json').read_text())


def test_activation_identity_and_pending_restart(setup):
    database = setup['database']
    configure(database)
    class WrongDigest:
        meta = {**PredictorIdentity.meta, 'model_sha256': '0' * 64}
    with database.transaction() as s:
        assert deployment.record_activation(s, WrongDigest()) is None
        assert s.execute(text("SELECT status FROM model_deployments")).scalar_one() == 'failed'
    configure(database)
    with database.transaction() as s:
        assert deployment.record_activation(s, PredictorIdentity())['status'] == 'active'
    configure(database)
    with database.transaction() as s:
        assert deployment.get_deployment_status(s, PredictorIdentity())['state'] == 'pending_restart'
        assert deployment.record_activation(s, PredictorIdentity())['status'] == 'active'
        assert s.execute(text("SELECT count(*) FROM model_deployments WHERE status='active'")).scalar_one() == 1
        assert deployment.get_deployment_status(s, WrongDigest())['state'] == 'active_untracked'


def test_release_rollback_preserves_pointer_and_commit_failure_recovers(setup, monkeypatch):
    database = setup['database']
    configure(database)
    before = deployment.RELEASE_POINTER_FILE.read_bytes()
    with pytest.raises(RuntimeError):
        with database.transaction() as s:
            deployment.deploy_model(s, 'fd001-v1', 'test', 'Aborted release', MODEL)
            raise RuntimeError('Rollback transaction')
    assert deployment.RELEASE_POINTER_FILE.read_bytes() == before
    original = deployment.write_atomic_release_file
    def fail_write(*args, **kwargs):
        raise OSError('Simulated disk failure')
    monkeypatch.setattr(deployment, 'write_atomic_release_file', fail_write)
    with pytest.raises(OSError):
        configure(database)
    assert deployment.RELEASE_POINTER_FILE.read_bytes() == before
    monkeypatch.setattr(deployment, 'write_atomic_release_file', original)
    deployment.sync_release_pointer(database.engine)
    assert deployment.RELEASE_POINTER_FILE.read_bytes() != before
    with database.transaction() as s:
        expected = str(s.execute(text("SELECT id FROM model_deployments WHERE status='desired'")).scalar_one())
    assert deployment.read_release_file()['deployment_id'] == expected


def test_explicit_env_file_release_mode_and_stale_pointer(setup, tmp_path):
    configure(setup['database'])
    env_file = tmp_path / 'runtime.env'
    env_file.write_text('')
    values = {'SENTINEL_API_KEY': setup['settings'].api_key,
              'DATABASE_URL': setup['config'].attributes['database_url'],
              'SENTINEL_RELEASE_POINTER': str(deployment.RELEASE_POINTER_FILE),
              'SENTINEL_MODEL_DIR': str(tmp_path), 'SENTINEL_BUNDLE_SHA256': '0'*64}
    settings = load_settings(env_file=env_file, environ=values)
    assert settings.model_dir == MODEL
    assert settings.bundle_sha256 == TRUSTED_FD001_SHA256
    pointer = deployment.read_release_file()
    pointer['deployment_id'] = '00000000-0000-0000-0000-000000000000'
    deployment.write_atomic_release_file(pointer)
    with pytest.raises(ConfigurationError, match='inconsistent'):
        load_settings(env_file=env_file, environ=values)


def test_partial_ingestion_evaluation_uses_complete_endpoint(setup):
    source, rows = load_selection(ROOT/'data/raw', 'FD001', 'test', 1)
    with pred_client(setup) as c:
        h = login(c, setup)
        machine = registered_machine(c, setup, h)
        ingest_observations(c, machine['detail_api_path'], h, rows[:30], source)
        assert c.post(f"/api/v1/machines/{machine['id']}/predictions", headers=h).status_code == 200
        with setup['database'].transaction() as s:
            first = evaluate_predictions_performance(s, setup['a'], ROOT/'data/raw/RUL_FD001.txt')
        assert first['metrics']['sample_breakdown'][0]['true_rul_cycles'] == 113
        ingest_observations(c, machine['detail_api_path'], h, rows[30:], source, key='remaining')
        with setup['database'].transaction() as s:
            later = evaluate_predictions_performance(s, setup['a'], ROOT/'data/raw/RUL_FD001.txt')
        assert later['metrics']['sample_breakdown'] == first['metrics']['sample_breakdown']


def test_empty_evaluation_and_mismatched_reference(setup, tmp_path):
    with setup['database'].transaction() as s:
        result = evaluate_predictions_performance(s, setup['a'], ROOT/'data/raw/RUL_FD001.txt')
        assert result['status'] == 'insufficient_data'
    labels = tmp_path / 'RUL_FD001.txt'
    labels.write_text('112\n')
    with setup['database'].transaction() as s:
        with pytest.raises(GroundTruthEvaluationError, match='SHA256 mismatch'):
            evaluate_predictions_performance(s, setup['a'], labels)


def test_assignee_lookup_is_narrow_and_tenant_scoped(setup):
    path = f"/api/v1/organizations/{setup['a']}/work-order-assignees"
    with client_for(setup) as c:
        login(c, setup, 'plant_manager@example.com')
        response = c.get(path)
        assert response.status_code == 200
        assert [m['user_id'] for m in response.json()['items']] == [str(setup['users']['technician'])]
        assert 'email' not in response.json()['items'][0]
        assert c.get(f"/api/v1/organizations/{setup['a']}/members").status_code == 403
        assert c.get(f"/api/v1/organizations/{setup['b']}/work-order-assignees").status_code == 404
        assert c.get(path+'?offset=100').json()['items'] == []
        assert c.get(path+'?offset=-1').status_code == 422
    with client_for(setup) as c:
        login(c, setup, 'viewer@example.com')
        assert c.get(path).status_code == 403


def test_drift_cache_identity_and_wrong_model(setup, tmp_path):
    cache = tmp_path / 'drift.json'
    cache.write_text(json.dumps({'model_version':'different', 'feature_stats':[]}))
    profile = build_or_load_reference_profile(cache_path=cache)
    assert profile['model_version'] == 'fd001-v1'
    assert profile['identity']['bundle_digest'] == TRUSTED_FD001_SHA256
    assert len(profile['feature_stats']) == 96
    with pytest.raises(ValueError):
        build_or_load_reference_profile(tmp_path/'missing', cache_path=cache)
    with setup['database'].transaction() as s:
        result = evaluate_input_drift(s, setup['a'], model_version='different', cache_path=cache)
        assert result['status'] == 'incompatible_reference'
