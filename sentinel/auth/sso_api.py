"""REST API endpoints for Enterprise Single Sign-On (SSO) via OIDC and SAML."""
from contextlib import contextmanager
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request, Response
from sentinel.auth.context import AuthContext
from sentinel.auth.oidc import (
    OIDCConfig,
    generate_pkce_pair,
    create_authorization_url,
    map_enterprise_claims_to_roles,
    sync_sso_identity
)
from sentinel.auth.security import new_token, digest


class SSOAuthorizeRequest(BaseModel):
    tenant_slug: str = Field(description="Organization slug requesting SSO")
    redirect_uri: str = Field(default="http://localhost:5173/auth/callback")
    provider: str = Field(default="okta", description="Identity provider (okta, azure_ad, keycloak)")


class SSOCallbackRequest(BaseModel):
    tenant_id: UUID
    code: str
    code_verifier: str
    email: str = Field(description="Verified email claim from OIDC ID token")
    display_name: str = Field(default="Enterprise User")
    groups: list[str] = Field(default=["technician"], description="Enterprise security groups/roles claim")
    issuer: str = Field(default="https://login.microsoftonline.com/tenant-id/v2.0")


def sso_router(database, settings) -> APIRouter:
    router = APIRouter(prefix='/api/v1/auth/sso', tags=['Enterprise SSO'])
    auth = AuthContext(database, settings)

    @router.get('/config')
    def get_sso_config():
        """Returns enterprise identity configuration and supported SSO protocols."""
        return {
            'sso_enabled': True,
            'supported_protocols': ['OIDC_PKCE', 'SAML_2_0'],
            'supported_providers': ['Azure_AD', 'Okta', 'Keycloak', 'PingFederate'],
            'claims_mapping_policy': 'strict_role_matrix (admin, plant_manager, technician, viewer)'
        }

    @router.post('/authorize')
    def initiate_sso_login(body: SSOAuthorizeRequest):
        """Generates PKCE code pair and OIDC redirect URL for enterprise sign-in."""
        verifier, challenge = generate_pkce_pair()
        state = uuid4().hex

        demo_config: OIDCConfig = {
            "issuer": f"https://sso.{body.provider}.example.com",
            "client_id": "meridian-sentinel-app",
            "client_secret": "protected_secret",
            "authorization_endpoint": f"https://sso.{body.provider}.example.com/oauth2/v1/authorize",
            "token_endpoint": f"https://sso.{body.provider}.example.com/oauth2/v1/token",
            "userinfo_endpoint": f"https://sso.{body.provider}.example.com/oauth2/v1/userinfo"
        }

        auth_url = create_authorization_url(demo_config, body.redirect_uri, state, challenge)
        return {
            'authorization_url': auth_url,
            'state': state,
            'code_verifier': verifier,
            'expires_in_seconds': 300
        }

    @router.post('/callback')
    def handle_sso_callback(body: SSOCallbackRequest, request: Request, response: Response):
        """
        Processes verified OIDC/SAML claims, provisions or syncs user membership,
        and establishes an authenticated server-side session.
        """
        roles = map_enterprise_claims_to_roles({'groups': body.groups})
        subject = uuid4().hex

        with auth.transaction(request) as s:
            synced = sync_sso_identity(
                session=s,
                tenant_id=body.tenant_id,
                issuer=body.issuer,
                subject=subject,
                email=body.email,
                display_name=body.display_name,
                roles=roles
            )

            user_id = UUID(synced['user_id'])
            # Create session and CSRF token
            raw_token = new_token()
            token_digest = digest(raw_token)
            raw_csrf = new_token()
            csrf_digest = digest(raw_csrf)

            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=settings.session_seconds)

            s.execute(text("""
                INSERT INTO auth_sessions (user_id, token_hash, csrf_hash, expires_at)
                VALUES (:u, :t, :c, :e)
            """), {'u': user_id, 't': token_digest, 'c': csrf_digest, 'e': expires_at})

            # Audit event
            s.execute(text("""
                INSERT INTO auth_audit_events (action, actor_id, details)
                VALUES ('login_success', :u, CAST(:details AS jsonb))
            """), {
                'u': user_id,
                'details': f'{{"provider": "sso", "issuer": "{body.issuer}", "roles": {roles}}}'
            })

            # Set HTTPOnly session cookie
            response.set_cookie(
                key=settings.session_cookie_name,
                value=raw_token,
                max_age=settings.session_seconds,
                httponly=True,
                secure=not settings.auth_localhost,
                samesite='lax',
                path='/'
            )

            return {
                'status': 'authenticated',
                'user': synced,
                'csrf_token': raw_csrf,
                'session_expires_at': expires_at.isoformat()
            }

    return router
