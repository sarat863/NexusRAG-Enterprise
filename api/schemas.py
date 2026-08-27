from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from rag_engine.evaluator import RAGTriadEvaluation, SentenceVerification
from rag_engine.query_expansion import QueryAnalysis
from rag_engine.knowledge_graph import GraphData, GraphNode, GraphLink
from rag_engine.vault_manager import KnowledgeVaultInfo
from rag_engine.pdf_inspector_engine import (
    PDFInspectionReport,
    PDFPageMarkdown,
    PDFExtractionResult,
    PDFBenchmarkScore
)


class ChatMessageSchema(BaseModel):
    role: str
    content: str
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class IngestDocumentRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1, max_length=5_000_000)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    vault_id: Optional[str] = "hr_benefits"


class SwitchVaultRequest(BaseModel):
    vault_id: str = Field(..., min_length=1, max_length=100)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10_000)
    vault_id: Optional[str] = "hr_benefits"
    session_id: Optional[str] = None
    history: Optional[List[ChatMessageSchema]] = None
    top_k_rerank: Optional[int] = Field(default=4, ge=1, le=20)
    overfetch_k: Optional[int] = Field(default=20, ge=1, le=100)
    alpha_hybrid_weight: Optional[float] = Field(default=0.5, ge=0.0, le=1.0)   # 0.0 (BM25 only) to 1.0 (Dense only)
    rrf_k: Optional[int] = Field(default=60, ge=1, le=200)
    use_hyde: Optional[bool] = True
    use_multi_query: Optional[bool] = True
    openai_api_key: Optional[str] = ""


class RetrievalStepItem(BaseModel):
    chunk_id: str
    doc_title: str
    section_header: str
    page_number: Any
    content: str
    dense_rank: int
    dense_score: float
    sparse_rank: int
    sparse_score: float
    rrf_score: float
    rerank_score: float
    has_table: Optional[bool] = False
    doc_format: Optional[str] = "text"


class CitationItem(BaseModel):
    chunk_id: str
    doc_title: str
    section_header: str
    page_number: Any
    url: str = ""
    snippet: str = ""
    has_table: Optional[bool] = False
    doc_format: Optional[str] = "text"


class LatencyBreakdown(BaseModel):
    query_expansion_ms: float = 0.0
    retrieval_ms: float = 0.0
    rerank_ms: float = 0.0
    generation_ms: float = 0.0
    evaluation_ms: float = 0.0
    total_ms: float = 0.0


class ArenaStrategyResult(BaseModel):
    strategy_name: str
    description: str
    answer: str
    citations_count: int
    faithfulness: float
    context_relevance: float
    latency_ms: float
    top_chunk_id: str


class ArenaCompareResponse(BaseModel):
    query: str
    vault_id: str
    strategy_a: ArenaStrategyResult   # e.g., Dense Semantic Vector Only
    strategy_b: ArenaStrategyResult   # e.g., Full Hybrid RRF + CRAG + Reranking
    winner_strategy: str
    accuracy_delta_percent: float


class AuditReportCertificate(BaseModel):
    audit_id: str
    timestamp: str
    query_hash: str
    query_text: str
    active_vault: str
    synthesized_answer: str
    cited_chunks: List[Dict[str, Any]]
    faithfulness_score: float
    context_relevance_score: float
    hallucination_risk: str
    cryptographic_signature: str


class RAGQueryResponse(BaseModel):
    query: str
    answer: str
    active_vault_id: str
    session_id: Optional[str] = None
    citations: List[CitationItem]
    retrieved_chunks: List[RetrievalStepItem]
    query_analysis: QueryAnalysis
    evaluation: RAGTriadEvaluation
    latency: LatencyBreakdown
    model_used: str
    is_hallucination_guarded: bool = True
    crag_reflection: Optional[Dict[str, Any]] = None


# ---------------- MULTI-FORMAT & PDF INGESTION SCHEMAS ----------------

class PDFInspectResponse(BaseModel):
    filename: str
    report: PDFInspectionReport
    summary: str


class PDFExtractResponse(BaseModel):
    title: str
    full_markdown: str
    pages: List[PDFPageMarkdown]
    table_blocks: List[str]
    inspection: PDFInspectionReport


class PDFIngestResponse(BaseModel):
    success: bool
    vault_id: str
    document_id: str
    title: str
    chunks_created: int
    table_chunks_created: int
    total_chunks_in_vault: int
    inspection_report: PDFInspectionReport


class MultiFormatUploadResponse(BaseModel):
    success: bool
    vault_id: str
    document_id: str
    title: str
    format: str
    chunks_created: int
    total_chunks_in_vault: int
    details: Optional[Dict[str, Any]] = None


class PDFBenchmarkResponse(BaseModel):
    benchmark: PDFBenchmarkScore
    details: Dict[str, Any]


# ---------------- ENHANCEMENT SCHEMAS ----------------

class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    username: str
    role: str
    expires_in: int = 86400


class MultiHopStepTraceSchema(BaseModel):
    hop_number: int
    sub_query: str
    target_vault: str
    retrieved_chunk_ids: List[str]
    evidence_summary: str
    gaps_identified: List[str]
    contradictions_resolved: List[str]
    confidence: float
    action_taken: str


class MultiHopResearchRequest(BaseModel):
    query: str
    initial_vault_id: Optional[str] = "all"
    max_hops: Optional[int] = 3


class MultiHopResearchResponse(BaseModel):
    query: str
    final_answer: str
    hops_taken: int
    total_chunks_consulted: int
    citations: List[Dict[str, Any]]
    hop_traces: List[MultiHopStepTraceSchema]
    faithfulness_score: float
    hallucination_risk: str
    execution_time_ms: float


class RAPTORNodeSchema(BaseModel):
    node_id: str
    level: int
    title: str
    content: str
    children_ids: List[str]
    parent_id: Optional[str] = None
    vault_id: str
    score: float = 0.0


class RAPTORSearchRequest(BaseModel):
    query: str
    vault_id: Optional[str] = "all"
    top_k: Optional[int] = 4
    target_level: Optional[int] = None


class RAPTORSearchResponse(BaseModel):
    query: str
    vault_id: str
    results_count: int
    results: List[Dict[str, Any]]


class RAPTORVisualizationResponse(BaseModel):
    total_nodes: int
    level_counts: Dict[int, int]
    nodes: List[Dict[str, Any]]
    links: List[Dict[str, Any]]


class DocGenCompileRequest(BaseModel):
    title: str
    query: str
    answer: str
    citations: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    doc_format: Optional[str] = "markdown"  # "markdown", "latex", "html"
    citation_style: Optional[str] = "APA"   # "APA", "IEEE", "MLA", "Chicago"
    author: Optional[str] = "Enterprise Architecture & Governance AI"
    abstract: Optional[str] = None


class DocGenCompileResponse(BaseModel):
    title: str
    doc_format: str
    citation_style: str
    content: str
    citation_count: int
    word_count: int
    generated_at: str


class MCPToolListResponse(BaseModel):
    tools: List[Dict[str, Any]]


class MCPToolCallRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class MCPToolCallResponse(BaseModel):
    tool: str
    content: List[Dict[str, Any]]
    is_error: bool = False


class AuditVerifyRequest(BaseModel):
    audit_id: str


class AuditVerifyResponse(BaseModel):
    audit_id: str
    is_valid: bool
    certificate: Optional[Dict[str, Any]] = None
