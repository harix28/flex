"""Shared session, tenant permission and CSRF boundary for application APIs."""
from contextlib import contextmanager
import hmac
import re
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from .permissions import permits
from .security import digest

class AuthContext:
    def __init__(self, database, settings):
        self.database, self.settings = database, settings
        self.cookie = 'meridian_session' if settings.auth_localhost else '__Host-meridian_session'

    @contextmanager
    def transaction(self, request):
        if not self.settings.auth_enabled or self.database is None:
            raise HTTPException(503,'authentication_unavailable')
        if self.settings.auth_localhost:
            if request.url.hostname not in ('localhost','127.0.0.1','::1'):
                raise HTTPException(403,'forbidden')
        elif request.url.scheme != 'https':
            raise HTTPException(403,'https_required')
        try:
            with self.database.transaction() as s:
                yield s
        except IntegrityError:
            raise HTTPException(409,'conflict') from None
        except SQLAlchemyError:
            raise HTTPException(503,'database_unavailable') from None

    def origin(self, request):
        if request.headers.get('origin') not in self.settings.auth_origins:
            raise HTTPException(403,'csrf_failed')
        if request.headers.get('sec-fetch-site') == 'cross-site':
            raise HTTPException(403,'csrf_failed')

    def principal(self, s, request):
        token = request.cookies.get(self.cookie, '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
            raise HTTPException(401,'authentication_required')
        actor = s.execute(text("""SELECT u.id AS user_id, u.email, u.display_name,
          a.id AS session_id, a.csrf_hash FROM auth_sessions a JOIN users u ON u.id=a.user_id
          WHERE a.token_hash=:hash AND a.revoked_at IS NULL AND a.expires_at>now() AND u.active"""),
          dict(hash=digest(token))).mappings().one_or_none()
        if actor is None:
            raise HTTPException(401,'authentication_required')
        return actor

    def csrf(self, request, actor):
        self.origin(request)
        token = request.headers.get('x-csrf-token','')
        if len(token) > 128 or not hmac.compare_digest(digest(token),actor['csrf_hash']):
            raise HTTPException(403,'csrf_failed')

    def membership(self, s, actor, tenant_id, permission):
        member = s.execute(text("""SELECT roles FROM memberships
          WHERE tenant_id=:tenant AND user_id=:user AND active"""),
          dict(tenant=tenant_id,user=actor['user_id'])).mappings().one_or_none()
        if member is None:
            raise HTTPException(404,'not_found')
        if not permits(member['roles'],permission):
            raise HTTPException(403,'forbidden')
        return member

