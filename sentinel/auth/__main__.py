"""Explicit local operator provisioning. Passwords accepted only through hidden prompts."""
import argparse
import getpass
import sys
from uuid import uuid4
from sentinel.config import load_database_url
from sentinel.db import Database
from .service import bootstrap, create_user, disable_user, reset_password, audit


def password_prompt():
    if not sys.stdin.isatty():
        raise ValueError('Interactive terminal required for hidden password entry')
    value = getpass.getpass('Password (12-128 characters): ')
    if value != getpass.getpass('Confirm password: '):
        raise ValueError('Passwords do not match')
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['bootstrap','create-user','disable-user','reset-password'])
    p.add_argument('--env-file')
    a = p.parse_args()
    database = None
    try:
        database = Database(load_database_url(a.env_file))
        if not database.ready():
            raise ValueError('Database unavailable or migration required')
        email = input('Email: ').strip()
        if a.action == 'bootstrap':
            slug = input('Organization slug (unique): ').strip()
            org = input('Organization name: ').strip()
            name = input('Administrator display name: ').strip()
            tenant, uid = bootstrap(database,slug,org,email,password_prompt(),name)
            print('Organization ID:',tenant,'User ID:',uid)
        elif a.action == 'create-user':
            name = input('Display name: ').strip()
            password = password_prompt()
            with database.transaction() as s:
                uid = create_user(s,email,password,name)
                audit(s,'user_created',uuid4(),target=uid)
            print('User ID:',uid,'(no organization membership; assign through an organization administrator)')
        elif a.action == 'disable-user':
            disable_user(database,email)
        else:
            reset_password(database,email,password_prompt())
    except Exception:
        p.exit(1,'Identity operation failed. Check input, uniqueness, last-admin protection, private configuration and migrations. No secrets printed.\n')
    finally:
        if database:
            database.close()
    print('Identity operation completed.')


if __name__ == '__main__':
    main()
