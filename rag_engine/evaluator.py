import re
from typing import List, Dict, Any
from pydantic import BaseModel
from .retriever import ScoredCandidate
from .indexing import specialized_tokenizer


class SentenceVerification(BaseModel):
    sentence: str
    is_grounded: bool
    confidence: float
    cited_chunk_id: str = ""
    evidence_snippet: str = ""


class RAGTriadEvaluation(BaseModel):
    context_relevance: float         # 0.0 - 1.0
    faithfulness: float              # 0.0 - 1.0 (Groundedness)
    answer_relevance: float          # 0.0 - 1.0
    overall_confidence: float        # Harmonic mean
    hallucination_risk: str          # "LOW", "MEDIUM", "HIGH"
    sentence_verifications: List[SentenceVerification]


class RAGTriadEvaluator:
    """
    RAGOps Observability & Triad Evaluation Engine.
    Computes:
    1. Context Relevance: Quality of retrieved chunks relative to query.
    2. Faithfulness / Groundedness: Percentage of answer sentences supported by cited chunks.
    3. Answer Relevance: Direct alignment of the response with user question.
    """

    def evaluate_context_relevance(self, query: str, candidates: List[ScoredCandidate]) -> float:
        """Calculates average semantic and keyword relevance of top retrieved context chunks."""
        if not candidates:
            return 0.0
        
        q_tokens = set(specialized_tokenizer(query))
        if not q_tokens:
            return 1.0

        scores = []
        for c in candidates:
            c_tokens = set(specialized_tokenizer(c.chunk.content))
            overlap = len(q_tokens.intersection(c_tokens)) / max(1, len(q_tokens))
            rerank_weight = c.rerank_score
            scores.append((overlap * 0.4) + (rerank_weight * 0.6))

        return round(float(sum(scores) / len(scores)), 3)

    def evaluate_sentence_faithfulness(
        self,
        sentence: str,
        candidates_map: Dict[str, ScoredCandidate]
    ) -> SentenceVerification:
        """Verifies if an individual sentence is grounded in its cited chunk or retrieved context."""
        s_clean = re.sub(r'\[Source:\s*[a-zA-Z0-9_-]+\]', '', sentence).strip()
        if not s_clean:
            return SentenceVerification(sentence=sentence, is_grounded=True, confidence=1.0)

        # Extract cited chunk id if present
        match = re.search(r'\[Source:\s*([a-zA-Z0-9_-]+)\]', sentence)
        cited_id = match.group(1) if match else ""

        target_text = ""
        if cited_id and cited_id in candidates_map:
            target_text = candidates_map[cited_id].chunk.content
        else:
            # Check across all candidates
            target_text = " ".join([c.chunk.content for c in candidates_map.values()])

        s_tokens = set(specialized_tokenizer(s_clean))
        target_tokens = set(specialized_tokenizer(target_text))

        if not s_tokens:
            return SentenceVerification(sentence=s_clean, is_grounded=True, confidence=1.0)

        overlap = len(s_tokens.intersection(target_tokens)) / max(1, len(s_tokens))
        is_grounded = overlap >= 0.35 or "i don't know" in s_clean.lower()
        confidence = round(min(1.0, overlap * 1.5), 3)

        return SentenceVerification(
            sentence=s_clean,
            is_grounded=is_grounded,
            confidence=confidence,
            cited_chunk_id=cited_id,
            evidence_snippet=target_text[:140] + "..." if target_text else "No source evidence."
        )

    def evaluate_answer_relevance(self, query: str, answer: str) -> float:
        """Measures how well the answer addresses the core nouns/acronyms of the query."""
        if "i don't know" in answer.lower():
            return 1.0  # Proper faithful refusal

        q_tokens = set(specialized_tokenizer(query))
        a_tokens = set(specialized_tokenizer(answer))

        if not q_tokens or not a_tokens:
            return 0.5

        overlap = len(q_tokens.intersection(a_tokens)) / max(1, len(q_tokens))
        return round(min(1.0, 0.4 + (overlap * 0.7)), 3)

    def evaluate(self, query: str, answer: str, candidates: List[ScoredCandidate]) -> RAGTriadEvaluation:
        """Full RAG Triad assessment."""
        candidates_map = {c.chunk.id: c for c in candidates}
        
        # 1. Context Relevance
        context_rel = self.evaluate_context_relevance(query, candidates)

        # 2. Faithfulness / Groundedness per sentence
        # Split by sentence boundaries while keeping the [Source: chunk_id] with its sentence
        raw_sentences = re.findall(r'[^.!?]+(?:[.!?]+)?(?:\s*\[Source:\s*[a-zA-Z0-9_-]+\])?', answer)
        sentences = [s.strip() for s in raw_sentences if s.strip() and not s.strip().startswith("[Source:")]
        if not sentences:
            sentences = [answer]

        verifications = [
            self.evaluate_sentence_faithfulness(s, candidates_map) for s in sentences
        ]

        grounded_count = sum(1 for v in verifications if v.is_grounded)
        faithfulness = round(grounded_count / max(1, len(verifications)), 3)

        # 3. Answer Relevance
        ans_rel = self.evaluate_answer_relevance(query, answer)

        # Harmonic Overall Confidence
        denom = (1 / max(0.01, context_rel)) + (1 / max(0.01, faithfulness)) + (1 / max(0.01, ans_rel))
        overall = round(3 / denom, 3)

        # Hallucination Risk
        if faithfulness >= 0.85:
            risk = "LOW"
        elif faithfulness >= 0.60:
            risk = "MEDIUM"
        else:
            risk = "HIGH"

        return RAGTriadEvaluation(
            context_relevance=context_rel,
            faithfulness=faithfulness,
            answer_relevance=ans_rel,
            overall_confidence=overall,
            hallucination_risk=risk,
            sentence_verifications=verifications
        )
