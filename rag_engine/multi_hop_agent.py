import time
import uuid
import re
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

from .retriever import HybridRetriever, ScoredCandidate
from .reranker import CrossEncoderReranker
from .crag import CorrectiveRAGEvaluator, CRAGEvaluationResult
from .generator import CitationEnforcedGenerator, RAGResponse
from .evaluator import RAGTriadEvaluator


class MultiHopStepTrace(BaseModel):
    """Execution trace of a single hop in the autonomous research loop."""
    hop_number: int
    sub_query: str
    target_vault: str
    retrieved_chunk_ids: List[str] = Field(default_factory=list)
    evidence_summary: str = ""
    gaps_identified: List[str] = Field(default_factory=list)
    contradictions_resolved: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    action_taken: str = "SEARCH"


class MultiHopResearchResult(BaseModel):
    """Comprehensive result of the Multi-Hop Autonomous Research Agent."""
    original_query: str
    final_answer: str
    hops_taken: int
    total_chunks_consulted: int
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    hop_traces: List[MultiHopStepTrace] = Field(default_factory=list)
    faithfulness_score: float = 0.95
    hallucination_risk: str = "LOW"
    execution_time_ms: float = 0.0


class MultiHopResearchAgent:
    """
    Multi-Hop Autonomous Research Agent (WisDev ARC YOLO Loop Evolution).
    
    Dynamically decomposes multi-faceted questions into sequential sub-queries,
    retrieves across isolated departmental vaults, evaluates gaps/contradictions,
    and synthesizes multi-source citation-enforced answers.
    """

    def __init__(
        self,
        retriever_map: Optional[Dict[str, HybridRetriever]] = None,
        unified_retriever: Optional[HybridRetriever] = None,
        reranker: Optional[CrossEncoderReranker] = None,
        generator: Optional[CitationEnforcedGenerator] = None,
        evaluator: Optional[RAGTriadEvaluator] = None,
        max_hops: int = 3,
        confidence_threshold: float = 0.82,
        vault_manager: Optional[Any] = None
    ):
        self.retriever_map = retriever_map or {}
        self.unified_retriever = unified_retriever or (next(iter(self.retriever_map.values())) if self.retriever_map else None)
        self.reranker = reranker or CrossEncoderReranker(top_n=4)
        self.generator = generator or CitationEnforcedGenerator()
        self.evaluator = evaluator or RAGTriadEvaluator()
        self.max_hops = max_hops
        self.confidence_threshold = confidence_threshold
        self.vault_manager = vault_manager

    def get_retriever_for_vault(self, vault_key: str) -> Optional[HybridRetriever]:
        """Dynamically resolves retriever from live VaultManager state or fallback map."""
        if self.vault_manager is not None and hasattr(self.vault_manager, "vaults"):
            target = vault_key if vault_key in self.vault_manager.vaults else "all"
            if target in self.vault_manager.vaults:
                return HybridRetriever(index=self.vault_manager.vaults[target]["index"])
        return self.retriever_map.get(vault_key, self.unified_retriever)

    def _decompose_query(self, query: str) -> List[Tuple[str, str]]:
        """
        Decomposes compound or multi-hop queries into sub-queries paired with recommended vaults.
        Returns list of (sub_query, vault_id).
        """
        q_lower = query.lower()
        sub_queries = []

        # Check for conjunctions or compound intents
        parts = re.split(r'\band\b|\balso\b|\bas well as\b|\bcompare to\b|\bwhile\b', query, flags=re.IGNORECASE)
        if len(parts) > 1 and all(len(p.strip()) > 8 for p in parts):
            for part in parts:
                p_text = part.strip()
                p_lower = p_text.lower()
                target_vault = "all"
                if any(k in p_lower for k in ["pto", "leave", "vacation", "benefit", "hr-", "dental", "rollover"]):
                    target_vault = "hr_benefits"
                elif any(k in p_lower for k in ["sre", "sla", "uptime", "rto", "rpo", "kubernetes", "incident", "database", "dr"]):
                    target_vault = "sre_infra"
                elif any(k in p_lower for k in ["hipaa", "iso-", "phi", "pii", "audit", "compliance", "sec-"]):
                    target_vault = "infosec_compliance"
                elif any(k in p_lower for k in ["procure", "gpu", "h100", "quantum", "vendor", "po-"]):
                    target_vault = "procurement_quantum"
                elif any(k in p_lower for k in ["pdf", "standard", "guideline"]):
                    target_vault = "pdf_standards"
                sub_queries.append((p_text, target_vault))
        else:
            # Single main query - default to all or routed vault
            target_vault = "all"
            if any(k in q_lower for k in ["pto", "leave", "vacation", "benefit", "hr-", "rollover"]):
                target_vault = "hr_benefits"
            elif any(k in q_lower for k in ["sre", "sla", "uptime", "rto", "rpo", "failover"]):
                target_vault = "sre_infra"
            elif any(k in q_lower for k in ["hipaa", "iso-", "phi", "sec-"]):
                target_vault = "infosec_compliance"
            sub_queries.append((query, target_vault))

        return sub_queries[:self.max_hops]

    def execute_research_loop(
        self,
        query: str,
        initial_vault_id: Optional[str] = "all"
    ) -> MultiHopResearchResult:
        """
        Executes the iterative multi-hop research cycle until evidence converges.
        """
        start_time = time.time()
        sub_queries = self._decompose_query(query)
        
        all_candidate_chunks: List[ScoredCandidate] = []
        hop_traces: List[MultiHopStepTrace] = []
        seen_chunk_ids = set()

        for hop_idx, (sub_q, target_vault) in enumerate(sub_queries, start=1):
            vault_key = target_vault
            retriever = self.get_retriever_for_vault(vault_key)
            
            if not retriever:
                continue

            # 1. Retrieve candidates for sub-query
            raw_candidates = retriever.retrieve(sub_q, overfetch_k=15, alpha=0.5)
            reranked = self.reranker.rerank(sub_q, raw_candidates, top_k=3)

            new_chunks = []
            hop_chunk_ids = []
            for cand in reranked:
                if cand.chunk.id not in seen_chunk_ids:
                    seen_chunk_ids.add(cand.chunk.id)
                    all_candidate_chunks.append(cand)
                    new_chunks.append(cand)
                hop_chunk_ids.append(cand.chunk.id)

            # 2. Evaluate context sufficiency
            top_score = reranked[0].rerank_score if reranked else 0.0
            gaps = []
            contradictions = []

            if top_score < 0.60:
                gaps.append(f"Insufficient confidence ({top_score:.2f}) for sub-topic: '{sub_q}'")
            if len(reranked) >= 2 and abs(reranked[0].rerank_score - reranked[1].rerank_score) < 0.05:
                contradictions.append("Closely competing policy interpretations detected; fused both candidates.")

            evidence_summary = (
                f"Retrieved {len(reranked)} relevant sources from vault '{vault_key}'. "
                f"Top source: '{reranked[0].chunk.doc_title}' ({reranked[0].chunk.metadata.get('section_header', 'Section')})."
                if reranked else "No confident matches."
            )

            hop_traces.append(MultiHopStepTrace(
                hop_number=hop_idx,
                sub_query=sub_q,
                target_vault=vault_key,
                retrieved_chunk_ids=hop_chunk_ids,
                evidence_summary=evidence_summary,
                gaps_identified=gaps,
                contradictions_resolved=contradictions,
                confidence=round(top_score, 3),
                action_taken="AGGREGATE_AND_CONTINUE" if hop_idx < len(sub_queries) else "CONVERGED"
            ))

        # 3. Final Multi-Source Synthesis
        if all_candidate_chunks:
            # Sort aggregated candidates by highest rerank score
            all_candidate_chunks.sort(key=lambda x: x.rerank_score, reverse=True)
            top_synthesized_cands = all_candidate_chunks[:6]
            
            gen_resp: RAGResponse = self.generator.generate(
                query=query,
                top_candidates=top_synthesized_cands
            )
            final_answer = gen_resp.answer
            citations = [c.model_dump() if hasattr(c, "model_dump") else (c.dict() if hasattr(c, "dict") else c) for c in gen_resp.citations]
        else:
            final_answer = f"I am unable to find sufficient verified documentation across vaults to answer: '{query}'."
            citations = []

        # 4. RAG Triad Groundedness Evaluation
        triad_eval = self.evaluator.evaluate(
            query=query,
            answer=final_answer,
            candidates=all_candidate_chunks[:6]
        )

        elapsed_ms = (time.time() - start_time) * 1000.0

        return MultiHopResearchResult(
            original_query=query,
            final_answer=final_answer,
            hops_taken=len(hop_traces),
            total_chunks_consulted=len(all_candidate_chunks),
            citations=citations,
            hop_traces=hop_traces,
            faithfulness_score=triad_eval.faithfulness,
            hallucination_risk=triad_eval.hallucination_risk,
            execution_time_ms=round(elapsed_ms, 2)
        )
