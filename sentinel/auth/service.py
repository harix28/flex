"""Transactional identity operations shared by HTTP and explicit operator CLI."""
from uuid import uuid4
from sqlalchemy import text
from fastapi import HTTPException
from .security import normalize_email, hash_password


def audit(session, action, request_id, actor=None, tenant=None, target=None):
    session.execute(text("""INSERT INTO auth_audit_events(action,request_id,actor_id,tenant_id,target_user_id)
      VALUES (:action,:request,:actor,:tenant,:target)"""),
      dict(action=action, request=request_id, actor=actor, tenant=tenant, target=target))


def create_user(session, email, password, name):
    email = normalize_email(email)
    if not name.strip() or len(name) > 120:
        raise ValueError('Display name must contain 1 to 120 characters')
    uid = uuid4()
    session.execute(text("""INSERT INTO users(id,oidc_issuer,oidc_subject,display_name,email,password_hash)
      VALUES (:id,'urn:meridian:local',:subject,:name,:email,:password_hash)"""),
      dict(id=uid,subject=str(uid),name=name.strip(),email=email,password_hash=hash_password(password)))
    return uid


def bootstrap(database, slug, organization, email, password, name):
    import re
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,62}', slug) or not organization.strip() or len(organization) > 120:
        raise ValueError('Invalid organization name or slug')
    with database.transaction() as s:
        tenant = s.execute(text('INSERT INTO tenants(name,slug) VALUES (:name,:slug) RETURNING id'),
                           dict(name=organization.strip(),slug=slug)).scalar_one()
        uid = create_user(s,email,password,name)
        s.execute(text("INSERT INTO memberships(tenant_id,user_id,roles) VALUES (:tenant,:user,ARRAY['admin'])"),dict(tenant=tenant,user=uid))
        audit(s,'bootstrap',uuid4(),actor=uid,tenant=tenant,target=uid)
    return tenant, uid


def lock_tenant(session, tenant_id):
    if session.execute(text('SELECT id FROM tenants WHERE id=:id FOR UPDATE'),dict(id=tenant_id)).scalar_one_or_none() is None:
        raise HTTPException(404,'not_found')


def ensure_admin_remains(session, tenant_id, user_id):
    current = session.execute(text("""SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id
      WHERE m.tenant_id=:tenant AND m.user_id=:user AND m.active AND u.active AND u.password_hash IS NOT NULL AND 'admin'=ANY(m.roles)"""),
      dict(tenant=tenant_id,user=user_id)).first()
    if current and not session.execute(text("""SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id
      WHERE m.tenant_id=:tenant AND m.user_id<>:user AND m.active AND u.active AND u.password_hash IS NOT NULL AND 'admin'=ANY(m.roles)"""),
      dict(tenant=tenant_id,user=user_id)).first():
        raise HTTPException(409,'last_admin')


def disable_user(database, email):
    # Lock ALL tenant rows in stable order before the user to serialize with membership edits.
    with database.transaction() as s:
        s.execute(text('SELECT id FROM tenants ORDER BY id FOR UPDATE')).all()
        uid = s.execute(text('SELECT id FROM users WHERE email=:email FOR UPDATE'),dict(email=normalize_email(email))).scalar_one()
        for tenant in s.execute(text('SELECT tenant_id FROM memberships WHERE user_id=:id AND active ORDER BY tenant_id'),dict(id=uid)).scalars():
            ensure_admin_remains(s,tenant,uid)
        s.execute(text('UPDATE users SET active=false WHERE id=:id'),dict(id=uid))
        audit(s,'user_disabled',uuid4(),target=uid)


def reset_password(database, email, password):
    encoded = hash_password(password)
    with database.transaction() as s:
        uid = s.execute(text('UPDATE users SET password_hash=:hash WHERE email=:email RETURNING id'),
          dict(hash=encoded,email=normalize_email(email))).scalar_one()
        audit(s,'password_changed',uuid4(),target=uid)
