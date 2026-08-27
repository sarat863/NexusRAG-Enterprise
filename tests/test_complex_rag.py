import pytest
from rag_engine.query_expansion import AgenticQueryProcessor
from rag_engine.knowledge_graph import EntityKnowledgeGraph
from rag_engine.evaluator import RAGTriadEvaluator
from rag_engine.vault_manager import MultiVaultManager
from rag_engine.ingestion import DocumentIngestionPipeline, Document


@pytest.fixture
def complex_engines():
    pipe = DocumentIngestionPipeline(chunk_size=120, chunk_overlap=25)
    vault_mgr = MultiVaultManager(ingestion_pipe=pipe)
    qp = AgenticQueryProcessor()
    kg = EntityKnowledgeGraph()
    evaluator = RAGTriadEvaluator()

    return {
        "pipeline": pipe,
        "vault_manager": vault_mgr,
        "query_processor": qp,
        "graph": kg,
        "evaluator": evaluator
    }


def test_agentic_query_expansion(complex_engines):
    """Test intent classification, entity detection, and multi-query expansions."""
    qp = complex_engines["query_processor"]
    
    # 1. Policy intent
    res1 = qp.analyze("What form must employees submit for Form HR-402?")
    assert res1.intent == "policy_compliance"
    assert "Form HR-402" in res1.detected_entities
    assert len(res1.expanded_queries) >= 3

    # 2. SRE metrics intent
    res2 = qp.analyze("What is the RTO and RPO for Tier-1 database systems?")
    assert res2.intent == "sre_metrics"
    assert "RTO" in res2.detected_entities or "RPO" in res2.detected_entities

    # 3. Out-of-domain intent
    res3 = qp.analyze("How to prepare Martian potato stew with dragon spices?")
    assert res3.intent == "out_of_domain"


def test_entity_knowledge_graph_extraction(complex_engines):
    """Test extraction of forms, acronyms, standards and graph construction."""
    kg = complex_engines["graph"]
    pipe = complex_engines["pipeline"]

    doc = Document(
        id="doc_compliance",
        title="InfoSec Protocol",
        content="""# Section 1: MFA Policy
All users must use FIDO2 keys for Multi-Factor Authentication (MFA). SMS-based 2FA is prohibited under Rule SEC-881.

# Section 2: Medical Forms
Medical records require Form HR-402 conforming to ISO-27001 standard.""",
        metadata={"url": "https://corp/sec"}
    )
    chunks = pipe.process_document(doc)
    kg.build_graph([doc], chunks)

    graph_data = kg.get_graph_data()
    assert len(graph_data.nodes) > 0
    assert len(graph_data.links) > 0

    node_labels = [n.label for n in graph_data.nodes]
    assert any("Form HR-402" in l or "Rule SEC-881" in l or "FIDO2" in l for l in node_labels)


def test_rag_triad_evaluator(complex_engines):
    """Test Context Relevance, Faithfulness and Answer Relevance."""
    evaluator = complex_engines["evaluator"]
    vault_mgr = complex_engines["vault_manager"]

    hr_vault = vault_mgr.vaults["hr_benefits"]
    chunks = hr_vault["chunks"]
    
    # Create fake candidate
    from rag_engine.retriever import ScoredCandidate
    candidates = [ScoredCandidate(chunk=c, rerank_score=0.95) for c in chunks]

    query = "What form is required for medical absences over 3 days?"
    answer = "For medical absences exceeding 3 consecutive days, employees must submit Form HR-402 within 48 hours. [Source: chunk_doc_fc60f2cb_1]"

    eval_res = evaluator.evaluate(query, answer, candidates)
    assert eval_res.faithfulness > 0.6
    assert eval_res.context_relevance > 0.5
    assert eval_res.hallucination_risk in ["LOW", "MEDIUM"]


def test_multi_collection_vault_isolation(complex_engines):
    """Test that vaults are isolated and maintain separate document collections."""
    vault_mgr = complex_engines["vault_manager"]
    vaults = vault_mgr.list_vaults()
    assert len(vaults) >= 4

    vault_ids = [v.id for v in vaults]
    assert "hr_benefits" in vault_ids
    assert "sre_infra" in vault_ids
    assert "infosec_compliance" in vault_ids

    # Switch active vault
    assert vault_mgr.set_active_vault("sre_infra") is True
    active = vault_mgr.get_active_vault()
    assert active["name"] == "SRE & Infrastructure SLAs"
