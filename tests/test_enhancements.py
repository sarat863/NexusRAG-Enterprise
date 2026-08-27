import pytest
from rag_engine.raptor import RAPTORIndex, RAPTORNode, RAPTORSearchResult
from rag_engine.multi_hop_agent import MultiHopResearchAgent, MultiHopResearchResult
from rag_engine.docgen import ScholarDocCompiler, CompiledDocumentResult
from rag_engine.audit_vault import AuditVaultManager
from rag_engine.ingestion import DocumentIngestionPipeline, Document, Chunk
from rag_engine.vault_manager import MultiVaultManager
from rag_engine.retriever import HybridRetriever
from rag_engine.reranker import CrossEncoderReranker
from rag_engine.generator import CitationEnforcedGenerator
from rag_engine.evaluator import RAGTriadEvaluator
from api.auth import JWTAuthHandler, UserTenantContext, DEMO_USERS
from api.mcp_server import MCPServerHandler


@pytest.fixture
def vault_manager_instance():
    pipeline = DocumentIngestionPipeline(chunk_size=120, chunk_overlap=20)
    return MultiVaultManager(pipeline)


def test_raptor_hierarchical_clustering_and_search(vault_manager_instance):
    """Verify RAPTOR constructs L0, L1, L2 nodes and supports hierarchical retrieval."""
    raptor = vault_manager_instance.raptor_index

    assert len(raptor.nodes) > 0
    assert len(raptor.level_nodes[0]) > 0
    assert len(raptor.level_nodes[1]) > 0
    assert len(raptor.level_nodes[2]) > 0

    # 1. Thematic search should retrieve L1/L2 summary nodes
    thematic_res = raptor.retrieve_hierarchical("Summarize all enterprise disaster recovery and SLA targets", top_k=3)
    assert len(thematic_res) > 0
    assert any(r.level in [1, 2] for r in thematic_res)

    # 2. Specific search should retrieve L0 granular leaf nodes
    granular_res = raptor.retrieve_hierarchical("What is Form HR-402 medical leave requirement?", top_k=3)
    assert len(granular_res) > 0
    assert any(r.level == 0 for r in granular_res)
    assert any("HR-402" in r.node.content for r in granular_res)

    # 3. Tree visualization D3 graph
    viz = raptor.get_tree_visualization()
    assert viz["total_nodes"] == len(raptor.nodes)
    assert len(viz["links"]) > 0


def test_multi_hop_research_agent_loop(vault_manager_instance):
    """Verify MultiHopResearchAgent decomposes cross-vault queries and iterates to convergence."""
    retriever_map = {vid: HybridRetriever(index=v["index"]) for vid, v in vault_manager_instance.vaults.items()}
    agent = MultiHopResearchAgent(
        retriever_map=retriever_map,
        unified_retriever=HybridRetriever(index=vault_manager_instance.vaults["all"]["index"]),
        reranker=CrossEncoderReranker(top_n=3),
        generator=CitationEnforcedGenerator(),
        evaluator=RAGTriadEvaluator()
    )

    query = "What is the Tier-1 RTO SLA and what form is required for PTO rollover?"
    res = agent.execute_research_loop(query)

    assert res.hops_taken >= 2
    assert res.total_chunks_consulted >= 2
    assert len(res.hop_traces) >= 2
    assert "15 minutes" in res.final_answer.lower() or "rto" in res.final_answer.lower()
    assert len(res.citations) > 0
    assert res.faithfulness_score >= 0.80


def test_scholardoc_compiler_latex_html_apa():
    """Verify ScholarDocCompiler outputs valid Markdown, LaTeX, HTML, and APA/IEEE citations."""
    compiler = ScholarDocCompiler()

    citations = [
        {"doc_title": "SRE SLA Guidelines", "section_header": "Disaster Recovery Protocols", "page_number": 1, "author": "SRE Lead"},
        {"doc_title": "Corporate PTO Policy 2026", "section_header": "PTO Entitlement", "page_number": 2, "author": "HR Lead"}
    ]

    # 1. APA Markdown
    md_res = compiler.compile_document(
        title="Enterprise Operational Synthesis",
        query="SRE SLAs & HR PTO rules",
        answer="Tier-1 RTO target is 15 minutes. PTO rolls over up to 5 days.",
        citations=citations,
        doc_format="markdown",
        citation_style="APA"
    )
    assert "# Enterprise Operational Synthesis" in md_res.content
    assert "SRE Lead. (2026)" in md_res.content or "SRE Lead." in md_res.content
    assert md_res.citation_count == 2

    # 2. LaTeX Output
    tex_res = compiler.compile_document(
        title="Compliance Report",
        query="HIPAA PHI Encryption",
        answer="AES-256 encryption is strictly required under Rule 164.312.",
        citations=citations,
        doc_format="latex",
        citation_style="IEEE"
    )
    assert "\\documentclass" in tex_res.content
    assert "\\begin{thebibliography}" in tex_res.content
    assert "\\bibitem{ref1}" in tex_res.content

    # 3. HTML Output
    html_res = compiler.compile_document(
        title="Policy Executive Brief",
        query="MFA hardware rules",
        answer="FIDO2 hardware authentication is required under SEC-881.",
        citations=citations,
        doc_format="html",
        citation_style="MLA"
    )
    assert "<!DOCTYPE html>" in html_res.content
    assert "<title>Policy Executive Brief</title>" in html_res.content
    assert "<strong>" in html_res.content or "<h3>" in html_res.content


def test_audit_vault_and_sha256_cryptographic_seal():
    """Verify immutable audit ledger generates and validates SHA-256 signatures."""
    audit_mgr = AuditVaultManager()

    entry = audit_mgr.record_transaction(
        tenant_id="sre_infra",
        user_id="sre_lead@nexusrag.com",
        query_text="What is the RPO for Tier-1 databases?",
        synthesized_answer="The RPO target is 60 seconds with continuous WAL replication.",
        faithfulness_score=0.98,
        context_relevance_score=0.95,
        cited_chunk_ids=["chunk_sre_0", "chunk_sre_1"],
        latency_ms=12.4
    )

    assert entry.audit_id.startswith("AUDIT-NEXUS-")
    assert len(entry.sha256_signature) == 64
    assert entry.is_tamper_verified is True

    # Verify signature validation
    assert audit_mgr.verify_audit_seal(entry.audit_id) is True

    # Export audit certificate
    cert = audit_mgr.export_certificate(entry.audit_id)
    assert cert is not None
    assert cert["is_cryptographically_verified"] is True
    assert cert["tenant_id"] == "sre_infra"


def test_jwt_auth_and_tenant_context():
    """Verify OAuth2 JWT token generation, signature validation, and tenant isolation."""
    # 1. Generate token
    token = JWTAuthHandler.create_access_token(
        username="compliance@nexusrag.com",
        tenant_id="infosec_compliance",
        role="auditor",
        is_admin=False
    )
    assert isinstance(token, str)
    assert len(token.split(".")) == 3

    # 2. Decode and verify payload
    payload = JWTAuthHandler.decode_token(token)
    assert payload["sub"] == "compliance@nexusrag.com"
    assert payload["tenant_id"] == "infosec_compliance"
    assert payload["role"] == "auditor"


def test_mcp_server_manifest_and_dispatch(vault_manager_instance):
    """Verify Model Context Protocol (MCP) tool manifest and tool execution."""
    mcp = MCPServerHandler(vault_manager_instance)
    manifest = mcp.get_manifest()

    assert len(manifest) >= 6
    tool_names = [t["name"] for t in manifest]
    assert "search_vault" in tool_names
    assert "raptor_thematic_search" in tool_names
    assert "verify_compliance" in tool_names
    assert "get_sla_timeline" in tool_names
    assert "compile_manuscript" in tool_names
    assert "inspect_pdf_structure" in tool_names

    # Test search_vault tool execution
    res = mcp.execute_tool("search_vault", {"query": "What is the P0 outage notification SLA?", "vault_id": "sre_infra"})
    assert res.is_error is False
    assert len(res.content) > 0
    assert "5" in res.content[0]["text"] or "PagerDuty" in res.content[0]["text"] or "SLA" in res.content[0]["text"]

    # Test compliance verification tool
    comp_res = mcp.execute_tool("verify_compliance", {
        "rule_code": "SEC-881",
        "statement": "All staff must authenticate using FIDO2 hardware keys."
    })
    assert comp_res.is_error is False
    assert "COMPLIANT" in comp_res.content[0]["text"]
