"""Isolated native development cluster. Never resets existing data.
Credentials stay in private .runtime/postgres.env; existing .env is untouched.
"""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sentinel.config import ROOT, read_env
from sentinel.local_setup import protect_file
import psycopg
from sqlalchemy.engine import make_url

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('action', choices=['start', 'stop'])
p.add_argument('--bin', type=Path, required=True)
a = p.parse_args()
runtime = ROOT / '.runtime'
runtime.mkdir(exist_ok=True)
data = runtime / 'postgres-phase2'
credentials = runtime / 'postgres.env'


def run(program, *args):
    result = subprocess.run([str(a.bin / (program + ('.exe' if os.name == 'nt' else ''))), *map(str, args)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode:
        raise SystemExit(program + ' failed; inspect local PostgreSQL logs. Existing data was not reset.')


if a.action == 'stop':
    run('pg_ctl', '-D', data, '-m', 'fast', '-w', 'stop')
    print('Isolated PostgreSQL stopped; data retained.')
else:
    if not data.exists():
        if credentials.exists():
            raise SystemExit('Credential file already exists without cluster; investigate manually.')
        credentials.touch(mode=0o600)
        protect_file(credentials)
        password = secrets.token_urlsafe(32)
        credentials.write_text('DATABASE_URL=postgresql+psycopg://meridian_local:' + password + '@127.0.0.1:55432/meridian_dev\n', encoding='utf-8')
        pwfile = runtime / 'postgres-init-password'
        pwfile.touch(mode=0o600)
        protect_file(pwfile)
        try:
            pwfile.write_text(password, encoding='utf-8')
            run('initdb', '-D', data, '-U', 'meridian_local', '--pwfile', pwfile, '--auth=scram-sha-256', '--encoding=UTF8', '--locale=C')
        finally:
            pwfile.unlink(missing_ok=True)
        with (data / 'postgresql.conf').open('a') as f:
            f.write("\nlisten_addresses = '127.0.0.1'\nport = 55432\n")
    # A retained PID file after shutdown/crash/move is not proof of a live server.
    status = subprocess.run([str(a.bin / ('pg_ctl.exe' if os.name == 'nt' else 'pg_ctl')),
                             '-D', str(data), 'status'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if status.returncode != 0:
        run('pg_ctl', '-D', data, '-l', runtime / 'postgres-phase2.log', '-w', 'start')
    url = make_url(read_env(credentials)['DATABASE_URL'])
    with psycopg.connect(host=url.host, port=url.port, user=url.username, password=url.password, dbname='postgres', connect_timeout=3, autocommit=True) as conn:
        if not conn.execute('SELECT 1 FROM pg_database WHERE datname=%s', ('meridian_dev',)).fetchone():
            conn.execute('CREATE DATABASE meridian_dev')
    print('Isolated PostgreSQL ready on loopback port 55432. Private URL: .runtime/postgres.env')

