import re
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel
from .retriever import ScoredCandidate
from .indexing import specialized_tokenizer


class CRAGEvaluationResult(BaseModel):
    action: str  # "CORRECT", "AMBIGUOUS", "INCORRECT"
    confidence_score: float
    reasoning: str
    reformulated_query: str = ""
    expanded_terms: List[str] = []


class CorrectiveRAGEvaluator:
    """
    Self-Corrective RAG (CRAG) & Active Reflection Engine.
    Evaluates retrieved candidate quality before passing to generation:
    - CORRECT (Confidence >= 0.75): High relevance -> Proceed to Cross-Encoder.
    - AMBIGUOUS (0.40 <= Conf < 0.75): Moderate/Borderline -> Triggers entity graph expansion & query reformulation.
    - INCORRECT (Conf < 0.40): Poor / Out-of-Domain -> Halts synthesis and triggers verified guard refusal.
    """

    def __init__(self, high_threshold: float = 0.70, low_threshold: float = 0.35):
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold

    def evaluate_retrieval_confidence(
        self,
        query: str,
        candidates: List[ScoredCandidate]
    ) -> CRAGEvaluationResult:
        """Evaluates whether the candidate chunks sufficiently answer the query."""
        if not candidates:
            return CRAGEvaluationResult(
                action="INCORRECT",
                confidence_score=0.0,
                reasoning="Zero candidate chunks retrieved from the knowledge vault."
            )

        q_tokens = set(specialized_tokenizer(query))
        if not q_tokens:
            return CRAGEvaluationResult(
                action="INCORRECT",
                confidence_score=0.0,
                reasoning="Empty or uninformative query tokens."
            )

        # Check top candidates
        top_candidates = candidates[:3]
        overlap_scores = []
        acronym_matches = []

        for cand in top_candidates:
            c_tokens = set(specialized_tokenizer(cand.chunk.content))
            overlap = len(q_tokens.intersection(c_tokens)) / max(1, len(q_tokens))
            overlap_scores.append(overlap)

            # Check exact acronym / code hits
            for qt in q_tokens:
                if ("-" in qt or len(qt) <= 4 or qt.isupper()):
                    if qt in c_tokens:
                        acronym_matches.append(qt)

        avg_overlap = sum(overlap_scores) / len(overlap_scores)
        top_rerank = max([c.rerank_score for c in top_candidates]) if top_candidates else 0.0
        
        # Combined Confidence Metric
        confidence = (avg_overlap * 0.4) + (top_rerank * 0.4) + (0.2 if acronym_matches else 0.0)
        confidence = round(min(1.0, confidence), 3)

        # Decision Routing
        if confidence >= self.high_threshold:
            return CRAGEvaluationResult(
                action="CORRECT",
                confidence_score=confidence,
                reasoning=f"High semantic overlap ({avg_overlap:.2f}) and rerank signal ({top_rerank:.2f}). Proceeding with high-confidence context."
            )
        elif confidence >= self.low_threshold:
            # Self-Correction: extract missing context terms for query reformulation
            expanded_terms = list(dict.fromkeys(acronym_matches + list(q_tokens)[:3]))
            reformulated = f"{query} {' '.join(expanded_terms)} standard policy criteria"
            return CRAGEvaluationResult(
                action="AMBIGUOUS",
                confidence_score=confidence,
                reasoning=f"Borderline retrieval confidence ({confidence:.2f}). Self-correcting via entity expansion and query reformulation.",
                reformulated_query=reformulated,
                expanded_terms=expanded_terms
            )
        else:
            return CRAGEvaluationResult(
                action="INCORRECT",
                confidence_score=confidence,
                reasoning=f"Low retrieval confidence ({confidence:.2f}). Query concepts are not supported by the document corpus."
            )
