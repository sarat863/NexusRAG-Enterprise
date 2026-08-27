from typing import List, Dict, Any, Tuple
from pydantic import BaseModel
from .ingestion import Chunk
from .indexing import HybridIndex
from .config import default_config


class ScoredCandidate(BaseModel):
    chunk: Chunk
    dense_rank: int = -1
    dense_score: float = 0.0
    sparse_rank: int = -1
    sparse_score: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float = 0.0


class HybridRetriever:
    """
    Advanced Multi-Strategy Hybrid Retriever.
    Supports:
    1. Simultaneous Vector Search (Dense) + BM25 Search (Sparse)
    2. Tunable Hybrid Weighting Ratio (alpha in [0.0, 1.0])
    3. Reciprocal Rank Fusion (RRF) with custom k parameter
    4. Multi-Query and HyDE Candidate Aggregation
    """

    def __init__(self, index: HybridIndex, config=default_config):
        self.index = index
        self.config = config

    def reciprocal_rank_fusion(
        self,
        dense_results: List[Tuple[Chunk, float]],
        sparse_results: List[Tuple[Chunk, float]],
        k: int = 60,
        alpha: float = 0.5,
        top_k: int = 20
    ) -> List[ScoredCandidate]:
        """
        Merges dense and sparse rankings using Weighted Reciprocal Rank Fusion:
        Score(d) = alpha * (1 / (k + rank_dense)) + (1 - alpha) * (1 / (k + rank_sparse))
        """
        candidates: Dict[str, ScoredCandidate] = {}

        # 1. Process Dense Vector Results
        for rank, (chunk, score) in enumerate(dense_results, start=1):
            if chunk.id not in candidates:
                candidates[chunk.id] = ScoredCandidate(chunk=chunk)
            candidate = candidates[chunk.id]
            candidate.dense_rank = rank
            candidate.dense_score = score
            candidate.rrf_score += (2.0 * alpha) * (1.0 / (k + rank))

        # 2. Process Sparse BM25 Results
        for rank, (chunk, score) in enumerate(sparse_results, start=1):
            if chunk.id not in candidates:
                candidates[chunk.id] = ScoredCandidate(chunk=chunk)
            candidate = candidates[chunk.id]
            candidate.sparse_rank = rank
            candidate.sparse_score = score
            candidate.rrf_score += (2.0 * (1.0 - alpha)) * (1.0 / (k + rank))

        # 3. Sort candidates by RRF Score descending
        sorted_candidates = sorted(
            candidates.values(),
            key=lambda x: x.rrf_score,
            reverse=True
        )

        return sorted_candidates[:top_k]

    def retrieve(
        self,
        query: str,
        overfetch_k: int = 20,
        alpha: float = 0.5,
        k: int = 60,
        expanded_queries: List[str] = None
    ) -> List[ScoredCandidate]:
        """
        Executes parallel hybrid retrieval across primary query and expanded queries.
        """
        dense_results = self.index.search_dense(query, top_k=overfetch_k)
        sparse_results = self.index.search_sparse(query, top_k=overfetch_k)

        # Merge candidate pools if expanded sub-queries are provided
        if expanded_queries:
            for eq in expanded_queries:
                dense_extra = self.index.search_dense(eq, top_k=5)
                sparse_extra = self.index.search_sparse(eq, top_k=5)
                dense_results.extend(dense_extra)
                sparse_results.extend(sparse_extra)

        rrf_candidates = self.reciprocal_rank_fusion(
            dense_results=dense_results,
            sparse_results=sparse_results,
            k=k or self.config.rrf_k,
            alpha=alpha,
            top_k=overfetch_k
        )

        return rrf_candidates
