"""Single-origin public demo entrypoint; database owner used only for migrations."""
import os
from pathlib import Path
import uvicorn
from fastapi.staticfiles import StaticFiles
from .config import load_settings, validate_database_url
from .container_setup import migrate_and_grant


def main():
    try:
        if 'MIGRATION_DATABASE_URL' in os.environ and 'SENTINEL_RUNTIME_PASSWORD' in os.environ:
            owner = validate_database_url(os.environ['MIGRATION_DATABASE_URL'])
            password = os.environ['SENTINEL_RUNTIME_PASSWORD']
            migrate_and_grant(owner.render_as_string(hide_password=False), password)
            os.environ['DATABASE_URL'] = owner.set(username='sentinel_app', password=password).render_as_string(hide_password=False)
            os.environ.pop('MIGRATION_DATABASE_URL', None)
            os.environ.pop('SENTINEL_RUNTIME_PASSWORD', None)
        elif 'DATABASE_URL' in os.environ:
            from alembic import command
            from alembic.config import Config
            cfg = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
            cfg.set_main_option('sqlalchemy.url', os.environ['DATABASE_URL'])
            command.upgrade(cfg, 'head')

        raw_origins = os.environ.get('SENTINEL_AUTH_ORIGINS') or os.environ.get('RENDER_EXTERNAL_URL', '')
        origins = [o.strip().rstrip('/') for o in raw_origins.split(',') if o.strip()]
        if origins:
            os.environ['SENTINEL_AUTH_ORIGINS'] = ','.join(origins)

        if not os.environ.get('SENTINEL_API_KEY'):
            import secrets
            os.environ['SENTINEL_API_KEY'] = secrets.token_urlsafe(32)

        from .api import create_app
        app = create_app(settings=load_settings().require_model())
        app.mount('/', StaticFiles(directory='/app/web', html=True), name='web')
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise SystemExit(f'Public startup failed: {e}') from None
    # Render terminates HTTPS; this image must only be served behind its trusted proxy.
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '10000')),
                proxy_headers=True, forwarded_allow_ips='*')


if __name__ == '__main__':
    main()
