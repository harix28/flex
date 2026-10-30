"""Unit tests for Enterprise OIDC/SAML SSO and Distributed Rate Limiting."""
from sentinel.auth.oidc import (
    generate_pkce_pair,
    create_authorization_url,
    map_enterprise_claims_to_roles,
    OIDCConfig
)
from sentinel.auth.distributed_limiter import DistributedRateLimiter


def test_pkce_and_oidc_url_generation():
    verifier, challenge = generate_pkce_pair()
    assert len(verifier) >= 43
    assert len(challenge) >= 43

    config: OIDCConfig = {
        "issuer": "https://auth.aerocorp.example.com",
        "client_id": "sentinel-portal",
        "client_secret": "client_secret",
        "authorization_endpoint": "https://auth.aerocorp.example.com/oauth2/authorize",
        "token_endpoint": "https://auth.aerocorp.example.com/oauth2/token",
        "userinfo_endpoint": "https://auth.aerocorp.example.com/oauth2/userinfo"
    }

    url = create_authorization_url(config, "http://localhost:5173/callback", "state123", challenge)
    assert url.startswith("https://auth.aerocorp.example.com/oauth2/authorize?")
    assert "client_id=sentinel-portal" in url
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
    assert "state=state123" in url


def test_enterprise_claims_to_role_mapping():
    # Admin claim
    assert map_enterprise_claims_to_roles({"groups": ["Aero_Enterprise_Admins"]}) == ["admin"]

    # Technician claim
    assert map_enterprise_claims_to_roles({"roles": ["Line_Maintenance_Technicians"]}) == ["technician"]

    # Plant Manager claim
    assert map_enterprise_claims_to_roles({"groups": ["Hangar_Supervisors_Manager"]}) == ["plant_manager"]

    # Fallback to viewer
    assert map_enterprise_claims_to_roles({"groups": ["General_Staff"]}) == ["viewer"]


def test_distributed_rate_limiter_enforcement():
    limiter = DistributedRateLimiter(limit=3, window_seconds=10)
    key = "user-test-ip-192.168.1.10"

    # 3 allowed
    assert limiter.check(key)["allowed"] is True
    assert limiter.check(key)["allowed"] is True
    assert limiter.check(key)["allowed"] is True

    # 4th blocked
    fourth = limiter.check(key)
    assert fourth["allowed"] is False
    assert fourth["remaining"] == 0
    assert fourth["retry_after_seconds"] > 0

