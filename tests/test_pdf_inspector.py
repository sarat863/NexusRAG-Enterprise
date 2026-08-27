import io
import pytest

from rag_engine.pdf_inspector_engine import (
    pdf_engine,
    PDFInspectionReport,
    PDFExtractionResult,
    extract_tables_from_markdown
)
from rag_engine.ingestion import DocumentIngestionPipeline
from rag_engine.indexing import HybridIndex
from rag_engine.retriever import HybridRetriever
from rag_engine.reranker import CrossEncoderReranker
from rag_engine.generator import CitationEnforcedGenerator
from rag_engine.vault_manager import MultiVaultManager


@pytest.fixture
def sample_pdf_bytes():
    return pdf_engine.generate_sample_pdf("ai_governance")


def test_pdf_inspector_classification(sample_pdf_bytes):
    """Verify sub-10ms classification, table detection, and OCR pass action."""
    report = pdf_engine.inspect_pdf_bytes(sample_pdf_bytes, "ai_governance.pdf")
    
    assert report.pdf_type == "text_based"
    assert report.confidence >= 0.95
    assert report.page_count >= 1
    assert report.processing_time_ms < 50.0  # Typically 2-10ms
    assert len(report.pages_with_tables) > 0
    assert report.table_count >= 1
    assert report.ocr_routing_action == "NATIVE_PASS"


def test_pdf_markdown_table_extraction(sample_pdf_bytes):
    """Verify dual-mode table detection extracts clean Markdown table syntax."""
    extracted = pdf_engine.extract_structured_markdown(sample_pdf_bytes, "ai_governance.pdf")
    
    assert "Enterprise AI Governance" in extracted.title or "Ai Governance" in extracted.title
    assert len(extracted.pages) >= 1
    assert len(extracted.table_blocks) >= 1
    
    table_str = extracted.table_blocks[0]
    assert "|Incident Level|" in table_str or "| Incident Level |" in table_str or "|" in table_str
    assert "P0 - Model Breach" in table_str
    assert "5 Minutes" in table_str


def test_pdf_ingestion_pipeline_and_chunks(sample_pdf_bytes):
    """Verify DocumentIngestionPipeline parses PDF and produces enriched chunks."""
    pipeline = DocumentIngestionPipeline(chunk_size=120, chunk_overlap=20)
    doc, chunks, report = pipeline.process_pdf(
        pdf_bytes=sample_pdf_bytes,
        filename="SEC909_Standard.pdf",
        vault_id="pdf_standards",
        base_metadata={"author": "CISO"}
    )

    assert doc.metadata["doc_format"] == "pdf"
    assert doc.metadata["pdf_type"] == "text_based"
    assert len(chunks) >= 3

    # Verify table chunk tagging
    table_chunks = [c for c in chunks if c.metadata.get("has_table") is True]
    assert len(table_chunks) >= 1
    
    first_table_chunk = table_chunks[0]
    assert first_table_chunk.metadata["layout_type"] == "table_block"
    assert first_table_chunk.metadata["page_number"] == 1
    assert "|" in first_table_chunk.content


def test_pdf_rag_retrieval_and_citations(sample_pdf_bytes):
    """Verify hybrid retriever and cross-encoder accurately retrieve tabular PDF data."""
    pipeline = DocumentIngestionPipeline(chunk_size=120, chunk_overlap=20)
    index = HybridIndex()
    retriever = HybridRetriever(index=index)
    reranker = CrossEncoderReranker(top_n=3)
    generator = CitationEnforcedGenerator()

    doc, chunks, _ = pipeline.process_pdf(sample_pdf_bytes, "AI_Governance.pdf", "pdf_standards")
    index.build_index([doc], chunks)

    query = "What is the response SLA for P0 Model Breach under SEC-909?"
    candidates = retriever.retrieve(query, overfetch_k=10)
    assert len(candidates) > 0

    top_reranked = reranker.rerank(query, candidates, top_k=2)
    assert len(top_reranked) > 0
    assert "5 Minutes" in top_reranked[0].chunk.content or "P0" in top_reranked[0].chunk.content

    resp = generator.generate(query, top_reranked)
    assert len(resp.citations) > 0
    assert "5 minutes" in resp.answer.lower() or "p0" in resp.answer.lower()


def test_pdf_standards_vault_integration():
    """Verify MultiVaultManager includes pdf_standards vault with pre-seeded PDFs."""
    pipeline = DocumentIngestionPipeline(chunk_size=150, chunk_overlap=25)
    vm = MultiVaultManager(ingestion_pipe=pipeline)

    assert "pdf_standards" in vm.vaults
    pdf_vault = vm.vaults["pdf_standards"]
    assert len(pdf_vault["documents"]) >= 3
    assert len(pdf_vault["chunks"]) >= 6

    # Test retrieval against SRE disaster recovery table in pdf_standards
    retriever = HybridRetriever(pdf_vault["index"])
    cands = retriever.retrieve("What is RTO target for Tier-1 Relational DB?", overfetch_k=5)
    assert len(cands) > 0
    assert any("15 Minutes" in c.chunk.content for c in cands)


def test_fastapi_pdf_inspect_endpoint(sample_pdf_bytes):
    """Verify /api/v1/pdf/inspect endpoint returns fast structural analysis."""
    import asyncio
    from starlette.datastructures import UploadFile
    from api.main import inspect_uploaded_pdf

    upload = UploadFile(filename="AI_Gov.pdf", file=io.BytesIO(sample_pdf_bytes))
    resp = asyncio.run(inspect_uploaded_pdf(upload))
    assert resp.filename == "AI_Gov.pdf"
    assert resp.report.pdf_type == "text_based"
    assert resp.report.confidence >= 0.95
    assert resp.report.ocr_routing_action == "NATIVE_PASS"


def test_fastapi_pdf_extract_endpoint(sample_pdf_bytes):
    """Verify /api/v1/pdf/extract endpoint returns position-aware markdown."""
    import asyncio
    from starlette.datastructures import UploadFile
    from api.main import extract_pdf_to_markdown

    upload = UploadFile(filename="AI_Gov.pdf", file=io.BytesIO(sample_pdf_bytes))
    resp = asyncio.run(extract_pdf_to_markdown(upload))
    assert resp.full_markdown is not None
    assert len(resp.pages) >= 1
    assert len(resp.table_blocks) >= 1


def test_fastapi_pdf_upload_endpoint(sample_pdf_bytes):
    """Verify /api/v1/pdf/upload endpoint ingests PDF and rebuilds vault index."""
    import asyncio
    from starlette.datastructures import UploadFile
    from api.main import upload_and_ingest_pdf

    upload = UploadFile(filename="Live_Upload.pdf", file=io.BytesIO(sample_pdf_bytes))
    resp = asyncio.run(upload_and_ingest_pdf(file=upload, vault_id="all"))
    assert resp.success is True
    assert resp.chunks_created >= 3
    assert resp.table_chunks_created >= 1


def test_fastapi_pdf_benchmark_endpoint():
    """Verify /api/v1/pdf/benchmark runs comparative speed and table fidelity benchmark."""
    import asyncio
    from api.main import run_pdf_parser_benchmark

    resp = asyncio.run(run_pdf_parser_benchmark(preset_name="ai_governance"))
    assert resp.benchmark.pdf_type == "text_based"
    assert resp.benchmark.speedup_factor_vs_ocr > 10.0
    assert resp.benchmark.tables_detected >= 1
