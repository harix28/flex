"""HTTP auth tests with real PostgreSQL; each test owns a disposable database."""
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from alembic import command
from sentinel.api import create_app
from sentinel.config import Settings
from sentinel.db import REVISION
from sentinel.auth.security import new_token, digest, HASHER, verify_password
from sentinel.auth.service import bootstrap, create_user, reset_password, disable_user
from tests.test_api import KEY
from tests.test_postgres import db, assets

pytestmark=pytest.mark.postgres
ORIGIN='http://127.0.0.1:8000'
LOGIN_HEADERS={'Origin':ORIGIN,'X-CSRF-Protection':'1'}

@pytest.fixture
def setup(db):
    database,config=db
    password=new_token()
    a,admin=bootstrap(database,'org-a','Organization A','admin-a@example.com',password,'Admin A')
    b,admin_b=bootstrap(database,'org-b','Organization B','admin-b@example.com',password,'Admin B')
    users={'admin':admin,'admin_b':admin_b}
    members={}
    with database.transaction() as s:
        for role in ('viewer','technician','plant_manager'):
            uid=create_user(s,role+'@example.com',password,role)
            users[role]=uid
            members[role]=s.execute(text('INSERT INTO memberships(tenant_id,user_id,roles) VALUES (:t,:u,:r) RETURNING id'),dict(t=a,u=uid,r=[role])).scalar_one()
        members['admin']=s.execute(text('SELECT id FROM memberships WHERE user_id=:id'),dict(id=admin)).scalar_one()
        members['admin_b']=s.execute(text('SELECT id FROM memberships WHERE user_id=:id'),dict(id=admin_b)).scalar_one()
    settings=Settings(KEY,database_url=config.attributes['database_url'],auth_enabled=True,auth_localhost=True,
                      auth_origins=(ORIGIN,),login_limit=100,login_global_limit=1000)
    return dict(database=database,config=config,password=password,a=a,b=b,users=users,members=members,settings=settings)


def client_for(setup,**changes):
    return TestClient(create_app(settings=replace(setup['settings'],**changes)),base_url=ORIGIN)


def login(client,setup,email='admin-a@example.com'):
    r=client.post('/api/v1/auth/login',json={'email':email,'password':setup['password']},headers=LOGIN_HEADERS)
    assert r.status_code==200
    return {'Origin':ORIGIN,'X-CSRF-Token':r.json()['csrf_token']}


def test_login_me_hashes_cookies_and_audit(setup):
    with client_for(setup) as c:
        headers=login(c,setup,' ADMIN-A@EXAMPLE.COM ')
        token=c.cookies.get('meridian_session')
        r=c.get('/api/v1/auth/me')
        assert r.status_code==200 and r.json()['user']['id']==str(setup['users']['admin'])
        assert [x['id'] for x in r.json()['organizations']]==[str(setup['a'])]
        assert setup['password'] not in r.text and token not in r.text
        with setup['database'].transaction() as s:
            row=s.execute(text('SELECT token_hash,csrf_hash FROM auth_sessions')).one()
            assert row.token_hash==digest(token) and row.csrf_hash==digest(headers['X-CSRF-Token'])
            actions=s.execute(text('SELECT action FROM auth_audit_events')).scalars().all()
            assert 'login_success' in actions
            hashed=s.execute(text('SELECT password_hash FROM users WHERE id=:id'),dict(id=setup['users']['admin'])).scalar_one()
            assert hashed.startswith('$argon2id$') and setup['password'] not in hashed


def test_failure_errors_equal_and_no_secrets_in_logs(setup,caplog):
    import logging
    caplog.set_level(logging.INFO, logger='sentinel.http')
    with client_for(setup) as c:
        bodies=[]
        for email in ('admin-a@example.com','absent@example.com','not-an-email'):
            r=c.post('/api/v1/auth/login',json={'email':email,'password':'wrong-password-marker'},headers=LOGIN_HEADERS)
            assert r.status_code==401
            bodies.append(r.json()['error'])
            assert email not in r.text and 'wrong-password-marker' not in r.text
        assert bodies[0]==bodies[1]==bodies[2]=={'code':'invalid_credentials'}
        assert 'wrong-password-marker' not in caplog.text and setup['password'] not in caplog.text
        with setup['database'].transaction() as s:
            assert s.execute(text("SELECT count(*) FROM auth_audit_events WHERE action='login_failure'")).scalar_one()==3


def test_disabled_and_no_membership_users_cannot_login(setup):
    with setup['database'].transaction() as s:
        s.execute(text('UPDATE users SET active=false WHERE id=:id'),dict(id=setup['users']['viewer']))
        create_user(s,'unassigned@example.com',setup['password'],'Unassigned')
    with client_for(setup) as c:
        for email in ('viewer@example.com','unassigned@example.com'):
            r=c.post('/api/v1/auth/login',json={'email':email,'password':setup['password']},headers=LOGIN_HEADERS)
            assert r.status_code==401 and r.json()['error']['code']=='invalid_credentials'


def test_csrf_login_and_mutations_fail_closed(setup):
    with client_for(setup) as c:
        for headers in ({},{'Origin':'https://evil.example','X-CSRF-Protection':'1'},{'Origin':ORIGIN},
                        {**LOGIN_HEADERS,'Sec-Fetch-Site':'cross-site'}):
            assert c.post('/api/v1/auth/login',json={'email':'admin-a@example.com','password':setup['password']},headers=headers).status_code==403
        valid=login(c,setup)
        for headers in ({},{'Origin':ORIGIN,'X-CSRF-Token':'wrong'}, {**valid,'Origin':'https://evil.example'}):
            assert c.post('/api/v1/auth/logout',headers=headers).status_code==403
        assert c.get('/api/v1/auth/me').status_code==200
        assert c.get('/api/v1/auth/csrf').status_code==403
        fresh=c.get('/api/v1/auth/csrf',headers=LOGIN_HEADERS)
        assert fresh.status_code==200
        assert c.post('/api/v1/auth/logout',headers=valid).status_code==403
        assert c.post('/api/v1/auth/logout',headers={'Origin':ORIGIN,'X-CSRF-Token':fresh.json()['csrf_token']}).status_code==200


def test_logout_expiry_revocation_and_rotation(setup):
    with client_for(setup) as c:
        first=login(c,setup)
        old=c.cookies.get('meridian_session')
        headers=login(c,setup)
        new=c.cookies.get('meridian_session')
        assert new != old
        c.cookies.set('meridian_session',old,domain='127.0.0.1',path='/')
        assert c.get('/api/v1/auth/me').status_code==401
        c.cookies.set('meridian_session',new,domain='127.0.0.1',path='/')
        assert c.post('/api/v1/auth/logout',headers=headers).status_code==200
        c.cookies.set('meridian_session',new,domain='127.0.0.1',path='/')
        assert c.get('/api/v1/auth/me').status_code==401
        login(c,setup)
        with setup['database'].transaction() as s:
            s.execute(text("UPDATE auth_sessions SET created_at=now()-interval '2 days',expires_at=now()-interval '1 day'"))
        assert c.get('/api/v1/auth/me').status_code==401


def test_password_change_revokes_all_sessions_and_requires_current_password(setup):
    with client_for(setup) as c,client_for(setup) as other:
        headers=login(c,setup)
        login(other,setup)
        new_password=new_token()
        assert c.post('/api/v1/auth/password',headers=headers,json={'current_password':'wrong','new_password':new_password}).status_code==401
        assert other.get('/api/v1/auth/me').status_code==200
        assert c.post('/api/v1/auth/password',headers=headers,json={'current_password':setup['password'],'new_password':new_password}).status_code==200
        assert other.get('/api/v1/auth/me').status_code==401
        assert c.get('/api/v1/auth/me').status_code==401
        assert c.post('/api/v1/auth/login',headers=LOGIN_HEADERS,json={'email':'admin-a@example.com','password':setup['password']}).status_code==401
        setup['password']=new_password
        login(c,setup)


def test_operator_password_reset_and_disable_revoke_sessions(setup):
    with client_for(setup) as c:
        login(c,setup,'viewer@example.com')
        reset_password(setup['database'],'viewer@example.com',setup['password'])
        assert c.get('/api/v1/auth/me').status_code==401
        login(c,setup,'viewer@example.com')
        disable_user(setup['database'],'viewer@example.com')
        assert c.get('/api/v1/auth/me').status_code==401
        with pytest.raises(Exception):
            disable_user(setup['database'],'admin-a@example.com')
        with setup['database'].transaction() as s:
            assert s.execute(text('SELECT active FROM users WHERE id=:id'),dict(id=setup['users']['admin'])).scalar_one()


@pytest.mark.parametrize('role',['viewer','technician','plant_manager'])
def test_role_permissions_and_forged_organization_ids(setup,role):
    with client_for(setup) as c:
        headers=login(c,setup,role+'@example.com')
        assert c.get(f"/api/v1/organizations/{setup['a']}").status_code==200
        assert c.get(f"/api/v1/organizations/{setup['b']}").status_code==404
        assert c.get(f"/api/v1/organizations/{setup['a']}/members").status_code==403
        assert c.post(f"/api/v1/organizations/{setup['a']}/members",headers=headers,json={'user_id':str(setup['users']['admin_b']),'roles':['admin']}).status_code==403


def test_admin_cross_tenant_reads_writes_and_mass_assignment(setup):
    with client_for(setup) as c:
        headers=login(c,setup)
        assert c.get(f"/api/v1/organizations/{setup['b']}/members").status_code==404
        for tenant,member in ((setup['b'],setup['members']['admin_b']),(setup['a'],setup['members']['admin_b'])):
            assert c.patch(f'/api/v1/organizations/{tenant}/members/{member}',headers=headers,json={'roles':['viewer']}).status_code==404
            assert c.delete(f'/api/v1/organizations/{tenant}/members/{member}',headers=headers).status_code==404
        path=f"/api/v1/organizations/{setup['a']}/members/{setup['members']['viewer']}"
        for payload in ({'roles':['platform_admin']},{'roles':['manager']},{'roles':['admin','admin']},
                        {'roles':['admin'],'tenant_id':str(setup['b'])},{'roles':['admin'],'active':'true'}):
            assert c.patch(path,headers=headers,json=payload).status_code==422
        with setup['database'].transaction() as s:
            assert s.execute(text('SELECT roles FROM memberships WHERE id=:id'),dict(id=setup['members']['admin_b'])).scalar_one()==['admin']


def test_add_existing_user_role_changes_and_removal_are_immediate(setup):
    with client_for(setup) as admin,client_for(setup) as member:
        ah=login(admin,setup)
        mh=login(member,setup,'viewer@example.com')
        base=f"/api/v1/organizations/{setup['a']}/members"
        target=f"{base}/{setup['members']['viewer']}"
        assert admin.patch(target,headers=ah,json={'roles':['admin']}).status_code==200
        assert member.get(base).status_code==200
        assert admin.patch(target,headers=ah,json={'roles':['viewer']}).status_code==200
        assert member.get(base).status_code==403
        assert admin.delete(target,headers=ah).status_code==200
        assert member.get(f"/api/v1/organizations/{setup['a']}").status_code==404
        assert member.get('/api/v1/auth/me').json()['organizations']==[]
        r=admin.post(base,headers=ah,json={'user_id':str(setup['users']['admin_b']),'roles':['viewer']})
        assert r.status_code==201
        assert admin.post(base,headers=ah,json={'user_id':str(setup['users']['admin_b']),'roles':['viewer']}).status_code==409
        assert admin.post(base,headers=ah,json={'user_id':str(uuid4()),'roles':['viewer']}).status_code==404
        with setup['database'].transaction() as s:
            actions=s.execute(text('SELECT action FROM auth_audit_events WHERE tenant_id=:id'),dict(id=setup['a'])).scalars().all()
            assert all(action in actions for action in ('membership_changed','membership_disabled','membership_added'))


def test_last_admin_and_failed_membership_change_roll_back(setup):
    with client_for(setup) as c:
        headers=login(c,setup)
        target=f"/api/v1/organizations/{setup['a']}/members/{setup['members']['admin']}"
        for method,payload in (('patch',{'roles':['viewer']}),('patch',{'roles':['admin'],'active':False}),('delete',None)):
            r=c.request(method,target,headers=headers,**({'json':payload} if payload else {}))
            assert r.status_code==409 and r.json()['error']['code']=='last_admin'
        with setup['database'].transaction() as s:
            row=s.execute(text('SELECT roles,active FROM memberships WHERE id=:id'),dict(id=setup['members']['admin'])).one()
            assert row.roles==['admin'] and row.active
            assert s.execute(text("SELECT count(*) FROM auth_audit_events WHERE action LIKE 'membership_%'")).scalar_one()==0


def test_login_rate_limit_audited_and_proxy_headers_do_not_bypass(setup):
    with client_for(setup,login_limit=2) as c:
        for i in range(2):
            assert c.post('/api/v1/auth/login',headers={**LOGIN_HEADERS,'X-Forwarded-For':str(i)},json={'email':'admin-a@example.com','password':'wrong'}).status_code==401
        r=c.post('/api/v1/auth/login',headers={**LOGIN_HEADERS,'X-Forwarded-For':'new-address'},json={'email':'admin-a@example.com','password':setup['password']})
        assert r.status_code==429 and r.headers['retry-after']=='300'
        with setup['database'].transaction() as s:
            assert s.execute(text("SELECT count(*) FROM auth_audit_events WHERE action='login_rate_limited'")).scalar_one()==1


def test_safe_hash_upgrade_revokes_old_sessions(setup):
    from argon2 import PasswordHasher,Type
    old=PasswordHasher(time_cost=2,memory_cost=32768,parallelism=2,type=Type.ID).hash(setup['password'])
    with setup['database'].transaction() as s:
        s.execute(text('UPDATE users SET password_hash=:hash WHERE id=:id'),dict(hash=old,id=setup['users']['admin']))
    with client_for(setup) as c:
        login(c,setup)
        with setup['database'].transaction() as s:
            upgraded=s.execute(text('SELECT password_hash FROM users WHERE id=:id'),dict(id=setup['users']['admin'])).scalar_one()
            assert upgraded!=old and not HASHER.check_needs_rehash(upgraded)
            assert verify_password(upgraded,setup['password'])
        assert c.get('/api/v1/auth/me').status_code==200


def test_secure_cookies_cors_and_key_not_application_identity(setup):
    settings=replace(setup['settings'],auth_localhost=False,auth_origins=('https://app.example.com',))
    with TestClient(create_app(settings=settings),base_url='https://app.example.com') as c:
        r=c.post('/api/v1/auth/login',headers={'Origin':'https://app.example.com','X-CSRF-Protection':'1'},json={'email':'admin-a@example.com','password':setup['password']})
        assert r.status_code==200
        cookie=r.headers['set-cookie']
        assert '__Host-meridian_session=' in cookie and 'Secure' in cookie and 'HttpOnly' in cookie and 'SameSite=lax' in cookie and 'Domain=' not in cookie
        assert c.get('/api/v1/auth/me').status_code==200
        preflight=c.options('/api/v1/auth/login',headers={'Origin':'https://evil.example','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'X-CSRF-Protection'})
        assert preflight.status_code==400 and 'access-control-allow-origin' not in preflight.headers
        good=c.options('/api/v1/auth/login',headers={'Origin':'https://app.example.com','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'X-CSRF-Protection'})
        assert good.headers['access-control-allow-origin']=='https://app.example.com'
    with client_for(setup) as c:
        assert c.get('/api/v1/auth/me',headers={'X-API-Key':KEY}).status_code==401
        assert c.get('/api/v1/auth/me').status_code==401
    with TestClient(create_app(settings=settings),base_url='http://app.example.com') as c:
        assert c.get('/api/v1/auth/me').status_code==403


def test_bootstrap_duplicate_and_email_uniqueness_atomic(setup):
    database=setup['database']
    for slug,email in (('org-a','another@example.com'),('other-org','ADMIN-A@EXAMPLE.COM')):
        with pytest.raises(IntegrityError):
            bootstrap(database,slug,'Another',email,setup['password'],'Another')
    with database.transaction() as s:
        assert s.execute(text('SELECT count(*) FROM tenants')).scalar_one()==2
        assert s.execute(text('SELECT count(*) FROM users')).scalar_one()==5


def test_migration_upgrade_from_populated_phase2_preserves_records(db):
    database,config=db
    command.downgrade(config,'0001_registry')
    tid,machine,sensor=assets(database)
    with database.transaction() as s:
        uid=s.execute(text("INSERT INTO users(oidc_issuer,oidc_subject,display_name) VALUES ('issuer','subject','Legacy') RETURNING id")).scalar_one()
        s.execute(text("INSERT INTO memberships(tenant_id,user_id,roles) VALUES (:t,:u,ARRAY['manager'])"),dict(t=tid,u=uid))
    command.upgrade(config,'head')
    assert database.ready()
    with database.transaction() as s:
        assert s.execute(text('SELECT roles FROM memberships WHERE user_id=:u'),dict(u=uid)).scalar_one()==['plant_manager']
        assert s.execute(text('SELECT email FROM users WHERE id=:u'),dict(u=uid)).scalar_one() is None
        assert s.execute(text('SELECT id FROM machines')).scalar_one()==machine
        assert s.execute(text('SELECT id FROM sensors')).scalar_one()==sensor
        assert s.execute(text('SELECT version_num FROM alembic_version')).scalar_one()==REVISION


def test_session_foreign_key_and_email_database_constraints(setup):
    for sql,values in [
      ("INSERT INTO users(oidc_issuer,oidc_subject,display_name,email) VALUES ('x','x','x','UPPER@example.com')",{}),
      ("INSERT INTO auth_sessions(user_id,token_hash,csrf_hash,expires_at) VALUES (:id,:hash,:hash,now()+interval '1 hour')",{'id':uuid4(),'hash':digest(new_token())})]:
        with pytest.raises(IntegrityError):
            with setup['database'].transaction() as s:
                s.execute(text(sql),values)


def test_concurrent_admin_demotions_leave_one_admin(setup):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    with client_for(setup) as first,client_for(setup) as second:
        h1=login(first,setup)
        base=f"/api/v1/organizations/{setup['a']}/members"
        assert first.patch(f"{base}/{setup['members']['viewer']}",headers=h1,json={'roles':['admin']}).status_code==200
        h2=login(second,setup,'viewer@example.com')
        barrier=Barrier(2)
        def demote(client,headers,member):
            barrier.wait(timeout=5)
            return client.patch(f'{base}/{member}',headers=headers,json={'roles':['viewer']}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            one=pool.submit(demote,first,h1,setup['members']['admin'])
            two=pool.submit(demote,second,h2,setup['members']['viewer'])
            assert sorted([one.result(timeout=15),two.result(timeout=15)])==[200,409]
        with setup['database'].transaction() as s:
            assert s.execute(text("SELECT count(*) FROM memberships WHERE tenant_id=:t AND active AND 'admin'=ANY(roles)"),dict(t=setup['a'])).scalar_one()==1


def test_unsupported_legacy_role_aborts_upgrade_without_data_loss(db):
    database,config=db
    command.downgrade(config,'0001_registry')
    with database.transaction() as s:
        tid=s.execute(text("INSERT INTO tenants(name) VALUES ('Legacy') RETURNING id")).scalar_one()
        uid=s.execute(text("INSERT INTO users(oidc_issuer,oidc_subject,display_name) VALUES ('issuer','legacy','Legacy') RETURNING id")).scalar_one()
        s.execute(text("INSERT INTO memberships(tenant_id,user_id,roles) VALUES (:t,:u,ARRAY['ml_engineer'])"),dict(t=tid,u=uid))
    from sqlalchemy.exc import DBAPIError
    with pytest.raises(DBAPIError):
        command.upgrade(config,'head')
    with database.transaction() as s:
        assert s.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0001_registry'
        assert s.execute(text('SELECT roles FROM memberships WHERE user_id=:u'),dict(u=uid)).scalar_one()==['ml_engineer']


def test_bootstrap_cli_hidden_prompts_and_duplicate_protection(db,monkeypatch,capsys):
    import sys
    from sentinel.auth.__main__ import main
    database,config=db
    password=new_token()
    monkeypatch.setenv('DATABASE_URL',config.attributes['database_url'])
    monkeypatch.setattr(sys,'argv',['sentinel.auth','bootstrap'])
    monkeypatch.setattr(sys.stdin,'isatty',lambda:True)
    monkeypatch.setattr('sentinel.auth.__main__.getpass.getpass',lambda prompt:password)
    def run():
        answers=iter(['cli@example.com','cli-org','CLI Organization','CLI Admin'])
        monkeypatch.setattr('builtins.input',lambda prompt:next(answers))
        main()
    run()
    assert password not in capsys.readouterr().out
    with pytest.raises(SystemExit) as error:
        run()
    assert error.value.code==1
    assert password not in capsys.readouterr().err
    with database.transaction() as s:
        assert s.execute(text('SELECT count(*) FROM tenants')).scalar_one()==1
        assert s.execute(text('SELECT count(*) FROM users')).scalar_one()==1
        assert s.execute(text('SELECT roles FROM memberships')).scalar_one()==['admin']


@pytest.mark.parametrize('change',["active=false","password_hash=NULL"])
def test_unusable_admin_does_not_allow_last_usable_admin_removal(setup,change):
    with client_for(setup) as c:
        headers=login(c,setup)
        base=f"/api/v1/organizations/{setup['a']}/members"
        assert c.patch(f"{base}/{setup['members']['viewer']}",headers=headers,json={'roles':['admin']}).status_code==200
        with setup['database'].transaction() as s:
            s.execute(text('UPDATE users SET '+change+' WHERE id=:id'),dict(id=setup['users']['viewer']))
        assert c.delete(f"{base}/{setup['members']['admin']}",headers=headers).status_code==409
