import re
import numpy as np
from typing import List, Tuple
from .retriever import ScoredCandidate
from .indexing import specialized_tokenizer
from .config import default_config


class CrossEncoderReranker:
    """
    Step 4: Apply Cross-Encoder Reranking (The Precision Layer).
    Re-scores the 15-20 over-fetched candidates by computing joint query-chunk
    contextual interactions and filters down to the top 3-5 high-precision chunks.
    """

    def __init__(self, top_n: int = 4):
        self.top_n = top_n

    def score_pair(self, query: str, candidate: ScoredCandidate) -> float:
        """
        Jointly computes contextual relevance score between query and chunk.
        Evaluates exact phrase matches, acronym density, structural header relevance,
        and term proximity.
        """
        chunk = candidate.chunk
        text = chunk.content
        header = chunk.metadata.get("section_header", "")
        
        query_tokens = specialized_tokenizer(query)
        text_tokens = specialized_tokenizer(text)
        header_tokens = specialized_tokenizer(header)

        if not query_tokens or not text_tokens:
            return 0.0

        # 1. Acronym and Exact Code Matching (Heavy Precision Weight)
        exact_code_matches = 0
        for token in query_tokens:
            # Check for acronyms or hyphenated codes (e.g. HR-402, PTO)
            if ("-" in token or len(token) <= 4 or token.isupper()):
                if token in text_tokens or token in header_tokens:
                    exact_code_matches += 1.5

        # 2. Sequential Bigram & Phrase Matching
        query_lower = query.lower()
        text_lower = text.lower()
        phrase_score = 0.0
        if len(query_lower.split()) > 1:
            # Check for whole sub-phrases
            sub_phrases = [
                " ".join(query_lower.split()[i:i+3])
                for i in range(len(query_lower.split()) - 1)
            ]
            for p in sub_phrases:
                if p in text_lower:
                    phrase_score += 1.0

        # 3. Term Overlap Ratio
        overlap_count = len(set(query_tokens).intersection(set(text_tokens)))
        overlap_ratio = overlap_count / max(1, len(set(query_tokens)))

        # 4. Section Header Alignment Boost
        header_boost = 0.0
        if any(t in header_tokens for t in query_tokens):
            header_boost = 0.8

        # 5. Base RRF Rank Signal (Prior)
        base_rrf_prior = candidate.rrf_score * 10.0

        # Joint Non-Linear Cross-Encoder Score
        raw_score = (
            (overlap_ratio * 3.0) +
            (exact_code_matches * 2.5) +
            (phrase_score * 2.0) +
            header_boost +
            base_rrf_prior
        )

        # Sigmoid normalization between 0 and 1
        normalized_score = 1.0 / (1.0 + np.exp(-raw_score / 3.0))
        return float(normalized_score)

    def rerank(self, query: str, candidates: List[ScoredCandidate], top_k: int = None) -> List[ScoredCandidate]:
        """
        Scores all candidate chunks jointly with the query and returns top 3-5 results.
        """
        k = top_k or self.top_n
        if not candidates:
            return []

        for candidate in candidates:
            candidate.rerank_score = self.score_pair(query, candidate)

        # Sort by Cross-Encoder Rerank Score descending
        reranked = sorted(candidates, key=lambda x: x.rerank_score, reverse=True)
        return reranked[:k]
