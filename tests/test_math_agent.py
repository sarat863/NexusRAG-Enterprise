import pytest
from rag_engine.math_agent import safe_calculate, QuantitativeMathAgent
from rag_engine.ingestion import DocumentIngestionPipeline, Document
from rag_engine.retriever import HybridRetriever, ScoredCandidate
from rag_engine.indexing import HybridIndex
from rag_engine.generator import CitationEnforcedGenerator


def test_safe_ast_calculator():
    """Verify safe AST calculation prevents code execution while solving math equations."""
    # Addition, Subtraction, Multiplication, Division
    assert safe_calculate("12 + (5 * 1.66) - 3") == 17.3
    assert safe_calculate("100 / 4 + 25") == 50.0
    assert safe_calculate("2 ** 3") == 8.0

    # Malicious injection strings should fail safely without executing
    with pytest.raises(Exception):
        safe_calculate("__import__('os').system('ls')")

    with pytest.raises(Exception):
        safe_calculate("eval('2+2')")


def test_quantitative_math_agent_pto_accrual():
    """
    Verify full quantitative reasoning on the audit benchmark scenario:
    'If I have 12 days of PTO saved and take 3 days off in March, and accrue 1.66 days per month, how many days will I have on August 1st?'
    """
    pipe = DocumentIngestionPipeline(chunk_size=100, chunk_overlap=20)
    doc = Document(
        id="doc_pto",
        title="Corporate Leave Policy",
        content="All full-time employees accrue 20 days of PTO per calendar year at a rate of 1.66 days per month.",
        metadata={"author": "HR"}
    )
    chunks = pipe.process_document(doc)
    index = HybridIndex()
    index.build_index([doc], chunks)

    cands = [ScoredCandidate(chunk=c, rerank_score=0.98) for c in chunks]
    math_agent = QuantitativeMathAgent()

    query = "If I have 12 days of PTO saved and take 3 days off in March, and accrue 1.66 days per month, how many days will I have on August 1st?"
    assert math_agent.detect_calculation_intent(query) is True

    res = math_agent.execute_analytical_query(query, cands)
    assert res is not None
    assert res.is_calculation is True
    # Formula: 12 + (5 * 1.66) - 3 = 17.3 days
    assert res.computed_value == 17.3
    assert "17.30 days" in res.step_by_step_proof or "17.3" in res.step_by_step_proof

    # Test integrated generator output
    generator = CitationEnforcedGenerator()
    rag_resp = generator.generate(query, cands)
    assert "17.3" in rag_resp.answer
    assert "[Source:" in rag_resp.answer
    assert len(rag_resp.citations) > 0
