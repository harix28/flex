"""Local configuration: explicit overrides > process environment > .env > defaults."""
from dataclasses import dataclass, field
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TRUSTED_FD001_SHA256 = '06d46a9c4f5f71aeb220ade135e52e713a0bd41f362e7caf00eda743442e7cfd'


class ConfigurationError(ValueError):
    """Messages name invalid fields, never their values."""


def read_env(path):
    """Small literal KEY=value format. No expansion, execution or inline comments."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding='utf-8-sig').splitlines()
    except (OSError, UnicodeError):
        raise ConfigurationError('Cannot read local environment file') from None
    values = {}
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key) or key in values:
            raise ConfigurationError(f'Invalid or duplicate environment assignment on line {number}')
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ConfigurationError(f'Unclosed environment quote on line {number}')
            value = value[1:-1]
        values[key] = value
    return values


def validate_api_key(value):
    if not isinstance(value, str) or not 24 <= len(value) <= 256 or not re.fullmatch(r'[!-~]+', value):
        raise ConfigurationError('SENTINEL_API_KEY must contain 24–256 printable ASCII characters without spaces')
    if value.lower().startswith(('replace', 'change', 'your-secret')):
        raise ConfigurationError('Replace the SENTINEL_API_KEY placeholder with a generated secret')
    return value


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    model_dir: Path | None = None
    bundle_sha256: str = ''
    port: int = 8000
    host: str = '127.0.0.1'
    database_url: str = field(default='', repr=False)
    auth_enabled: bool = False
    auth_localhost: bool = False
    auth_origins: tuple[str, ...] = ()
    session_seconds: int = 28800
    login_limit: int = 10
    login_window: int = 300
    login_global_limit: int = 100
    container_mode: bool = False
    classifier_dir: Path | None = None


    def __post_init__(self):
        validate_api_key(self.api_key)
        validate_auth_settings(self)
        if self.database_url:
            validate_database_url(self.database_url)
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ConfigurationError('SENTINEL_PORT must be an integer from 1 to 65535')
        if self.container_mode:
            if self.host not in ('127.0.0.1', '0.0.0.0'):
                raise ConfigurationError('SENTINEL_HOST must be 127.0.0.1 or 0.0.0.0 in container mode')
        else:
            if self.host != '127.0.0.1':
                raise ConfigurationError('SENTINEL_HOST must be 127.0.0.1 for this local experiment')
        if self.model_dir is not None:
            if not isinstance(self.model_dir, Path) or not self.model_dir.is_dir():
                raise ConfigurationError('SENTINEL_MODEL_DIR must identify an existing directory')
            if not re.fullmatch(r'[0-9a-f]{64}', self.bundle_sha256):
                raise ConfigurationError('SENTINEL_BUNDLE_SHA256 must be a trusted 64-character lowercase SHA256')
        elif self.bundle_sha256:
            raise ConfigurationError('SENTINEL_MODEL_DIR is required with SENTINEL_BUNDLE_SHA256')

    def require_model(self):
        if self.model_dir is None:
            raise ConfigurationError('SENTINEL_MODEL_DIR and SENTINEL_BUNDLE_SHA256 are required to start the server')
        return self


def load_settings(env_file=None, environ=None, overrides=None):
    path = Path(env_file) if env_file is not None else ROOT / '.env'
    values = read_env(path)
    values.update(os.environ if environ is None else environ)
    values.update({k: v for k, v in (overrides or {}).items() if v is not None})
    try:
        port = int(values.get('SENTINEL_PORT', '8000'))
    except (TypeError, ValueError):
        raise ConfigurationError('SENTINEL_PORT must be an integer from 1 to 65535') from None
    directory = values.get('SENTINEL_MODEL_DIR', '')
    bundle_sha256 = values.get('SENTINEL_BUNDLE_SHA256', '')
    pointer_path = values.get('SENTINEL_RELEASE_POINTER', '')
    if pointer_path:
        # Explicit mode works with --env-file too and never mixes pointer/config identities.
        try:
            import json
            from sqlalchemy import create_engine, text
            pointer = Path(pointer_path)
            if not pointer.is_absolute():
                pointer = path.resolve().parent / pointer
            rel_data = json.loads(pointer.read_text(encoding='utf-8'))
            engine = create_engine(validate_database_url(values.get('DATABASE_URL', '')),
                                   hide_parameters=True, connect_args={'connect_timeout': 3})
            try:
                with engine.connect() as connection:
                    release = connection.execute(text("""SELECT d.id,d.model_version,m.bundle_digest
                        FROM model_deployments d JOIN models m ON m.id=d.model_id
                        WHERE d.target_environment='local' AND d.status IN ('desired','active')
                        ORDER BY d.created_at DESC LIMIT 1""")).mappings().first()
                if (not release or str(release['id']) != rel_data.get('deployment_id')
                        or release['model_version'] != rel_data.get('desired_version')
                        or release['bundle_digest'] != rel_data.get('bundle_digest')
                        or rel_data.get('target_environment') != 'local'):
                    raise ValueError('Release pointer differs from committed deployment')
            finally:
                engine.dispose()
            directory = rel_data['model_dir']
            bundle_sha256 = rel_data['bundle_digest']
        except Exception:
            raise ConfigurationError('Release pointer unavailable or inconsistent; run sync-release-pointer before restart') from None
    model_dir = Path(directory) if directory else None
    if model_dir is not None and not model_dir.is_absolute():
        model_dir = (path.resolve().parent / model_dir).resolve()
    return Settings(api_key=values.get('SENTINEL_API_KEY', ''), model_dir=model_dir,
                    bundle_sha256=bundle_sha256, port=port,
                    host=values.get('SENTINEL_HOST', '127.0.0.1'),
                    database_url=values.get('DATABASE_URL', ''),
                    auth_enabled=env_bool(values, 'SENTINEL_AUTH_ENABLED'),
                    auth_localhost=env_bool(values, 'SENTINEL_AUTH_LOCALHOST'),
                    auth_origins=tuple(x.strip() for x in values.get('SENTINEL_AUTH_ORIGINS', '').split(',') if x.strip()),
                    session_seconds=env_int(values, 'SENTINEL_SESSION_SECONDS', 28800),
                    login_limit=env_int(values, 'SENTINEL_LOGIN_LIMIT', 10),
                    login_window=env_int(values, 'SENTINEL_LOGIN_WINDOW', 300),
                    login_global_limit=env_int(values, 'SENTINEL_LOGIN_GLOBAL_LIMIT', 100),
                    container_mode=env_bool(values, 'SENTINEL_CONTAINER_MODE'),
                    classifier_dir=Path(values['SENTINEL_CLASSIFIER_DIR']) if values.get('SENTINEL_CLASSIFIER_DIR') else None)


def validate_database_url(value):
    from sqlalchemy.engine import make_url
    try:
        url = make_url(value)
        if (url.drivername != 'postgresql+psycopg' or not url.host or not url.database
                or not url.username or url.query or ',' in url.host):
            raise ValueError()
        _ = url.port
    except Exception:
        raise ConfigurationError('DATABASE_URL must be a postgresql+psycopg URL with host, database and user; query options are not supported') from None
    return url


def load_database_url(env_file=None):
    values = read_env(Path(env_file) if env_file else ROOT / '.env')
    value = os.environ.get('DATABASE_URL', values.get('DATABASE_URL', ''))
    validate_database_url(value)
    return value


def env_bool(values, name):
    value = values.get(name, 'false')
    if value not in ('true', 'false'):
        raise ConfigurationError(name + ' must be true or false')
    return value == 'true'


def env_int(values, name, default):
    try:
        return int(values.get(name, default))
    except (ValueError, TypeError):
        raise ConfigurationError(name + ' must be an integer') from None


def validate_auth_settings(settings):
    from urllib.parse import urlsplit
    if type(settings.auth_enabled) is not bool or type(settings.auth_localhost) is not bool:
        raise ConfigurationError('Authentication flags must be booleans')
    for field, lower, upper in (('session_seconds', 60, 86400), ('login_limit', 1, 100),
                                ('login_window', 1, 3600), ('login_global_limit', 1, 1000)):
        value = getattr(settings, field)
        if type(value) is not int or not lower <= value <= upper:
            raise ConfigurationError('Invalid authentication limit: ' + field)
    if settings.auth_enabled and (not settings.database_url or not settings.auth_origins):
        raise ConfigurationError('Authentication requires DATABASE_URL and SENTINEL_AUTH_ORIGINS')
    for origin in settings.auth_origins:
        try:
            parsed = urlsplit(origin)
            if (parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username
                    or parsed.password or parsed.path or parsed.query or parsed.fragment or '*' in origin
                    or parsed.hostname != parsed.hostname.lower() or parsed.port == 0):
                raise ValueError()
            if settings.auth_localhost:
                if parsed.hostname not in ('localhost','127.0.0.1','::1'):
                    raise ValueError()
            elif parsed.scheme != 'https':
                raise ValueError()
        except ValueError:
            raise ConfigurationError('Invalid SENTINEL_AUTH_ORIGINS; use exact HTTPS origins or explicit localhost development') from None
