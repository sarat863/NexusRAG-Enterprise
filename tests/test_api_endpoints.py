import io
import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.auth import DEMO_USERS, DEMO_API_KEYS


@pytest.fixture
def client():
    return TestClient(app)


def test_api_health_endpoint(client):
    """Test /api/v1/health endpoint."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"
    assert data["persistence_backend"] == "SQLite (WAL Mode)"
    assert data["rbac_active"] is True
    assert data["multi_turn_memory_active"] is True


def test_api_auth_token_and_rbac_vault_access(client):
    """Test OAuth2 JWT token acquisition and RBAC vault filtering."""
    # 1. Login as HR user
    token_resp = client.post("/api/v1/auth/token", json={
        "username": "hr_user@nexusrag.com",
        "password": "HRPass123!"
    })
    assert token_resp.status_code == 200
    hr_token = token_resp.json()["access_token"]
    hr_headers = {"Authorization": f"Bearer {hr_token}"}

    # 2. Query allowed vault
    query_resp = client.post("/api/v1/query", json={
        "query": "What is the policy for medical leave exceeding 3 days?",
        "vault_id": "hr_benefits"
    }, headers=hr_headers)
    assert query_resp.status_code == 200
    assert "HR-402" in query_resp.json()["answer"]

    # 3. Query forbidden vault (SRE) -> 403 Forbidden
    forbidden_resp = client.post("/api/v1/query", json={
        "query": "What is Tier-1 RTO?",
        "vault_id": "sre_infra"
    }, headers=hr_headers)
    assert forbidden_resp.status_code == 403


def test_api_api_key_auth(client):
    """Test API key header authentication."""
    headers = {"X-API-Key": "nexus-sre-key-2026"}
    resp = client.post("/api/v1/query", json={
        "query": "What is the RTO for Tier-1 databases?",
        "vault_id": "sre_infra"
    }, headers=headers)
    assert resp.status_code == 200
    assert "15 minutes" in resp.json()["answer"].lower() or "rto" in resp.json()["answer"].lower()


def test_api_multi_turn_session_and_coreference(client):
    """Test multi-turn query rewriting and session history retrieval."""
    session_id = "test_session_api_99"
    admin_headers = {"X-API-Key": "nexus-admin-key-2026"}

    # Turn 1
    t1_resp = client.post("/api/v1/query", json={
        "query": "What is the filing process for Form HR-402?",
        "vault_id": "hr_benefits",
        "session_id": session_id
    }, headers=admin_headers)
    assert t1_resp.status_code == 200
    assert "HR-402" in t1_resp.json()["answer"]

    # Turn 2: pronoun "it"
    t2_resp = client.post("/api/v1/query", json={
        "query": "Who must sign it?",
        "vault_id": "hr_benefits",
        "session_id": session_id
    }, headers=admin_headers)
    assert t2_resp.status_code == 200
    assert t2_resp.json()["query_analysis"]["coreference_resolved"] is True
    assert "healthcare provider" in t2_resp.json()["answer"].lower() or "signed" in t2_resp.json()["answer"].lower() or "certified" in t2_resp.json()["answer"].lower()

    # Get session history
    hist_resp = client.get(f"/api/v1/sessions/{session_id}/history", headers=admin_headers)
    assert hist_resp.status_code == 200
    assert hist_resp.json()["turns_count"] >= 4

    # Clear session
    del_resp = client.delete(f"/api/v1/sessions/{session_id}", headers=admin_headers)
    assert del_resp.status_code == 200


def test_api_quantitative_math_query(client):
    """Test quantitative math calculation query via API."""
    admin_headers = {"X-API-Key": "nexus-admin-key-2026"}
    math_query = "If I have 12 days of PTO saved and take 3 days off in March, and accrue 1.66 days per month, how many days will I have on August 1st?"
    resp = client.post("/api/v1/query", json={
        "query": math_query,
        "vault_id": "hr_benefits"
    }, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "17.3" in data["answer"]
    assert len(data["citations"]) > 0


def test_api_streaming_query(client):
    """Test SSE real-time streaming endpoint."""
    admin_headers = {"X-API-Key": "nexus-admin-key-2026"}
    resp = client.post("/api/v1/query/stream", json={
        "query": "What is Form HR-402 used for?",
        "vault_id": "hr_benefits"
    }, headers=admin_headers)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    content = resp.text
    assert "data:" in content
    assert "[DONE]" in content


def test_api_multiformat_upload_csv(client):
    """Test multi-format file upload endpoint with CSV."""
    admin_headers = {"X-API-Key": "nexus-admin-key-2026"}
    csv_bytes = b"Rule,Description\nSEC-881,FIDO2 hardware MFA is mandatory\n"
    files = {"file": ("rules.csv", io.BytesIO(csv_bytes), "text/csv")}
    resp = client.post("/api/v1/documents/upload", files=files, data={"vault_id": "infosec_compliance"}, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["format"] == "csv"
    assert data["chunks_created"] >= 1
