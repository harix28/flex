import os
import subprocess
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from sentinel import container_setup
from sentinel.api import create_app
from sentinel.config import Settings, ROOT
from tests.test_api import KEY
from tests.test_postgres import db


def test_migration_failure_never_provisions_role(monkeypatch):
    def fail(*args):
        raise RuntimeError('migration failed')
    monkeypatch.setattr(container_setup.command, 'upgrade', fail)
    monkeypatch.setattr(container_setup, 'create_engine', lambda *a, **k: pytest.fail('Must not provision after failure'))
    with pytest.raises(RuntimeError, match='migration failed'):
        container_setup.migrate_and_grant('postgresql+psycopg://owner:owner@localhost/db', 'a'*40)


def test_readiness_checks_database_schema(monkeypatch):
    class FakeDB:
        def __init__(self, url): pass
        def ready(self): return False
        def close(self): pass
    monkeypatch.setattr('sentinel.api.Database', FakeDB)
    settings = Settings(api_key=KEY, database_url='postgresql+psycopg://owner:pass@localhost/db')
    client = TestClient(create_app(predictor=object(), settings=settings))
    assert client.get('/health/live').status_code == 200
    assert client.get('/health/ready').status_code == 200
    assert client.get('/health/deployment').status_code == 503


def test_powershell_deploy_stops_on_native_failure(tmp_path):
    shell = shutil.which('pwsh') or shutil.which('powershell')
    if not shell:
        pytest.skip('PowerShell unavailable')
    # Mock only the external executable. Never launch Docker during this test.
    script = tmp_path/'failure.ps1'
    script.write_text("function docker { $global:LASTEXITCODE = 7 }; & '" + str(ROOT/'scripts/deploy.ps1') + "'", encoding='utf-8')
    result = subprocess.run([shell, '-NoProfile', '-File', str(script)], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'Container health checks passed' not in result.stdout


@pytest.mark.parametrize('fail_up', [False, True])
def test_powershell_deploy_waits_and_uses_selected_env(tmp_path, fail_up):
    shell = shutil.which('pwsh') or shutil.which('powershell')
    if not shell:
        pytest.skip('PowerShell unavailable')
    envfile = tmp_path/'private env'
    envfile.write_text('')
    logfile = tmp_path/'calls'
    script = tmp_path/'mock.ps1'
    script.write_text(
        "function docker { Add-Content -LiteralPath '" + str(logfile) + "' -Value ($args -join '|'); "
        "$global:LASTEXITCODE = 0; "
        + ("if ($args -contains 'up') { $global:LASTEXITCODE = 7 }; " if fail_up else '')
        + "}; & '" + str(ROOT/'scripts/deploy.ps1') + "' -Dev -EnvFile '" + str(envfile) + "'",
        encoding='utf-8')
    result = subprocess.run([shell, '-NoProfile', '-File', str(script)], capture_output=True, text=True)
    calls = logfile.read_text(encoding='utf-8-sig')
    assert '--env-file|' + str(envfile) in calls
    assert 'docker-compose.dev.yml' in calls
    assert '--wait|--wait-timeout|180' in calls
    assert (result.returncode != 0) == fail_up
    assert ('Container health checks passed' in result.stdout) == (not fail_up)


@pytest.mark.postgres
def test_runtime_role_cannot_ddl_or_change_revision(db):
    database, config = db
    role = 'test_runtime_' + uuid4().hex
    password = uuid4().hex + uuid4().hex
    url = database.engine.url
    runtime = None
    try:
        container_setup.migrate_and_grant(url.render_as_string(hide_password=False), password, role)
        runtime = create_engine(url.set(username=role, password=password), hide_parameters=True)
        with runtime.begin() as connection:
            assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar() == '0007_mlops'
            connection.execute(text("INSERT INTO tenants(name) VALUES ('runtime permission test')"))
        for statement in ('CREATE TABLE forbidden_table(id int)', 'DELETE FROM alembic_version'):
            with pytest.raises(DBAPIError):
                with runtime.begin() as connection:
                    connection.execute(text(statement))
        with database.engine.connect() as connection:
            flags = connection.execute(text('SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname=:role'), {'role':role}).one()
            assert not any(flags)
    finally:
        if runtime:
            runtime.dispose()
        # Role names are generated above and contain only lowercase ASCII/hex.
        with database.engine.begin() as connection:
            connection.exec_driver_sql('DROP OWNED BY ' + role)
            connection.exec_driver_sql('DROP ROLE ' + role)
