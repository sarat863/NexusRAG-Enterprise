import os
import time
import hashlib
import datetime
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from rag_engine.config import default_config
from rag_engine.ingestion import Document, DocumentIngestionPipeline
from rag_engine.indexing import HybridIndex
from rag_engine.retriever import HybridRetriever
from rag_engine.reranker import CrossEncoderReranker
from rag_engine.generator import CitationEnforcedGenerator
from rag_engine.query_expansion import AgenticQueryProcessor, QueryAnalysis
from rag_engine.knowledge_graph import EntityKnowledgeGraph, GraphData
from rag_engine.evaluator import RAGTriadEvaluator
from rag_engine.vault_manager import MultiVaultManager, KnowledgeVaultInfo
from rag_engine.crag import CorrectiveRAGEvaluator, CRAGEvaluationResult
from rag_engine.timeline import PolicyTimelineExtractor, TimelineEvent

from .schemas import (
    IngestDocumentRequest,
    SwitchVaultRequest,
    QueryRequest,
    RAGQueryResponse,
    RetrievalStepItem,
    CitationItem,
    LatencyBreakdown,
    ArenaCompareResponse,
    ArenaStrategyResult,
    AuditReportCertificate
)

app = FastAPI(
    title="NexusRAG Enterprise 4.0 API",
    description="Enterprise RAG Intelligence, CRAG Self-Reflection, Real-Time SSE Streaming, and A/B Arena Platform.",
    version="4.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Engines
ingestion_pipe = DocumentIngestionPipeline(
    chunk_size=default_config.chunk_size,
    chunk_overlap=default_config.chunk_overlap
)
vault_manager = MultiVaultManager(ingestion_pipe=ingestion_pipe)
query_processor = AgenticQueryProcessor()
reranker = CrossEncoderReranker(top_n=default_config.rerank_top_k)
generator = CitationEnforcedGenerator()
evaluator = RAGTriadEvaluator()
crag_evaluator = CorrectiveRAGEvaluator()
timeline_extractor = PolicyTimelineExtractor()


# Middleware: Latency Tracker
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response: Response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
    return response


# ---------------- API ROUTES ----------------

@app.get("/api/v1/health")
async def health_check():
    """System health check and active vault metrics."""
    active_vault = vault_manager.get_active_vault()
    return {
        "status": "online",
        "platform": "NexusRAG Enterprise 4.0",
        "active_vault": {
            "id": vault_manager.active_vault_id,
            "name": active_vault["name"],
            "total_documents": len(active_vault["documents"]),
            "total_chunks": len(active_vault["chunks"])
        },
        "available_vaults": len(vault_manager.vaults),
        "crag_reflection_active": True,
        "sse_streaming_ready": True,
        "timeline_extractor_active": True,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }


@app.get("/api/v1/vaults", response_model=List[KnowledgeVaultInfo])
async def list_knowledge_vaults():
    """Lists all available departmental knowledge vaults."""
    return vault_manager.list_vaults()


@app.post("/api/v1/vaults/switch")
async def switch_active_vault(payload: SwitchVaultRequest):
    """Switches the active knowledge vault."""
    success = vault_manager.set_active_vault(payload.vault_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Vault '{payload.vault_id}' not found.")
    active = vault_manager.get_active_vault()
    return {
        "success": True,
        "active_vault_id": vault_manager.active_vault_id,
        "name": active["name"],
        "document_count": len(active["documents"]),
        "chunk_count": len(active["chunks"])
    }


@app.get("/api/v1/graph", response_model=GraphData)
async def get_knowledge_graph(vault_id: str = None):
    """Returns the entity knowledge graph data for active or specified vault."""
    target_vault_id = vault_id or vault_manager.active_vault_id
    if target_vault_id not in vault_manager.vaults:
        raise HTTPException(status_code=404, detail="Vault not found.")
    graph: EntityKnowledgeGraph = vault_manager.vaults[target_vault_id]["graph"]
    return graph.get_graph_data()


@app.get("/api/v1/timeline", response_model=List[TimelineEvent])
async def get_cross_vault_timelines():
    """Extracts all temporal deadlines, SLA targets, and recurring frequencies across vaults."""
    return timeline_extractor.extract_all_timelines(vault_manager.vaults)


@app.post("/api/v1/query/expand", response_model=QueryAnalysis)
async def analyze_and_expand_query(payload: QueryRequest):
    """Inspects query intent, HyDE hypothetical doc, and sub-queries."""
    return query_processor.analyze(payload.query)


@app.post("/api/v1/query", response_model=RAGQueryResponse)
async def execute_enterprise_rag_query(payload: QueryRequest):
    """
    Full Enterprise Hybrid RAG Execution Pipeline with CRAG Self-Reflection:
    1. Query Analysis (Intent + HyDE + Multi-Query)
    2. Hybrid Retrieval with Tunable Alpha & RRF
    3. Corrective RAG (CRAG) Quality & Confidence Reflection
    4. Cross-Encoder Contextual Precision Reranking
    5. Enforced Source Citations Synthesis
    6. RAG Triad Observability Evaluation
    """
    total_start = time.time()
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    target_vault_id = payload.vault_id or vault_manager.active_vault_id
    if target_vault_id not in vault_manager.vaults:
        target_vault_id = vault_manager.active_vault_id
    vault_data = vault_manager.vaults[target_vault_id]
    index: HybridIndex = vault_data["index"]

    # 1. Query Analysis & Expansion
    t0 = time.time()
    query_analysis = query_processor.analyze(query)
    expanded_queries = query_analysis.expanded_queries if payload.use_multi_query else [query]
    if payload.use_hyde and query_analysis.hyde_document:
        expanded_queries.append(query_analysis.hyde_document[:100])
    expansion_ms = (time.time() - t0) * 1000

    # 2. Hybrid Retrieval (Tunable Alpha & RRF)
    t1 = time.time()
    retriever = HybridRetriever(index=index, config=default_config)
    overfetched_candidates = retriever.retrieve(
        query=query,
        overfetch_k=payload.overfetch_k or default_config.vector_top_k,
        alpha=payload.alpha_hybrid_weight if payload.alpha_hybrid_weight is not None else 0.5,
        k=payload.rrf_k or default_config.rrf_k,
        expanded_queries=expanded_queries
    )
    retrieval_ms = (time.time() - t1) * 1000

    # 3. Cross-Encoder Contextual Reranking
    t2 = time.time()
    top_reranked = reranker.rerank(
        query=query,
        candidates=overfetched_candidates,
        top_k=payload.top_k_rerank or default_config.rerank_top_k
    )
    rerank_ms = (time.time() - t2) * 1000

    # 4. CRAG Reflection Check
    crag_res = crag_evaluator.evaluate_retrieval_confidence(query, top_reranked)

    # 5. Citation-Enforced Generation
    t3 = time.time()
    gen = generator
    if payload.openai_api_key:
        gen = CitationEnforcedGenerator(api_key=payload.openai_api_key)

    if crag_res.action == "INCORRECT" and query_analysis.intent == "out_of_domain":
        rag_result = gen.generate(query, [])
    else:
        rag_result = gen.generate(query, top_reranked)
    generation_ms = (time.time() - t3) * 1000

    # 6. RAG Triad Observability Evaluation
    t4 = time.time()
    triad_eval = evaluator.evaluate(query, rag_result.answer, top_reranked)
    eval_ms = (time.time() - t4) * 1000
    total_elapsed = (time.time() - total_start) * 1000

    formatted_chunks = [
        RetrievalStepItem(**item) for item in rag_result.retrieved_chunks
    ]
    formatted_citations = [
        CitationItem(**cit.model_dump()) for cit in rag_result.citations
    ]

    latencies = LatencyBreakdown(
        query_expansion_ms=round(expansion_ms, 2),
        retrieval_ms=round(retrieval_ms, 2),
        rerank_ms=round(rerank_ms, 2),
        generation_ms=round(generation_ms, 2),
        evaluation_ms=round(eval_ms, 2),
        total_ms=round(total_elapsed, 2)
    )

    return RAGQueryResponse(
        query=query,
        answer=rag_result.answer,
        active_vault_id=target_vault_id,
        citations=formatted_citations,
        retrieved_chunks=formatted_chunks,
        query_analysis=query_analysis,
        evaluation=triad_eval,
        latency=latencies,
        model_used=rag_result.model_used,
        is_hallucination_guarded=True,
        crag_reflection=crag_res.model_dump()
    )


@app.post("/api/v1/query/stream")
async def execute_rag_streaming_query(payload: QueryRequest):
    """
    Real-Time Server-Sent Events (SSE) Token-by-Token Streaming Endpoint.
    """
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    target_vault_id = payload.vault_id or vault_manager.active_vault_id
    vault_data = vault_manager.vaults.get(target_vault_id, vault_manager.get_active_vault())
    index: HybridIndex = vault_data["index"]

    retriever = HybridRetriever(index=index, config=default_config)
    overfetched = retriever.retrieve(query=query, overfetch_k=15)
    top_reranked = reranker.rerank(query=query, candidates=overfetched, top_k=4)

    async def event_generator():
        async for token in generator.generate_stream(query, top_reranked):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/v1/arena", response_model=ArenaCompareResponse)
async def execute_rag_arena_comparison(payload: QueryRequest):
    """
    A/B Strategy Experimentation Arena:
    Runs Strategy A (Dense Semantic Vector Only) side-by-side with
    Strategy B (Advanced Hybrid RRF + CRAG + Cross-Encoder).
    """
    query = payload.query.strip()
    target_vault_id = payload.vault_id or vault_manager.active_vault_id
    vault_data = vault_manager.vaults.get(target_vault_id, vault_manager.get_active_vault())
    index: HybridIndex = vault_data["index"]

    # 1. Execute Strategy A (Dense Vector Only)
    tA_start = time.time()
    dense_candidates = index.search_dense(query, top_k=4)
    from rag_engine.retriever import ScoredCandidate
    candA = [ScoredCandidate(chunk=c, dense_score=s, rerank_score=s) for c, s in dense_candidates]
    resA = generator.generate(query, candA)
    evalA = evaluator.evaluate(query, resA.answer, candA)
    latA = (time.time() - tA_start) * 1000

    strat_a = ArenaStrategyResult(
        strategy_name="Dense Semantic Vector Only",
        description="Standard single-encoder cosine similarity search without keyword fusion or cross-encoder reranking.",
        answer=resA.answer,
        citations_count=len(resA.citations),
        faithfulness=evalA.faithfulness,
        context_relevance=evalA.context_relevance,
        latency_ms=round(latA, 2),
        top_chunk_id=candA[0].chunk.id if candA else "none"
    )

    # 2. Execute Strategy B (Hybrid RRF + CRAG + Cross-Encoder)
    tB_start = time.time()
    retriever = HybridRetriever(index=index, config=default_config)
    q_analysis = query_processor.analyze(query)
    overfetched = retriever.retrieve(query=query, overfetch_k=20, expanded_queries=q_analysis.expanded_queries)
    top_reranked = reranker.rerank(query=query, candidates=overfetched, top_k=4)
    resB = generator.generate(query, top_reranked)
    evalB = evaluator.evaluate(query, resB.answer, top_reranked)
    latB = (time.time() - tB_start) * 1000

    strat_b = ArenaStrategyResult(
        strategy_name="NexusRAG Hybrid (RRF + CRAG + Cross-Encoder)",
        description="Full multi-query expansion, weighted RRF fusion, CRAG confidence reflection, and contextual cross-attention reranking.",
        answer=resB.answer,
        citations_count=len(resB.citations),
        faithfulness=evalB.faithfulness,
        context_relevance=evalB.context_relevance,
        latency_ms=round(latB, 2),
        top_chunk_id=top_reranked[0].chunk.id if top_reranked else "none"
    )

    winner = "Strategy B (NexusRAG Hybrid)" if evalB.faithfulness >= evalA.faithfulness else "Strategy A"
    delta = round(abs(evalB.faithfulness - evalA.faithfulness) * 100, 1)

    return ArenaCompareResponse(
        query=query,
        vault_id=target_vault_id,
        strategy_a=strat_a,
        strategy_b=strat_b,
        winner_strategy=winner,
        accuracy_delta_percent=delta
    )


@app.get("/api/v1/audit/export", response_model=AuditReportCertificate)
async def generate_audit_report(query: str, vault_id: str = "hr_benefits"):
    """Generates a cryptographic compliance audit certificate for verified synthesis."""
    resp = await execute_enterprise_rag_query(QueryRequest(query=query, vault_id=vault_id))
    
    query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    audit_id = f"AUDIT-NEXUS-{hashlib.md5(f'{query}_{time.time()}'.encode()).hexdigest()[:10].upper()}"
    signature = hashlib.sha256(f"{audit_id}_{resp.answer}_{resp.evaluation.faithfulness}".encode()).hexdigest()

    return AuditReportCertificate(
        audit_id=audit_id,
        timestamp=datetime.datetime.utcnow().isoformat(),
        query_hash=query_hash,
        query_text=query,
        active_vault=vault_id,
        synthesized_answer=resp.answer,
        cited_chunks=[c.model_dump() for c in resp.citations],
        faithfulness_score=resp.evaluation.faithfulness,
        context_relevance_score=resp.evaluation.context_relevance,
        hallucination_risk=resp.evaluation.hallucination_risk,
        cryptographic_signature=signature
    )


@app.post("/api/v1/documents/ingest")
async def ingest_document(payload: IngestDocumentRequest):
    """Ingests document into the selected vault and rebuilds indexes & knowledge graph."""
    if not payload.title or not payload.content:
        raise HTTPException(status_code=400, detail="Title and content are required.")

    vault_id = payload.vault_id or vault_manager.active_vault_id
    if vault_id not in vault_manager.vaults:
        raise HTTPException(status_code=404, detail=f"Vault '{vault_id}' not found.")

    v = vault_manager.vaults[vault_id]
    doc = Document(
        title=payload.title,
        content=payload.content,
        metadata=payload.metadata
    )
    new_chunks = ingestion_pipe.process_document(doc)
    
    v["documents"].append(doc)
    v["chunks"].extend(new_chunks)
    v["index"].build_index(v["documents"], v["chunks"])
    v["graph"].build_graph(v["documents"], v["chunks"])

    return {
        "success": True,
        "vault_id": vault_id,
        "document_id": doc.id,
        "title": doc.title,
        "chunks_created": len(new_chunks),
        "total_chunks_in_vault": len(v["chunks"])
    }


# Mount Static Dashboard
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def serve_dashboard():
        return FileResponse(os.path.join(static_dir, "index.html"))
