import pytest
from rag_engine.crag import CorrectiveRAGEvaluator
from rag_engine.timeline import PolicyTimelineExtractor
from rag_engine.vault_manager import MultiVaultManager
from rag_engine.ingestion import DocumentIngestionPipeline, Document
from rag_engine.retriever import ScoredCandidate


@pytest.fixture
def crag_setup():
    pipe = DocumentIngestionPipeline(chunk_size=100, chunk_overlap=20)
    vault_mgr = MultiVaultManager(ingestion_pipe=pipe)
    crag = CorrectiveRAGEvaluator()
    timeline = PolicyTimelineExtractor()
    return {
        "vault_mgr": vault_mgr,
        "crag": crag,
        "timeline": timeline
    }


def test_crag_evaluation_actions(crag_setup):
    """Test CRAG confidence evaluation for correct, ambiguous, and out-of-domain queries."""
    crag = crag_setup["crag"]
    vault_mgr = crag_setup["vault_mgr"]
    hr_vault = vault_mgr.vaults["hr_benefits"]
    chunks = hr_vault["chunks"]

    # 1. High confidence candidates
    good_candidates = [
        ScoredCandidate(chunk=chunks[1], rerank_score=0.98)
    ]
    res_correct = crag.evaluate_retrieval_confidence(
        "What form is needed for medical absences exceeding 3 days?",
        good_candidates
    )
    assert res_correct.action in ["CORRECT", "AMBIGUOUS"]
    assert res_correct.confidence_score > 0.4

    # 2. Out of domain candidates
    res_incorrect = crag.evaluate_retrieval_confidence(
        "Martian dragon spice recipe",
        []
    )
    assert res_incorrect.action == "INCORRECT"


def test_policy_timeline_extractor(crag_setup):
    """Test extraction of SLA targets, deadlines, and timeframes across vaults."""
    timeline = crag_setup["timeline"]
    vault_mgr = crag_setup["vault_mgr"]

    events = timeline.extract_all_timelines(vault_mgr.vaults)
    assert len(events) > 0

    timeframes = [e.timeframe.lower() for e in events]
    # Check for known deadlines extracted
    assert any("48 hours" in tf or "15 minutes" in tf or "60 seconds" in tf or "90 days" in tf for tf in timeframes)

    # Check urgency levels present
    urgencies = set([e.urgency_level for e in events])
    assert "CRITICAL" in urgencies or "HIGH" in urgencies or "MEDIUM" in urgencies
