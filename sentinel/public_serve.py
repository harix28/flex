"""Single-origin public demo entrypoint; database owner used only for migrations."""
import os
import sys
from pathlib import Path
import uvicorn
from fastapi.staticfiles import StaticFiles
from .config import load_settings, validate_database_url
from .container_setup import migrate_and_grant


def seed_demo_accounts(db_url: str):
    from sqlalchemy import create_engine, text
    from .auth.service import create_user
    engine = create_engine(db_url, hide_parameters=True)
    try:
        with engine.begin() as conn:
            exists = conn.execute(text("SELECT id FROM users WHERE email='admin@meridian.example.com'")).scalar_one_or_none()
            if exists:
                return
            tenant = conn.execute(text("SELECT id FROM tenants WHERE slug='meridian-a'")).scalar_one_or_none()
            if not tenant:
                tenant = conn.execute(
                    text("INSERT INTO tenants(name, slug) VALUES ('Meridian Turbofan Maintenance', 'meridian-a') RETURNING id")
                ).scalar_one()

            admin_id = create_user(conn, 'admin@meridian.example.com', 'Password12345!', 'Chief Maintenance Inspector (Admin)')
            conn.execute(
                text("INSERT INTO memberships(tenant_id, user_id, roles) VALUES (:t, :u, ARRAY['admin', 'manager', 'technician'])"),
                dict(t=tenant, u=admin_id)
            )

            mgr_id = create_user(conn, 'manager@meridian.example.com', 'Password12345!', 'Maintenance Operations Lead')
            conn.execute(
                text("INSERT INTO memberships(tenant_id, user_id, roles) VALUES (:t, :u, ARRAY['manager'])"),
                dict(t=tenant, u=mgr_id)
            )

            tech_id = create_user(conn, 'tech@meridian.example.com', 'Password12345!', 'Lead Turbofan Technician (A&P)')
            conn.execute(
                text("INSERT INTO memberships(tenant_id, user_id, roles) VALUES (:t, :u, ARRAY['technician'])"),
                dict(t=tenant, u=tech_id)
            )
            print("Successfully auto-seeded baseline demo accounts into PostgreSQL.")
    except Exception as e:
        print(f"Demo seeding note: {e}", file=sys.stderr)
    finally:
        engine.dispose()


def main():
    try:
        # Normalize database URLs from Render or cloud providers (e.g. postgres:// -> postgresql+psycopg://)
        for key in ('MIGRATION_DATABASE_URL', 'DATABASE_URL'):
            val = os.environ.get(key, '')
            if val.startswith('postgres://'):
                os.environ[key] = 'postgresql+psycopg://' + val[len('postgres://'):]
            elif val.startswith('postgresql://') and not val.startswith('postgresql+'):
                os.environ[key] = 'postgresql+psycopg://' + val[len('postgresql://'):]

        if 'MIGRATION_DATABASE_URL' in os.environ and 'SENTINEL_RUNTIME_PASSWORD' in os.environ:
            owner = validate_database_url(os.environ['MIGRATION_DATABASE_URL'])
            password = os.environ['SENTINEL_RUNTIME_PASSWORD']
            try:
                migrate_and_grant(owner.render_as_string(hide_password=False), password)
                os.environ['DATABASE_URL'] = owner.set(username='sentinel_app', password=password).render_as_string(hide_password=False)
            except Exception as e:
                print(f"Migration/grant warning: {e}. Falling back to direct database migration.", file=sys.stderr)
                try:
                    from alembic import command
                    from alembic.config import Config
                    cfg = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
                    cfg.set_main_option('sqlalchemy.url', owner.render_as_string(hide_password=False))
                    command.upgrade(cfg, 'head')
                except Exception as ex:
                    print(f"Direct migration note: {ex}", file=sys.stderr)
                os.environ['DATABASE_URL'] = owner.render_as_string(hide_password=False)
            finally:
                os.environ.pop('MIGRATION_DATABASE_URL', None)
                os.environ.pop('SENTINEL_RUNTIME_PASSWORD', None)
        elif 'DATABASE_URL' in os.environ:
            try:
                from alembic import command
                from alembic.config import Config
                cfg = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
                cfg.set_main_option('sqlalchemy.url', os.environ['DATABASE_URL'])
                command.upgrade(cfg, 'head')
            except Exception as e:
                print(f"Direct migration warning: {e}", file=sys.stderr)

        # Normalize origins: strip whitespace and trailing slashes
        raw_origins = os.environ.get('SENTINEL_AUTH_ORIGINS') or os.environ.get('RENDER_EXTERNAL_URL', '')
        origins = [o.strip().rstrip('/') for o in raw_origins.split(',') if o.strip()]
        for default_origin in (
            'https://meridian-sentinel.onrender.com',
            'https://meridian-sentinel.vercel.app',
            'https://flex-apps.vercel.app',
            'http://localhost:8080',
            'http://localhost:5173',
            'http://127.0.0.1:8080',
            'http://127.0.0.1:5173',
        ):
            if default_origin not in origins:
                origins.append(default_origin)
        os.environ['SENTINEL_AUTH_ORIGINS'] = ','.join(origins)

        # Ensure baseline demo accounts exist when database is attached
        if os.environ.get('DATABASE_URL'):
            seed_demo_accounts(os.environ['DATABASE_URL'])

        # Auto-generate secure API key if not explicitly set in environment
        if not os.environ.get('SENTINEL_API_KEY'):
            import secrets
            os.environ['SENTINEL_API_KEY'] = secrets.token_urlsafe(32)

        # If no database is connected, fall back to standalone public demo mode (auth disabled)
        if not os.environ.get('DATABASE_URL'):
            print("Notice: No database connected. Starting in standalone demo mode.", file=sys.stderr)
            os.environ['SENTINEL_AUTH_ENABLED'] = 'false'

        from .api import create_app
        app = create_app(settings=load_settings().require_model())
        web_dir = Path('/app/web')
        if web_dir.is_dir():
            app.mount('/', StaticFiles(directory=str(web_dir), html=True), name='web')
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise SystemExit(f'Public startup failed: {e}') from None

    # Render terminates HTTPS; this image must only be served behind its trusted proxy.
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '10000')),
                proxy_headers=True, forwarded_allow_ips='*')


if __name__ == '__main__':
    main()
