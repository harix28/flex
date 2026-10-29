import pytest
from sentinel.config import Settings, ConfigurationError, load_settings
from sentinel.auth.security import hash_password, verify_password, normalize_email, HASHER
from sentinel.auth.limiter import LoginLimiter
from sentinel.auth.permissions import permits
from tests.test_api import KEY


def test_argon2id_hashes_salts_and_verification():
    password = 'test-only-password-long'
    first, second = hash_password(password), hash_password(password)
    assert first.startswith('$argon2id$') and first != second
    assert password not in first
    assert verify_password(first,password)
    assert not verify_password(first,'wrong')
    assert not verify_password(None,password)
    assert not verify_password('broken-hash',password)
    assert not HASHER.check_needs_rehash(first)


def test_email_normalization_and_password_bounds():
    assert normalize_email(' USER@Example.COM ') == 'user@example.com'
    for email in ('bad','a@','a b@example.com'):
        with pytest.raises(ValueError): normalize_email(email)
    for password in ('short','x'*129):
        with pytest.raises(ValueError): hash_password(password)


@pytest.mark.parametrize('changes', [
    {'auth_enabled':True}, {'auth_enabled':True,'database_url':'postgresql+psycopg://u:p@localhost/db'},
    {'auth_origins':('http://example.com',)}, {'auth_origins':('https://*.example.com',)},
    {'auth_localhost':True,'auth_origins':('http://example.com',)},
    {'auth_origins':('https://example.com/path',)}, {'session_seconds':0}, {'login_limit':0},
    {'login_window':0}, {'login_global_limit':0}])
def test_auth_configuration_fail_closed(changes):
    with pytest.raises(ConfigurationError): Settings(KEY,**changes)


def test_auth_config_precedence(tmp_path):
    path=tmp_path/'.env'
    path.write_text(f'SENTINEL_API_KEY={KEY}\nSENTINEL_SESSION_SECONDS=100\n')
    assert load_settings(path,environ={'SENTINEL_SESSION_SECONDS':'200'}).session_seconds==200
    with pytest.raises(ConfigurationError):
        load_settings(path,environ={'SENTINEL_AUTH_ENABLED':'yes'})


def test_limiter_bounds_account_ip_and_window(monkeypatch):
    now=[1.0]
    monkeypatch.setattr('sentinel.auth.limiter.monotonic',lambda:now[0])
    limiter=LoginLimiter(2,10,10)
    assert limiter.allow('ip1','user1')
    assert limiter.allow('ip2','user1')
    assert not limiter.allow('ip3','user1')
    assert limiter.allow('ip1','user2')
    assert not limiter.allow('ip1','user3')
    now[0]=12
    assert limiter.allow('ip1','user1')
    assert len(limiter.buckets)==3


def test_central_permissions_do_not_invent_maintenance_or_platform_access():
    for role in ('admin','plant_manager','technician','viewer'):
        assert permits([role],'organization.read')
        assert not permits([role],'maintenance.approve')
        assert not permits([role],'platform.admin')
    assert permits(['admin'],'members.manage')
    assert not permits(['plant_manager'],'members.manage')


def test_auth_database_unavailable_is_controlled():
    from fastapi.testclient import TestClient
    from sentinel.api import create_app
    from sentinel.auth.security import new_token
    settings=Settings(KEY,database_url='postgresql+psycopg://user:private-marker@127.0.0.1:1/no_db',
      auth_enabled=True,auth_localhost=True,auth_origins=('http://127.0.0.1:8000',))
    with TestClient(create_app(predictor=object(),settings=settings),base_url='http://127.0.0.1:8000') as c:
        c.cookies.set('meridian_session',new_token())
        r=c.get('/api/v1/auth/me')
        assert r.status_code==503 and r.json()['error']['code']=='database_unavailable'
        assert 'private-marker' not in r.text
        assert c.get('/health/live').status_code==200
        assert c.get('/health/ready').status_code==200
        assert c.get('/health/database').status_code==503


def test_cli_refuses_insecure_noninteractive_password_input(monkeypatch):
    from sentinel.auth.__main__ import password_prompt
    import sys
    monkeypatch.setattr(sys.stdin,'isatty',lambda:False)
    with pytest.raises(ValueError,match='Interactive terminal'):
        password_prompt()
