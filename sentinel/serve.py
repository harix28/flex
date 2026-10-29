"""Canonical local entrypoint: python -m sentinel.serve."""
import argparse
import logging
import uvicorn
from .api import create_app
from .config import ConfigurationError, load_settings


def get_app(env_file=None):
    """Application factory for WSGI/ASGI servers (Gunicorn, Uvicorn factory)."""
    settings = load_settings(env_file).require_model()
    return create_app(settings=settings)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--env-file', help='Defaults to the project .env')
    p.add_argument('--bundle')
    p.add_argument('--sha256', help='Trusted bundle.json hash from training report')
    p.add_argument('--port', type=int)
    p.add_argument('--host')
    a = p.parse_args()
    overrides = {
        'SENTINEL_MODEL_DIR': a.bundle,
        'SENTINEL_BUNDLE_SHA256': a.sha256,
        'SENTINEL_PORT': a.port,
    }
    if a.host:
        overrides['SENTINEL_HOST'] = a.host
    try:
        settings = load_settings(a.env_file, overrides=overrides).require_model()
        app = create_app(settings=settings)
    except ConfigurationError as exc:
        p.error(str(exc))
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s %(message)s')
    uvicorn.run(app, host=settings.host, port=settings.port, access_log=False, proxy_headers=True)


if __name__=='__main__':
    main()
