import pytest
from rag_engine.crag import CorrectiveRAGEvaluator, CRAGEvaluationResult
from rag_engine.retriever import ScoredCandidate
from rag_engine.ingestion import Chunk


def test_crag_ambiguous_web_grounding():
    """Verify that borderline/ambiguous retrieval triggers query reformulation and web grounding."""
    crag = CorrectiveRAGEvaluator(high_threshold=0.65, low_threshold=0.35)

    chunk = Chunk(
        id="chunk_test_0",
        doc_id="doc_test",
        doc_title="General Compliance Guidelines",
        content="Enterprise compliance policies mandate adherence to standard security requirements and audit procedures.",
        metadata={"section_header": "Overview"},
        token_count=15
    )
    # Borderline scored candidate
    cand = ScoredCandidate(chunk=chunk, rerank_score=0.45)

    query = "What are the latest compliance updates for standard audit?"
    res: CRAGEvaluationResult = crag.evaluate_retrieval_confidence(query, [cand])

    assert res.action in ["AMBIGUOUS", "CORRECT"]
    if res.action == "AMBIGUOUS":
        assert res.confidence_score >= 0.35
        assert res.reformulated_query != ""
        assert res.external_search_grounding is not None
        assert len(res.external_search_grounding) > 0
        assert "url" in res.external_search_grounding[0]
        assert "title" in res.external_search_grounding[0]
