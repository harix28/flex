"""Initialize a private local .env without displaying credentials."""
import os
from pathlib import Path
import secrets
import subprocess
from .config import ROOT, TRUSTED_FD001_SHA256, ConfigurationError, load_settings, read_env


def protect_file(path):
    if os.name == 'nt':
        # The path is passed as an environment value, not interpolated into code.
        script = """
        $ErrorActionPreference = 'Stop'
        $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $acl = New-Object System.Security.AccessControl.FileSecurity
        $acl.SetAccessRuleProtection($true, $false)
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', 'Allow')
        $acl.AddAccessRule($rule)
        [System.IO.File]::SetAccessControl($env:SENTINEL_PRIVATE_FILE, $acl)
        """
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                                env={**os.environ, 'SENTINEL_PRIVATE_FILE': str(path)},
                                capture_output=True)
        if result.returncode:
            raise ConfigurationError('Could not restrict local environment file permissions')
    else:
        path.chmod(0o600)


def initialize(path=ROOT / '.env'):
    path = Path(path)
    if not path.exists():
        # Create empty, restrict permissions, then write credentials.
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    protect_file(path)
    values = read_env(path)
    effective_key = os.environ.get('SENTINEL_API_KEY', values.get('SENTINEL_API_KEY', ''))
    additions = []
    if not effective_key and 'SENTINEL_API_KEY' not in os.environ:
        lines = path.read_text(encoding='utf-8-sig').splitlines()
        lines = [line for line in lines if line.partition('=')[0].strip() != 'SENTINEL_API_KEY']
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        additions.append('SENTINEL_API_KEY=' + secrets.token_urlsafe(32))
    defaults = {'SENTINEL_MODEL_DIR': 'runs/fd001-v1',
                'SENTINEL_BUNDLE_SHA256': TRUSTED_FD001_SHA256,
                'SENTINEL_PORT': '8000', 'SENTINEL_HOST': '127.0.0.1'}
    for key, value in defaults.items():
        if key not in values:
            additions.append(f'{key}={value}')
    if additions:
        with path.open('a', encoding='utf-8') as stream:
            stream.write('\n' + '\n'.join(additions) + '\n')
    return load_settings(path).require_model()


def main():
    try:
        initialize()
    except (ConfigurationError, OSError):
        raise SystemExit('Local setup failed: check .env fields, permissions and model directory; credentials were not printed') from None
    print('Local configuration ready. Server and replay read the same private .env; process environment overrides it.')


if __name__ == '__main__':
    main()
