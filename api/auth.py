import os
import logging
import base64
import hmac
import hashlib
import json
import time
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, Security, status, Header

logger = logging.getLogger("nexusrag.auth")

SECRET_KEY = os.getenv("NEXUSRAG_JWT_SECRET", "nexusrag-enterprise-secret-key-soc2-compliant")
if SECRET_KEY == "nexusrag-enterprise-secret-key-soc2-compliant":
    logger.warning("Using default JWT SECRET_KEY. In production, configure NEXUSRAG_JWT_SECRET environment variable.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv("JWT_EXPIRE_SECONDS", str(3600 * 24)))  # Default 24 hours


class UserTenantContext(BaseModel):
    """Authenticated user context with strict tenant isolation metadata and RBAC scopes."""
    username: str
    tenant_id: str
    role: str = "user"  # "admin", "auditor", "engineer", "user", "guest"
    is_admin: bool = False
    allowed_vaults: List[str] = Field(default_factory=list)


# Pre-seeded enterprise demo credentials
DEMO_USERS = {
    "admin@nexusrag.com": {
        "password": "AdminPass123!",
        "tenant_id": "enterprise_hq",
        "role": "admin",
        "is_admin": True,
        "allowed_vaults": ["*"]
    },
    "sre_lead@nexusrag.com": {
        "password": "SREPass123!",
        "tenant_id": "sre_infra",
        "role": "engineer",
        "is_admin": False,
        "allowed_vaults": ["sre_infra", "all", "pdf_standards"]
    },
    "compliance@nexusrag.com": {
        "password": "CompPass123!",
        "tenant_id": "infosec_compliance",
        "role": "auditor",
        "is_admin": False,
        "allowed_vaults": ["infosec_compliance", "all", "pdf_standards"]
    },
    "hr_user@nexusrag.com": {
        "password": "HRPass123!",
        "tenant_id": "hr_benefits",
        "role": "user",
        "is_admin": False,
        "allowed_vaults": ["hr_benefits", "pdf_standards"]
    }
}

# Pre-seeded API Keys for automated service integrations
DEMO_API_KEYS = {
    "nexus-admin-key-2026": "admin@nexusrag.com",
    "nexus-sre-key-2026": "sre_lead@nexusrag.com",
    "nexus-compliance-key-2026": "compliance@nexusrag.com",
    "nexus-hr-key-2026": "hr_user@nexusrag.com"
}


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _base64url_decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("utf-8"))


class JWTAuthHandler:
    """Pure-Python HMAC-SHA256 JWT Token Manager (Zero External Dependencies)."""

    @classmethod
    def create_access_token(
        cls,
        username: str,
        tenant_id: str,
        role: str = "user",
        is_admin: bool = False,
        allowed_vaults: Optional[List[str]] = None
    ) -> str:
        header = {"alg": ALGORITHM, "typ": "JWT"}
        payload = {
            "sub": username,
            "tenant_id": tenant_id,
            "role": role,
            "is_admin": is_admin,
            "allowed_vaults": allowed_vaults if allowed_vaults is not None else ([tenant_id] if not is_admin else ["*"]),
            "iat": int(time.time()),
            "exp": int(time.time()) + ACCESS_TOKEN_EXPIRE_SECONDS
        }

        h_bytes = _base64url_encode(json.dumps(header).encode("utf-8"))
        p_bytes = _base64url_encode(json.dumps(payload).encode("utf-8"))
        signing_input = f"{h_bytes}.{p_bytes}".encode("utf-8")

        signature = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
        sig_bytes = _base64url_encode(signature)

        return f"{h_bytes}.{p_bytes}.{sig_bytes}"

    @classmethod
    def decode_token(cls, token: str) -> Dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 3:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token structure")

        h_bytes, p_bytes, sig_bytes = parts
        signing_input = f"{h_bytes}.{p_bytes}".encode("utf-8")
        expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()

        if not hmac.compare_digest(expected_sig, _base64url_decode(sig_bytes)):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token cryptographic signature")

        try:
            payload = json.loads(_base64url_decode(p_bytes).decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Corrupted token payload")

        if payload.get("exp", 0) < int(time.time()):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")

        return payload


def validate_vault_permission(user: Any, target_vault_id: str) -> bool:
    """
    Validates whether the user's role and allowed_vaults grant access to target_vault_id.
    - Admins have wildcard '*' access.
    - Departmental users have access to their tenant_id, 'pdf_standards', and explicit allowed_vaults.
    - Guests have access to 'all' and 'pdf_standards'.
    """
    if not isinstance(user, UserTenantContext):
        return True

    if user.is_admin or user.role == "admin" or "*" in user.allowed_vaults:
        return True
    
    if target_vault_id in user.allowed_vaults:
        return True

    if target_vault_id == user.tenant_id:
        return True

    if target_vault_id in ["pdf_standards"]:
        return True

    # Guests or users querying 'all'
    if user.role in ["guest", "user"] and target_vault_id == "all":
        return True

    return False


def get_current_tenant_context(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None)
) -> UserTenantContext:
    """
    FastAPI dependency for authenticating and enforcing tenant context.
    Supports:
    1. 'X-API-Key' Header for automated services.
    2. 'Authorization: Bearer <JWT>' Header for user sessions.
    3. Public Guest fallback when no auth headers are supplied.
    """
    # 1. Check API Key Header
    if x_api_key and isinstance(x_api_key, str):
        username = DEMO_API_KEYS.get(x_api_key)
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key provided in X-API-Key header"
            )
        user_info = DEMO_USERS.get(username, {})
        return UserTenantContext(
            username=username,
            tenant_id=user_info.get("tenant_id", "enterprise_hq"),
            role=user_info.get("role", "user"),
            is_admin=user_info.get("is_admin", False),
            allowed_vaults=user_info.get("allowed_vaults", ["*"])
        )

    # 2. Check Authorization Header
    if authorization and isinstance(authorization, str):
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "apikey":
            username = DEMO_API_KEYS.get(token)
            if not username:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API Key in Authorization header"
                )
            user_info = DEMO_USERS.get(username, {})
            return UserTenantContext(
                username=username,
                tenant_id=user_info.get("tenant_id", "enterprise_hq"),
                role=user_info.get("role", "user"),
                is_admin=user_info.get("is_admin", False),
                allowed_vaults=user_info.get("allowed_vaults", ["*"])
            )

        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header format. Expected 'Bearer <token>' or 'ApiKey <key>'"
            )

        payload = JWTAuthHandler.decode_token(token)
        allowed = payload.get("allowed_vaults")
        if allowed is None:
            if payload.get("is_admin", False):
                allowed = ["*"]
            else:
                allowed = [payload.get("tenant_id", "all"), "pdf_standards"]

        return UserTenantContext(
            username=payload.get("sub", "unknown"),
            tenant_id=payload.get("tenant_id", "all"),
            role=payload.get("role", "user"),
            is_admin=payload.get("is_admin", False),
            allowed_vaults=allowed
        )

    # 3. Fallback to Guest access (scoped to demo vaults, no wildcard)
    return UserTenantContext(
        username="guest@nexusrag.com",
        tenant_id="all",
        role="guest",
        is_admin=False,
        allowed_vaults=["pdf_standards", "all"]
    )
