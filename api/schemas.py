from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from rag_engine.evaluator import RAGTriadEvaluation, SentenceVerification
from rag_engine.query_expansion import QueryAnalysis
from rag_engine.knowledge_graph import GraphData, GraphNode, GraphLink
from rag_engine.vault_manager import KnowledgeVaultInfo


class IngestDocumentRequest(BaseModel):
    title: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    vault_id: Optional[str] = "hr_benefits"


class SwitchVaultRequest(BaseModel):
    vault_id: str


class QueryRequest(BaseModel):
    query: str
    vault_id: Optional[str] = "hr_benefits"
    top_k_rerank: Optional[int] = 4
    overfetch_k: Optional[int] = 20
    alpha_hybrid_weight: Optional[float] = 0.5   # 0.0 (BM25 only) to 1.0 (Dense only)
    rrf_k: Optional[int] = 60
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


class CitationItem(BaseModel):
    chunk_id: str
    doc_title: str
    section_header: str
    page_number: Any
    url: str = ""
    snippet: str = ""


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
    citations: List[CitationItem]
    retrieved_chunks: List[RetrievalStepItem]
    query_analysis: QueryAnalysis
    evaluation: RAGTriadEvaluation
    latency: LatencyBreakdown
    model_used: str
    is_hallucination_guarded: bool = True
    crag_reflection: Optional[Dict[str, Any]] = None
