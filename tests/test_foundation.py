import json
import logging
from uuid import UUID
import pytest
from fastapi.testclient import TestClient
from sentinel.api import create_app
from sentinel.config import ConfigurationError, Settings, load_settings, read_env
from sentinel.data import sha256
from sentinel.local_setup import initialize
from tests.test_api import KEY, bundle, client, payload


def test_configuration_precedence_and_no_environment_mutation(tmp_path, monkeypatch):
    path = tmp_path / '.env'
    path.write_text(f'SENTINEL_API_KEY={KEY}\nSENTINEL_PORT=8100\n', encoding='utf-8')
    monkeypatch.delenv('SENTINEL_PORT', raising=False)
    assert load_settings(path, environ={}).port == 8100
    assert load_settings(path, environ={'SENTINEL_PORT': '8200'}).port == 8200
    assert load_settings(path, environ={'SENTINEL_PORT': '8200'},
                         overrides={'SENTINEL_PORT': 8300}).port == 8300
    import os
    assert 'SENTINEL_PORT' not in os.environ
    assert KEY not in repr(load_settings(path, environ={}))


@pytest.mark.parametrize('field,value', [
    ('SENTINEL_API_KEY', ''), ('SENTINEL_API_KEY', 'short'),
    ('SENTINEL_API_KEY', 'replace-with-a-random-generated-key'),
    ('SENTINEL_API_KEY', 'x' * 23 + '\u00e9'),
    ('SENTINEL_PORT', '0'), ('SENTINEL_PORT', '65536'), ('SENTINEL_PORT', 'abc'),
    ('SENTINEL_HOST', '0.0.0.0'), ('SENTINEL_MODEL_DIR', 'absent'),
    ('SENTINEL_BUNDLE_SHA256', '0' * 64)])
def test_invalid_configuration_is_sanitized(tmp_path, field, value):
    with pytest.raises(ConfigurationError) as error:
        load_settings(tmp_path / '.env', environ={'SENTINEL_API_KEY': KEY, field: value})
    assert KEY not in str(error.value)


def test_relative_model_path_and_hash_validation(tmp_path):
    model = tmp_path / 'model'
    model.mkdir()
    path = tmp_path / '.env'
    path.write_text(f'SENTINEL_API_KEY="{KEY}"\nSENTINEL_MODEL_DIR=model\n'
                    f'SENTINEL_BUNDLE_SHA256={"a" * 64}\n')
    assert load_settings(path, environ={}).model_dir == model
    with pytest.raises(ConfigurationError, match='SHA256'):
        load_settings(path, environ={'SENTINEL_BUNDLE_SHA256': 'wrong'})


@pytest.mark.parametrize('text', ['not-an-assignment', 'A=1\nA=2', 'A="unclosed'])
def test_bad_env_format_does_not_echo_contents(tmp_path, text):
    path = tmp_path / '.env'
    path.write_text(text)
    with pytest.raises(ConfigurationError) as error:
        read_env(path)
    assert text not in str(error.value)


def test_generated_key_is_reused_without_printing(tmp_path, monkeypatch, capsys):
    for key in ('SENTINEL_API_KEY', 'SENTINEL_MODEL_DIR', 'SENTINEL_BUNDLE_SHA256', 'SENTINEL_PORT', 'SENTINEL_HOST'):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / 'runs/fd001-v1').mkdir(parents=True)
    path = tmp_path / '.env'
    first = initialize(path)
    second = initialize(path)
    assert first.api_key == second.api_key and len(first.api_key) >= 32
    assert first.api_key not in capsys.readouterr().out


def test_process_key_is_not_written_to_local_file(tmp_path, monkeypatch):
    monkeypatch.setenv('SENTINEL_API_KEY', KEY)
    for key in ('SENTINEL_MODEL_DIR', 'SENTINEL_BUNDLE_SHA256', 'SENTINEL_PORT', 'SENTINEL_HOST'):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / 'runs/fd001-v1').mkdir(parents=True)
    path = tmp_path / '.env'
    assert initialize(path).api_key == KEY
    assert KEY not in path.read_text()


def test_health_meanings_with_and_without_model(client):
    empty = TestClient(create_app(api_key=KEY))
    assert empty.get('/health').json() == {'status': 'ok', 'model_loaded': False, 'mode': 'local_experiment'}
    assert empty.get('/health/live').status_code == 200
    assert empty.get('/health/ready').status_code == 503
    assert client.get('/health/ready').json()['status'] == 'ready'
    assert client.get('/health/live').status_code == 200


@pytest.mark.parametrize('path', ['/api/v1/experimental/model', '/api/v1/experimental/predict'])
@pytest.mark.parametrize('key', [None, 'incorrect-key'])
def test_both_protected_routes_reject_missing_or_wrong_key(client, path, key):
    headers = {} if key is None else {'X-API-Key': key}
    response = client.get(path, headers=headers) if path.endswith('model') else client.post(path, json=payload(), headers=headers)
    assert response.status_code == 401
    assert response.json()['error']['code'] == 'authentication_required'
    assert response.headers['x-request-id'] == response.json()['request_id']


def test_authenticated_model_report(client):
    assert client.get('/api/v1/experimental/model', headers={'X-API-Key': KEY}).status_code == 200


@pytest.mark.parametrize('field', ['engine_id', 'cycle'])
def test_out_of_range_integers_return_422(client, field):
    data = payload()
    if field == 'cycle':
        data['observations'][0]['cycle'] = 10**30
    else:
        data[field] = 10**30
    assert client.post('/api/v1/experimental/predict', json=data, headers={'X-API-Key': KEY}).status_code == 422


def test_every_response_has_trace_and_cache_headers(client):
    responses = [client.get('/health'), client.get('/missing'), client.post('/health'),
                 client.post('/api/v1/experimental/predict', content=b' ' * 1048577),
                 client.post('/api/v1/experimental/predict', content=b'{bad', headers={'X-API-Key': KEY})]
    assert [r.status_code for r in responses] == [200, 404, 405, 413, 422]
    ids = []
    for response in responses:
        request_id = response.headers['x-request-id']
        UUID(request_id)
        ids.append(request_id)
        assert response.headers['cache-control'] == 'no-store'
        if response.status_code >= 400:
            assert response.json()['request_id'] == request_id
    assert len(set(ids)) == len(ids)


def test_unexpected_errors_and_logs_are_sanitized(caplog):
    class BrokenPredictor:
        def predict(self, subset, records):
            raise RuntimeError(f'{KEY} private-telemetry-marker {records}')
    app = create_app(BrokenPredictor(), KEY)
    with caplog.at_level(logging.INFO, logger='sentinel.http'):
        response = TestClient(app).post('/api/v1/experimental/predict?secret=private-query',
                                        json=payload(), headers={'X-API-Key': KEY})
    assert response.status_code == 500
    assert response.json()['error']['code'] == 'internal_error'
    assert response.headers['x-request-id'] == response.json()['request_id']
    for secret in (KEY, 'private-telemetry-marker', 'private-query', 'Traceback'):
        assert secret not in response.text + caplog.text


def test_factory_rejects_corrupt_artifact_before_readiness(bundle):
    settings = Settings(KEY, bundle, sha256(bundle / 'bundle.json'))
    (bundle / 'model.json').write_text('{"secret": "do-not-echo"}')
    with pytest.raises(ConfigurationError, match='Model bundle rejected') as error:
        create_app(settings=settings)
    assert 'do-not-echo' not in str(error.value)


def test_factory_loads_verified_configured_model(bundle):
    app = create_app(settings=Settings(KEY, bundle, sha256(bundle / 'bundle.json')))
    assert TestClient(app).get('/health/ready').status_code == 200


def test_openapi_snapshots_match_factory():
    from sentinel.config import ROOT
    schema = create_app(api_key=KEY).openapi()
    for name in ('packages/contracts/experimental.openapi.json', 'reports/openapi.json'):
        assert json.loads((ROOT / name).read_text()) == schema


def test_empty_process_key_does_not_fall_back_to_file(tmp_path):
    path = tmp_path / '.env'
    path.write_text(f'SENTINEL_API_KEY={KEY}\n')
    with pytest.raises(ConfigurationError, match='API_KEY'):
        load_settings(path, environ={'SENTINEL_API_KEY': ''})


def test_server_requires_a_model_configuration():
    with pytest.raises(ConfigurationError, match='required to start'):
        Settings(KEY).require_model()
