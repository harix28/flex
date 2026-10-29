"""Backend-only local identity and organization membership API."""
from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import text
from .limiter import LoginLimiter
from .context import AuthContext
from .permissions import Role
from .security import HASHER, digest, hash_password, new_token, normalize_email, verify_password
from .service import audit, ensure_admin_remains, lock_tenant


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Login(Input):
    email: str = Field(min_length=1, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)


class MemberChange(Input):
    roles: list[Role] = Field(min_length=1, max_length=4)
    active: bool = Field(default=True, strict=True)

    @field_validator('roles')
    @classmethod
    def unique_roles(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('Duplicate roles')
        return value


class MemberAdd(MemberChange):
    user_id: UUID


class PasswordChange(Input):
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=12, max_length=128)


def auth_router(database, settings):
    router = APIRouter(prefix='/api/v1', tags=['Authentication and organizations'])
    limiter = LoginLimiter(settings.login_limit, settings.login_window, settings.login_global_limit)
    cookie = 'meridian_session' if settings.auth_localhost else '__Host-meridian_session'

    context = AuthContext(database, settings)
    transaction, origin = context.transaction, context.origin
    principal, csrf, membership = context.principal, context.csrf, context.membership

    def organization_list(s, uid):
        return [dict(row) for row in s.execute(text("""SELECT t.id,t.name,t.slug,m.roles
          FROM tenants t JOIN memberships m ON m.tenant_id=t.id
          WHERE m.user_id=:id AND m.active ORDER BY t.id"""),dict(id=uid)).mappings()]

    def envelope(request, **data):
        return dict(data,request_id=request.state.request_id)

    @router.post('/auth/login')
    def login(payload: Login, request: Request, response: Response):
        origin(request)
        if (request.headers.get('x-csrf-protection') != '1' or
            request.headers.get('content-type','').split(';')[0].strip().lower() != 'application/json'):
            raise HTTPException(403,'csrf_failed')
        try:
            email = normalize_email(payload.email)
        except ValueError:
            email = ''
        allowed = limiter.allow(request.client.host if request.client else 'unknown', email)
        failure = None
        with transaction(request) as s:
            if not allowed:
                audit(s,'login_rate_limited',request.state.request_id)
                failure = 429
            else:
                user = s.execute(text('SELECT id,password_hash,active FROM users WHERE email=:email FOR UPDATE'),dict(email=email)).mappings().one_or_none()
                valid = verify_password(user['password_hash'] if user else None, payload.password.get_secret_value())
                organizations = organization_list(s,user['id']) if user else []
                if not valid or not user['active'] or not organizations:
                    audit(s,'login_failure',request.state.request_id)
                    failure = 401
                else:
                    if HASHER.check_needs_rehash(user['password_hash']):
                        s.execute(text('UPDATE users SET password_hash=:hash WHERE id=:id'),
                          dict(hash=hash_password(payload.password.get_secret_value()),id=user['id']))
                    # Rotate: a previous browser session must not survive a replacement login.
                    old = request.cookies.get(cookie,'')
                    if old:
                        s.execute(text('UPDATE auth_sessions SET revoked_at=now() WHERE token_hash=:hash'),dict(hash=digest(old)))
                    token, csrf_token = new_token(), new_token()
                    s.execute(text("""INSERT INTO auth_sessions(user_id,token_hash,csrf_hash,expires_at)
                      VALUES (:user,:token,:csrf,:expiry)"""),dict(user=user['id'],token=digest(token),csrf=digest(csrf_token),
                      expiry=datetime.now(timezone.utc)+timedelta(seconds=settings.session_seconds)))
                    audit(s,'login_success',request.state.request_id,actor=user['id'])
        # Raise only after audit transaction commits. Never return a cookie before commit.
        if failure == 429:
            raise HTTPException(429,'rate_limited',headers={'Retry-After':str(settings.login_window)})
        if failure:
            raise HTTPException(401,'invalid_credentials')
        response.set_cookie(cookie,token,max_age=settings.session_seconds,httponly=True,
                            secure=not settings.auth_localhost,samesite='lax',path='/')
        return envelope(request,csrf_token=csrf_token,organizations=organizations)

    @router.get('/auth/me')
    def me(request: Request):
        with transaction(request) as s:
            actor = principal(s,request)
            return envelope(request,user={'id':actor['user_id'],'email':actor['email'],'display_name':actor['display_name']},
                            organizations=organization_list(s,actor['user_id']))

    @router.get('/auth/csrf')
    def refresh_csrf(request: Request):
        # Recovery after browser reload, no unauthenticated token or URL token.
        origin(request)
        if request.headers.get('x-csrf-protection') != '1':
            raise HTTPException(403,'csrf_failed')
        with transaction(request) as s:
            actor = principal(s,request)
            token = new_token()
            s.execute(text('UPDATE auth_sessions SET csrf_hash=:hash WHERE id=:id'),dict(hash=digest(token),id=actor['session_id']))
        return envelope(request,csrf_token=token)

    @router.post('/auth/logout')
    def logout(request: Request, response: Response):
        with transaction(request) as s:
            actor = principal(s,request)
            csrf(request,actor)
            s.execute(text('UPDATE auth_sessions SET revoked_at=now() WHERE id=:id'),dict(id=actor['session_id']))
            audit(s,'logout',request.state.request_id,actor=actor['user_id'])
        response.delete_cookie(cookie,path='/',secure=not settings.auth_localhost,httponly=True,samesite='lax')
        return envelope(request,status='logged_out')

    @router.post('/auth/password')
    def change_password(payload: PasswordChange, request: Request, response: Response):
        with transaction(request) as s:
            actor = principal(s,request)
            csrf(request,actor)
            stored = s.execute(text('SELECT password_hash FROM users WHERE id=:id FOR UPDATE'),dict(id=actor['user_id'])).scalar_one()
            if not verify_password(stored,payload.current_password.get_secret_value()):
                raise HTTPException(401,'invalid_credentials')
            s.execute(text('UPDATE users SET password_hash=:hash WHERE id=:id'),
                      dict(hash=hash_password(payload.new_password.get_secret_value()),id=actor['user_id']))
            audit(s,'password_changed',request.state.request_id,actor=actor['user_id'],target=actor['user_id'])
        response.delete_cookie(cookie,path='/',secure=not settings.auth_localhost,httponly=True,samesite='lax')
        return envelope(request,status='password_changed_login_required')

    @router.get('/organizations/{tenant_id}')
    def organization(tenant_id: UUID, request: Request):
        with transaction(request) as s:
            actor = principal(s,request)
            member = membership(s,actor,tenant_id,'organization.read')
            tenant = s.execute(text('SELECT id,name,slug FROM tenants WHERE id=:id'),dict(id=tenant_id)).mappings().one()
            return envelope(request,organization=dict(tenant),roles=member['roles'])

    @router.get('/organizations/{tenant_id}/members')
    def members(tenant_id: UUID, request: Request, offset: int = 0):
        if not 0 <= offset <= 100000:
            raise HTTPException(422,'invalid_schema')
        with transaction(request) as s:
            actor = principal(s,request)
            membership(s,actor,tenant_id,'members.manage')
            rows = s.execute(text("""SELECT m.id,m.user_id,m.roles,m.active,u.display_name,u.email,u.active AS user_active
              FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.tenant_id=:tenant
              ORDER BY m.id LIMIT 100 OFFSET :offset"""),dict(tenant=tenant_id,offset=offset)).mappings().all()
            return envelope(request,items=[dict(row) for row in rows],next_offset=offset+100 if len(rows)==100 else None)

    @router.get('/organizations/{tenant_id}/work-order-assignees')
    def work_order_assignees(tenant_id: UUID, request: Request, offset: int = 0):
        if not 0 <= offset <= 100000:
            raise HTTPException(422, 'invalid_schema')
        with transaction(request) as s:
            actor = principal(s, request)
            membership(s, actor, tenant_id, 'work_orders.assign')
            rows = s.execute(text("""SELECT m.id,m.user_id,m.roles,m.active,u.display_name,u.active AS user_active
                FROM memberships m JOIN users u ON u.id=m.user_id
                WHERE m.tenant_id=:tenant AND m.active AND u.active AND 'technician'=ANY(m.roles)
                ORDER BY m.id LIMIT 100 OFFSET :offset"""), dict(tenant=tenant_id, offset=offset)).mappings().all()
            return envelope(request, items=[dict(row) for row in rows],
                            next_offset=offset+100 if len(rows)==100 else None)

    def admin_context(s,request,tenant_id):
        # Serialize all membership writes for the organization, then re-read privileges.
        actor = principal(s,request)
        csrf(request,actor)
        lock_tenant(s,tenant_id)
        actor = principal(s,request)  # Revalidate after any wait for the organization lock.
        membership(s,actor,tenant_id,'members.manage')
        return actor

    @router.post('/organizations/{tenant_id}/members',status_code=201)
    def add_member(tenant_id: UUID,payload: MemberAdd,request: Request):
        with transaction(request) as s:
            actor = admin_context(s,request,tenant_id)
            if not s.execute(text('SELECT id FROM users WHERE id=:id AND active FOR SHARE'),dict(id=payload.user_id)).first():
                raise HTTPException(404,'not_found')
            mid = s.execute(text("""INSERT INTO memberships(tenant_id,user_id,roles,active)
              VALUES (:tenant,:user,:roles,:active) RETURNING id"""),dict(tenant=tenant_id,user=payload.user_id,roles=payload.roles,active=payload.active)).scalar_one()
            audit(s,'membership_added',request.state.request_id,actor=actor['user_id'],tenant=tenant_id,target=payload.user_id)
        return envelope(request,id=mid)

    def update_member(s,request,tenant_id,member_id,roles=None,active=False):
        actor = admin_context(s,request,tenant_id)
        target = s.execute(text('SELECT user_id,roles FROM memberships WHERE tenant_id=:tenant AND id=:id'),dict(tenant=tenant_id,id=member_id)).mappings().one_or_none()
        if target is None:
            raise HTTPException(404,'not_found')
        new_roles = target['roles'] if roles is None else roles
        if not active or 'admin' not in new_roles:
            ensure_admin_remains(s,tenant_id,target['user_id'])
        s.execute(text('UPDATE memberships SET roles=:roles,active=:active WHERE tenant_id=:tenant AND id=:id'),
                  dict(roles=new_roles,active=active,tenant=tenant_id,id=member_id))
        audit(s,'membership_changed' if active else 'membership_disabled',request.state.request_id,
              actor=actor['user_id'],tenant=tenant_id,target=target['user_id'])

    @router.patch('/organizations/{tenant_id}/members/{member_id}')
    def change_member(tenant_id: UUID,member_id: UUID,payload: MemberChange,request: Request):
        with transaction(request) as s:
            update_member(s,request,tenant_id,member_id,payload.roles,payload.active)
        return envelope(request,status='updated')

    @router.delete('/organizations/{tenant_id}/members/{member_id}')
    def remove_member(tenant_id: UUID,member_id: UUID,request: Request):
        with transaction(request) as s:
            update_member(s,request,tenant_id,member_id)
        return envelope(request,status='disabled')

    return router
