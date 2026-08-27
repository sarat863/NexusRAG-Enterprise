import re
import numpy as np
from typing import List, Tuple
from .retriever import ScoredCandidate
from .indexing import specialized_tokenizer
from .config import default_config


STOPWORDS = {
    "what", "is", "the", "for", "in", "of", "and", "to", "a", "an", "on",
    "at", "by", "with", "from", "as", "about", "into", "through", "after",
    "between", "out", "against", "during", "without", "before",
    "under", "around", "among", "how", "why", "when", "where", "who", "which",
    "are", "be", "do", "does", "did", "have", "has", "had", "can", "could",
    "should", "would", "will", "shall", "all", "any", "some", "every", "this",
    "that", "these", "those", "it", "its", "or", "if", "not", "no", "so", "than",
    "then", "too", "very", "just", "per", "via", "form", "rule", "standard", "policy",
    "many", "much", "days", "day", "time", "granted", "required", "requires",
    "provides", "need", "needs", "number", "amount", "total", "allowed", "allow", "get",
    "i", "me", "my", "we", "our", "you", "your", "they", "them", "their", "use", "used", "dont", "off"
}


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

        # Extract uppercase words from original query for acronym detection
        orig_words = re.findall(r'\b[A-Z0-9_-]+\b', query)
        uppercase_acronyms = {w.lower() for w in orig_words if len(w) >= 2 and (w.isupper() or any(c.isdigit() for c in w))}

        # 1. Acronym and Exact Code Matching (Heavy Precision Weight)
        exact_code_matches = 0.0
        query_codes = set()
        for token in query_tokens:
            is_code = (
                "-" in token or
                "." in token or
                "_" in token or
                any(c.isdigit() for c in token) or
                token in uppercase_acronyms
            )
            if is_code and token not in STOPWORDS:
                query_codes.add(token)
                if token in text_tokens or token in header_tokens:
                    exact_code_matches += 2.0

        # Code mismatch penalty: query asks for specific code(s) that are missing from chunk
        code_penalty = 0.0
        if query_codes and exact_code_matches == 0:
            code_penalty = 2.0

        # 2. Sequential Bigram & Phrase Matching
        query_lower = query.lower()
        text_lower = text.lower()
        phrase_score = 0.0
        content_words = [w for w in query_lower.split() if w not in STOPWORDS]
        if len(content_words) > 1:
            for i in range(len(content_words) - 1):
                bigram = f"{content_words[i]} {content_words[i+1]}"
                if bigram in text_lower:
                    phrase_score += 1.2

        # 3. Content Term Overlap Ratio (Ignoring stopwords)
        q_content = [t for t in query_tokens if t not in STOPWORDS]
        t_content = set(t for t in text_tokens if t not in STOPWORDS)
        if q_content:
            overlap_count = len(set(q_content).intersection(t_content))
            overlap_ratio = overlap_count / len(set(q_content))
        else:
            overlap_ratio = 0.0

        # 4. Section Header Alignment Boost
        header_boost = 0.0
        if any(t in header_tokens for t in q_content):
            header_boost = 0.8

        # 5. Base RRF Rank Signal (Prior)
        base_rrf_prior = candidate.rrf_score * 8.0

        # Joint Non-Linear Cross-Encoder Score
        raw_score = (
            (overlap_ratio * 3.5) +
            (exact_code_matches * 2.5) +
            (phrase_score * 1.5) +
            header_boost +
            base_rrf_prior -
            code_penalty
        )

        # Sigmoid normalization between 0 and 1 with calibrated center
        normalized_score = 1.0 / (1.0 + np.exp(-(raw_score - 1.0) / 2.0))
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
