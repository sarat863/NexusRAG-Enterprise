import pytest
from rag_engine.ingestion import Document, DocumentIngestionPipeline
from rag_engine.indexing import HybridIndex
from rag_engine.retriever import HybridRetriever
from rag_engine.reranker import CrossEncoderReranker
from rag_engine.generator import CitationEnforcedGenerator


@pytest.fixture
def sample_pipeline():
    pipeline = DocumentIngestionPipeline(chunk_size=100, chunk_overlap=20)
    index = HybridIndex()
    retriever = HybridRetriever(index=index)
    reranker = CrossEncoderReranker(top_n=3)
    generator = CitationEnforcedGenerator()

    doc1 = Document(
        id="doc_hr",
        title="Corporate Leave Policy",
        content="""# Section 1: PTO Rules
Full-time staff receive 20 days of Paid Time Off (PTO) annually.

# Section 2: Medical Form HR-402
For medical absences exceeding 3 days, employees must submit Form HR-402 within 48 hours to HR.""",
        metadata={"author": "HR", "page_number": 1}
    )

    doc2 = Document(
        id="doc_sre",
        title="SRE Protocols",
        content="""# Section 1: SLA Targets
Tier-1 production systems require 99.99% SLA availability.

# Section 2: Recovery Metrics
The Recovery Time Objective (RTO) is 15 minutes and Recovery Point Objective (RPO) is 60 seconds.""",
        metadata={"author": "SRE", "page_number": 1}
    )

    chunks1 = pipeline.process_document(doc1)
    chunks2 = pipeline.process_document(doc2)
    all_chunks = chunks1 + chunks2
    index.build_index([doc1, doc2], all_chunks)

    return {
        "pipeline": pipeline,
        "index": index,
        "retriever": retriever,
        "reranker": reranker,
        "generator": generator
    }


def test_chunking_metadata(sample_pipeline):
    """Verify structural metadata is attached to all chunks."""
    index = sample_pipeline["index"]
    assert len(index.chunks) >= 4
    for chunk in index.chunks:
        assert chunk.id.startswith("chunk_")
        assert "section_header" in chunk.metadata
        assert "page_number" in chunk.metadata


def test_exact_acronym_and_form_id_retrieval(sample_pipeline):
    """Verify BM25 accurately catches exact acronyms and form codes like HR-402."""
    index = sample_pipeline["index"]
    results = index.search_sparse("Form HR-402", top_k=5)
    assert len(results) > 0
    top_chunk, score = results[0]
    assert "HR-402" in top_chunk.content
    assert score > 0


def test_reciprocal_rank_fusion(sample_pipeline):
    """Verify RRF correctly merges dense and sparse results."""
    retriever = sample_pipeline["retriever"]
    candidates = retriever.retrieve("What is RTO and RPO for Tier-1 systems?", overfetch_k=10)
    assert len(candidates) > 0
    assert candidates[0].rrf_score > 0
    # Top chunk should discuss RTO/RPO
    top_candidate = candidates[0]
    assert "RTO" in top_candidate.chunk.content or "SLA" in top_candidate.chunk.content


def test_cross_encoder_reranker(sample_pipeline):
    """Verify cross-encoder re-scores and prioritizes exact contextual answers."""
    retriever = sample_pipeline["retriever"]
    reranker = sample_pipeline["reranker"]

    query = "medical leave form required after 3 days"
    candidates = retriever.retrieve(query, overfetch_k=5)
    top_reranked = reranker.rerank(query, candidates, top_k=2)

    assert len(top_reranked) <= 2
    assert "HR-402" in top_reranked[0].chunk.content


def test_enforced_citations_generation(sample_pipeline):
    """Verify generation outputs strict [Source: chunk_id] citations."""
    retriever = sample_pipeline["retriever"]
    reranker = sample_pipeline["reranker"]
    generator = sample_pipeline["generator"]

    query = "What is Form HR-402 used for?"
    candidates = retriever.retrieve(query, overfetch_k=5)
    top_chunks = reranker.rerank(query, candidates, top_k=2)

    response = generator.generate(query, top_chunks)
    assert response.query == query
    assert "[Source:" in response.answer
    assert len(response.citations) > 0
    assert response.citations[0].doc_title == "Corporate Leave Policy"


def test_hallucination_prevention_out_of_context(sample_pipeline):
    """Verify system outputs 'I don't know' for questions outside knowledge base."""
    generator = sample_pipeline["generator"]
    out_of_context_query = "What is the secret recipe for Martian potato stew?"
    response = generator.generate(out_of_context_query, [])

    assert "I don't know" in response.answer
    assert len(response.citations) == 0
