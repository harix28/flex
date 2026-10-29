"""Unit behavior, no PostgreSQL required."""
import pytest
from fastapi.testclient import TestClient
from sentinel.api import create_app
from sentinel.config import Settings, load_settings, ConfigurationError
from sentinel.db import Database
from sentinel.db.repository import RegistryRepository
from tests.test_api import KEY


def test_database_configuration_precedence_and_redaction(tmp_path):
    url = 'postgresql+psycopg://user:private-marker@127.0.0.1/db'
    path = tmp_path / '.env'
    path.write_text(f'SENTINEL_API_KEY={KEY}\nDATABASE_URL={url}\n')
    assert load_settings(path, environ={}).database_url == url
    assert load_settings(path, environ={'DATABASE_URL': ''}).database_url == ''
    assert 'private-marker' not in repr(load_settings(path, environ={}))


@pytest.mark.parametrize('url', ['sqlite:///test.db', 'bad-secret', 'postgresql://u:p@localhost/db', 'postgresql+psycopg://u:p@localhost/db?connect_timeout=0'])
def test_database_configuration_rejects_unsupported_urls(url):
    with pytest.raises(ConfigurationError) as error:
        Settings(KEY, database_url=url)
    assert url not in str(error.value)


def test_database_failure_is_independent_and_sanitized(caplog):
    settings = Settings(KEY, database_url='postgresql+psycopg://user:private-marker@127.0.0.1:1/absent')
    with TestClient(create_app(predictor=object(), settings=settings)) as client:
        response = client.get('/health/database')
        assert response.status_code == 503
        assert response.json()['error']['code'] == 'database_unavailable'
        assert client.get('/health/ready').status_code == 200
        assert client.get('/health/live').status_code == 200
        assert 'private-marker' not in response.text + caplog.text
    with TestClient(create_app(api_key=KEY)) as client:
        assert client.get('/health/database').json()['error']['code'] == 'database_not_configured'


def test_repository_requires_explicit_uuid_scope():
    with pytest.raises(ValueError):
        RegistryRepository(None, tenant_id=None)
    with pytest.raises(TypeError):
        RegistryRepository(None)
