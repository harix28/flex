"""Enterprise OpenID Connect (OIDC) & SAML SSO adapter for Meridian Sentinel.
Supports Okta, Azure AD, Keycloak, and PingFederate with PKCE and claims-to-roles mapping.
"""
import hashlib
import base64
import json
import secrets
from urllib.parse import urlencode
from typing import TypedDict
from uuid import UUID, uuid4
from sqlalchemy import text
from sentinel.auth.permissions import PERMISSIONS

ALL_ROLES = list(PERMISSIONS.keys())

class OIDCConfig(TypedDict):
    issuer: str
    client_id: str
    client_secret: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str


def generate_pkce_pair() -> tuple[str, str]:
    """Generates PKCE code_verifier and code_challenge (RFC 7636)."""
    verifier = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    challenge = base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')
    return verifier, challenge


def create_authorization_url(
    config: OIDCConfig,
    redirect_uri: str,
    state: str,
    code_challenge: str
) -> str:
    """Constructs the compliant OIDC authorization redirect URL."""
    params = {
        "client_id": config["client_id"],
        "response_type": "code",
        "scope": "openid email profile groups",
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256"
    }
    return f"{config['authorization_endpoint']}?{urlencode(params)}"


def map_enterprise_claims_to_roles(claims: dict, default_role: str = "viewer") -> list[str]:
    """
    Maps enterprise SSO claims (e.g. from Okta, Azure AD, or Keycloak) to Meridian Sentinel roles.
    Recognized roles: 'admin', 'plant_manager', 'technician', 'viewer'.
    """
    raw_groups = claims.get("groups", claims.get("roles", []))
    if isinstance(raw_groups, str):
        raw_groups = [raw_groups]

    mapped_roles = set()
    for g in raw_groups:
        g_lower = str(g).lower().strip()
        if "admin" in g_lower or "executive" in g_lower:
            mapped_roles.add("admin")
        elif "manager" in g_lower or "supervisor" in g_lower:
            mapped_roles.add("plant_manager")
        elif "tech" in g_lower or "maintenance" in g_lower or "mechanic" in g_lower:
            mapped_roles.add("technician")
        elif "viewer" in g_lower or "operator" in g_lower or "audit" in g_lower:
            mapped_roles.add("viewer")

    if not mapped_roles:
        mapped_roles.add(default_role)

    # Ensure mapped roles are within recognized schema
    valid = [r for r in ALL_ROLES if r in mapped_roles]
    return valid or [default_role]


def sync_sso_identity(
    session,
    tenant_id: UUID,
    issuer: str,
    subject: str,
    email: str,
    display_name: str,
    roles: list[str]
) -> dict:
    """
    Idempotently syncs an enterprise SSO user and their tenant membership.
    Never overwrites or deletes local password accounts.
    """
    email_clean = email.strip().lower()

    # 1. Check or insert user by (issuer, subject)
    user_row = session.execute(text("""
        SELECT id, active FROM users WHERE issuer = :issuer AND subject = :subject
    """), {'issuer': issuer, 'subject': subject}).mappings().one_or_none()

    if user_row:
        user_id = user_row['id']
        session.execute(text("""
            UPDATE users SET display_name = :name, email = :email WHERE id = :id
        """), {'id': user_id, 'name': display_name[:120], 'email': email_clean})
    else:
        user_id = session.execute(text("""
            INSERT INTO users (issuer, subject, display_name, email, active)
            VALUES (:issuer, :subject, :name, :email, true)
            RETURNING id
        """), {
            'issuer': issuer,
            'subject': subject,
            'name': display_name[:120],
            'email': email_clean
        }).scalar_one()

    # 2. Check or upsert tenant membership
    session.execute(text("""
        INSERT INTO memberships (tenant_id, user_id, roles, active)
        VALUES (:t, :u, :roles, true)
        ON CONFLICT (tenant_id, user_id) DO UPDATE
        SET roles = EXCLUDED.roles, active = true
    """), {'t': tenant_id, 'u': user_id, 'roles': roles})

    return {
        'user_id': str(user_id),
        'email': email_clean,
        'display_name': display_name,
        'issuer': issuer,
        'roles': roles
    }
