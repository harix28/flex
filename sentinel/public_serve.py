"""Single-origin public demo entrypoint; database owner used only for migrations."""
import os
from pathlib import Path
import uvicorn
from fastapi.staticfiles import StaticFiles
from .config import load_settings, validate_database_url
from .container_setup import migrate_and_grant


def main():
    try:
        owner = validate_database_url(os.environ['MIGRATION_DATABASE_URL'])
        password = os.environ['SENTINEL_RUNTIME_PASSWORD']
        migrate_and_grant(owner.render_as_string(hide_password=False), password)
        os.environ['DATABASE_URL'] = owner.set(username='sentinel_app', password=password).render_as_string(hide_password=False)
        os.environ.pop('MIGRATION_DATABASE_URL', None)
        os.environ.pop('SENTINEL_RUNTIME_PASSWORD', None)
        os.environ['SENTINEL_AUTH_ORIGINS'] = os.environ.get('SENTINEL_AUTH_ORIGINS') or os.environ['RENDER_EXTERNAL_URL']
        from .api import create_app
        app = create_app(settings=load_settings().require_model())
        app.mount('/', StaticFiles(directory='/app/web', html=True), name='web')
    except Exception:
        raise SystemExit('Public startup failed: verify private database, origins and model configuration.') from None
    # Render terminates HTTPS; this image must only be served behind its trusted proxy.
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '10000')),
                proxy_headers=True, forwarded_allow_ips='*')


if __name__ == '__main__':
    main()
