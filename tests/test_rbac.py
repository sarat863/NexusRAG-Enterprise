import pytest
from fastapi import HTTPException
from api.auth import (
    JWTAuthHandler,
    UserTenantContext,
    validate_vault_permission,
    get_current_tenant_context,
    DEMO_USERS,
    DEMO_API_KEYS
)


def test_rbac_admin_wildcard_access():
    """Verify Admin role has wildcard access to all departmental vaults."""
    admin_ctx = UserTenantContext(
        username="admin@nexusrag.com",
        tenant_id="enterprise_hq",
        role="admin",
        is_admin=True,
        allowed_vaults=["*"]
    )

    assert validate_vault_permission(admin_ctx, "hr_benefits") is True
    assert validate_vault_permission(admin_ctx, "sre_infra") is True
    assert validate_vault_permission(admin_ctx, "infosec_compliance") is True
    assert validate_vault_permission(admin_ctx, "procurement_quantum") is True
    assert validate_vault_permission(admin_ctx, "all") is True


def test_rbac_departmental_user_isolation():
    """Verify HR user cannot access SRE or InfoSec confidential vaults."""
    hr_ctx = UserTenantContext(
        username="hr_user@nexusrag.com",
        tenant_id="hr_benefits",
        role="user",
        is_admin=False,
        allowed_vaults=["hr_benefits", "pdf_standards"]
    )

    assert validate_vault_permission(hr_ctx, "hr_benefits") is True
    assert validate_vault_permission(hr_ctx, "pdf_standards") is True
    # Should be denied access to other departmental vaults
    assert validate_vault_permission(hr_ctx, "sre_infra") is False
    assert validate_vault_permission(hr_ctx, "infosec_compliance") is False
    assert validate_vault_permission(hr_ctx, "procurement_quantum") is False


def test_rbac_sre_engineer_isolation():
    """Verify SRE engineer can access SRE vault and unified vault, but not HR benefits."""
    sre_ctx = UserTenantContext(
        username="sre_lead@nexusrag.com",
        tenant_id="sre_infra",
        role="engineer",
        is_admin=False,
        allowed_vaults=["sre_infra", "all", "pdf_standards"]
    )

    assert validate_vault_permission(sre_ctx, "sre_infra") is True
    assert validate_vault_permission(sre_ctx, "all") is True
    assert validate_vault_permission(sre_ctx, "hr_benefits") is False
    assert validate_vault_permission(sre_ctx, "procurement_quantum") is False


def test_api_key_authentication_resolution():
    """Verify X-API-Key header properly maps to authorized user context."""
    # SRE API Key
    ctx = get_current_tenant_context(x_api_key="nexus-sre-key-2026")
    assert ctx.username == "sre_lead@nexusrag.com"
    assert ctx.tenant_id == "sre_infra"
    assert ctx.role == "engineer"
    assert "sre_infra" in ctx.allowed_vaults

    # Invalid API Key should raise 401
    with pytest.raises(HTTPException) as exc_info:
        get_current_tenant_context(x_api_key="invalid-bogus-key")
    assert exc_info.value.status_code == 401


def test_jwt_token_claims_and_permission_validation():
    """Verify JWT token payload includes allowed_vaults and validates correctly."""
    token = JWTAuthHandler.create_access_token(
        username="compliance@nexusrag.com",
        tenant_id="infosec_compliance",
        role="auditor",
        is_admin=False,
        allowed_vaults=["infosec_compliance", "all"]
    )

    auth_header = f"Bearer {token}"
    ctx = get_current_tenant_context(authorization=auth_header)
    assert ctx.username == "compliance@nexusrag.com"
    assert ctx.tenant_id == "infosec_compliance"
    assert validate_vault_permission(ctx, "infosec_compliance") is True
    assert validate_vault_permission(ctx, "hr_benefits") is False
