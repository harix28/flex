"""One-shot container migrations and least-privilege runtime role provisioning."""
import os
import re

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from sentinel.config import ROOT, validate_database_url


def migrate_and_grant(url, password, runtime_role="sentinel_app"):
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", runtime_role):
        raise ValueError("Invalid runtime role")
    # URL-safe characters only: the same password is interpolated into Compose URLs.
    if not isinstance(password, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', password):
        raise ValueError('Runtime password must be 32-128 URL-safe characters')
    parsed = validate_database_url(url)
    if password == parsed.password:
        raise ValueError('Owner and runtime passwords must differ')
    config = Config(str(ROOT / 'alembic.ini'))
    config.attributes['database_url'] = url
    # Never provision or launch against a failed migration.
    command.upgrade(config, 'head')
    engine = create_engine(parsed, hide_parameters=True)
    try:
        with engine.begin() as connection:
            from psycopg import sql
            cursor = connection.connection.driver_connection.cursor()
            role = sql.Identifier(runtime_role)
            try:
                cursor.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (runtime_role,))
                if not cursor.fetchone():
                    cursor.execute(sql.SQL('CREATE ROLE {} LOGIN').format(role))
                cursor.execute(sql.SQL('ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(role, sql.Literal(password)))
                cursor.execute(sql.SQL('REVOKE CREATE ON DATABASE {} FROM PUBLIC').format(sql.Identifier(parsed.database)))
                cursor.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(parsed.database), role))
                cursor.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
                for statement in (
                    'GRANT USAGE ON SCHEMA public TO {}',
                    'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}',
                    'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}',
                    'REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM {}',
                ):
                    cursor.execute(sql.SQL(statement).format(role))
            finally:
                cursor.close()
    finally:
        engine.dispose()


def main():
    try:
        migrate_and_grant(os.environ['DATABASE_URL'], os.environ['SENTINEL_RUNTIME_PASSWORD'])
    except Exception:
        # Connection exceptions can contain credentials. Do not print them in containers.
        raise SystemExit('Migration/runtime-role setup failed; backend startup blocked.') from None
    print('Migrations and runtime-role grants completed.')


if __name__ == '__main__':
    main()
