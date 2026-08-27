import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.auth import JWTAuthHandler, DEMO_USERS


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_api_health_check(client):
    """Verify health check returns online status, active vault metrics, and verified DB probe."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"
    assert data["database_healthy"] is True
    assert data["platform"] == "NexusRAG Enterprise v0.2.0"
    assert data["available_vaults"] >= 5


def test_api_auth_token_lifecycle(client):
    """Verify OAuth2 token issuance for valid and invalid credentials."""
    # 1. Invalid credentials -> 401
    bad_resp = client.post("/api/v1/auth/token", json={
        "username": "admin@nexusrag.com",
        "password": "WrongPassword!"
    })
    assert bad_resp.status_code == 401

    # 2. Valid Admin credentials -> 200 with JWT
    ok_resp = client.post("/api/v1/auth/token", json={
        "username": "admin@nexusrag.com",
        "password": "AdminPass123!"
    })
    assert ok_resp.status_code == 200
    token_data = ok_resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["role"] == "admin"
    assert token_data["tenant_id"] == "enterprise_hq"


def test_api_rbac_vault_switching(client):
    """Verify RBAC restricts tenant vault switching and denies unauthorized cross-vault access."""
    # 1. Login as HR user
    hr_resp = client.post("/api/v1/auth/token", json={
        "username": "hr_user@nexusrag.com",
        "password": "HRPass123!"
    })
    assert hr_resp.status_code == 200
    hr_token = hr_resp.json()["access_token"]
    hr_headers = {"Authorization": f"Bearer {hr_token}"}

    # 2. HR user switching to 'hr_benefits' -> 200 OK
    switch_ok = client.post("/api/v1/vaults/switch", json={"vault_id": "hr_benefits"}, headers=hr_headers)
    assert switch_ok.status_code == 200
    assert switch_ok.json()["active_vault_id"] == "hr_benefits"

    # 3. HR user attempting to switch to 'sre_infra' -> 403 Forbidden
    switch_forbidden = client.post("/api/v1/vaults/switch", json={"vault_id": "sre_infra"}, headers=hr_headers)
    assert switch_forbidden.status_code == 403
    assert "Access Denied" in switch_forbidden.json()["detail"]


def test_api_query_pipeline(client):
    """Verify full RAG query execution with citation enforcement and triad metrics."""
    resp = client.post("/api/v1/query", json={
        "query": "What is the Tier-1 disaster recovery RTO target?",
        "vault_id": "all"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "15 minutes" in data["answer"].lower() or "rto" in data["answer"].lower()
    assert len(data["citations"]) > 0
    assert data["evaluation"]["faithfulness"] >= 0.75
    assert "latency" in data


def test_api_multi_hop_research(client):
    """Verify autonomous multi-hop research agent endpoint."""
    admin_token = JWTAuthHandler.create_access_token(
        username="admin@nexusrag.com",
        tenant_id="enterprise_hq",
        role="admin",
        is_admin=True
    )
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = client.post("/api/v1/research/multi-hop", json={
        "query": "What is the Tier-1 RTO and what form is needed for medical leave?",
        "initial_vault_id": "all"
    }, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["hops_taken"] >= 2
    assert len(data["hop_traces"]) >= 2
    assert len(data["citations"]) > 0
    assert data["faithfulness_score"] >= 0.70


def test_api_raptor_search_and_tree(client):
    """Verify RAPTOR hierarchical search and tree visualization endpoints."""
    # 1. Thematic search
    search_resp = client.post("/api/v1/raptor/search", json={
        "query": "Summarize enterprise disaster recovery and SLA targets",
        "top_k": 3
    })
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert search_data["results_count"] > 0

    # 2. Tree graph
    tree_resp = client.get("/api/v1/raptor/tree")
    assert tree_resp.status_code == 200
    tree_data = tree_resp.json()
    assert tree_data["total_nodes"] > 0
    assert len(tree_data["nodes"]) > 0
    assert len(tree_data["links"]) > 0


def test_api_docgen_compile(client):
    """Verify ScholarDoc compilation endpoint for Markdown, LaTeX, and HTML."""
    req_payload = {
        "title": "Enterprise Operations Protocol",
        "query": "SRE SLAs & HIPAA rules",
        "answer": "Tier-1 RTO is 15 minutes. PHI is encrypted with AES-256.",
        "citations": [
            {"doc_title": "SRE SLA Guidelines", "section_header": "DR Protocols", "page_number": 1, "author": "SRE Lead"}
        ],
        "doc_format": "latex",
        "citation_style": "IEEE"
    }
    resp = client.post("/api/v1/docgen/compile", json=req_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "\\documentclass" in data["content"]
    assert data["doc_format"] == "latex"
    assert data["citation_count"] == 1


def test_api_mcp_tools_and_dispatch(client):
    """Verify Model Context Protocol (MCP) tool list and tool execution."""
    # 1. List tools
    list_resp = client.get("/api/v1/mcp/tools")
    assert list_resp.status_code == 200
    manifest = list_resp.json()["tools"]
    tool_names = [t["name"] for t in manifest]
    assert "search_vault" in tool_names
    assert "verify_compliance" in tool_names

    # 2. Call search_vault
    call_resp = client.post("/api/v1/mcp/call", json={
        "tool": "search_vault",
        "arguments": {"query": "What is the P0 outage notification SLA?", "vault_id": "sre_infra"}
    })
    assert call_resp.status_code == 200
    res = call_resp.json()
    assert res["is_error"] is False
    assert len(res["content"]) > 0


def test_api_audit_verification(client):
    """Verify SOC 2 audit seal verification endpoint."""
    admin_token = JWTAuthHandler.create_access_token(
        username="admin@nexusrag.com",
        tenant_id="enterprise_hq",
        role="admin",
        is_admin=True
    )
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create a query to generate an audit log
    query_resp = client.post("/api/v1/query", json={
        "query": "What is the RPO target for relational databases?",
        "vault_id": "sre_infra"
    }, headers=headers)
    assert query_resp.status_code == 200
    logs_resp = client.get("/api/v1/audit/logs", headers=headers)
    assert logs_resp.status_code == 200
    logs = logs_resp.json()["logs"]
    assert len(logs) > 0
    latest_audit_id = logs[0]["audit_id"]

    # 3. Verify seal
    verify_resp = client.post("/api/v1/audit/verify", json={"audit_id": latest_audit_id})
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["is_valid"] is True
    assert verify_data["certificate"]["is_cryptographically_verified"] is True
