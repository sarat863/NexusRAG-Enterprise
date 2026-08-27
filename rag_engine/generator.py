import os
import re
import requests
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from .retriever import ScoredCandidate
from .config import default_config


class Citation(BaseModel):
    chunk_id: str
    doc_title: str
    section_header: str
    page_number: Any
    url: str = ""
    snippet: str = ""


class RAGResponse(BaseModel):
    query: str
    answer: str
    citations: List[Citation]
    retrieved_chunks: List[Dict[str, Any]]
    model_used: str
    is_hallucination_guarded: bool = True


class CitationEnforcedGenerator:
    """
    Step 5: Generate with Enforced Citations.
    Uses strict prompt engineering to prevent hallucinations and force
    the model to cite the exact chunk_id for every claim made.
    """

    SYSTEM_PROMPT = """You are an expert assistant. Answer the user's question using ONLY the provided context chunks.
If the answer is not in the context, say "I don't know".
For every claim you make, append an inline citation using the chunk's ID, like this: [Source: chunk_id].
Do NOT use outside knowledge. Do NOT hallucinate information not present in the context chunks."""

    def __init__(self, api_key: str = "", model: str = ""):
        self.api_key = api_key or default_config.openai_api_key
        self.model = model or default_config.openai_model

    def build_context_prompt(self, candidates: List[ScoredCandidate]) -> str:
        """
        Formats the top reranked chunks with explicit IDs and structural metadata.
        """
        context_parts = []
        for c in candidates:
            chunk = c.chunk
            meta = chunk.metadata
            part = (
                f"--- START CONTEXT CHUNK ---\n"
                f"[Chunk ID: {chunk.id}]\n"
                f"[Document: {chunk.doc_title}]\n"
                f"[Section: {meta.get('section_header', 'General')}]\n"
                f"[Page: {meta.get('page_number', 1)}]\n"
                f"Content:\n{chunk.content}\n"
                f"--- END CONTEXT CHUNK ---"
            )
            context_parts.append(part)

        return "\n\n".join(context_parts)

    def extract_citations(self, answer: str, candidates: List[ScoredCandidate]) -> List[Citation]:
        """
        Parses all [Source: chunk_id] tags from the generated text and resolves
        them against the retrieved candidate metadata.
        """
        cited_ids = re.findall(r'\[Source:\s*([a-zA-Z0-9_-]+)\]', answer)
        unique_ids = list(dict.fromkeys(cited_ids))

        candidate_map = {c.chunk.id: c.chunk for c in candidates}
        citations: List[Citation] = []

        for cid in unique_ids:
            if cid in candidate_map:
                chunk = candidate_map[cid]
                citations.append(Citation(
                    chunk_id=cid,
                    doc_title=chunk.doc_title,
                    section_header=chunk.metadata.get("section_header", "General"),
                    page_number=chunk.metadata.get("page_number", 1),
                    url=chunk.metadata.get("url", ""),
                    snippet=chunk.content[:160] + "..."
                ))

        return citations

    def _generate_deterministic_fallback(self, query: str, candidates: List[ScoredCandidate]) -> str:
        """
        High-precision deterministic factual synthesizer with enforced citations.
        Used when no OpenAI API key is supplied. Strictly returns 'I don't know'
        if no meaningful query terms match the context.
        """
        stopwords = {
            "what", "is", "the", "for", "in", "of", "and", "to", "a", "an", "on",
            "at", "by", "with", "from", "as", "about", "into", "through", "after",
            "over", "between", "out", "against", "during", "without", "before",
            "under", "around", "among", "how", "why", "when", "where", "who", "which"
        }
        raw_query_words = set(re.findall(r'[a-zA-Z0-9_-]+', query.lower()))
        content_query_words = raw_query_words - stopwords

        if not content_query_words:
            return "I don't know. The question does not contain sufficient specific terms to match the knowledge base."

        matched_sentences = []

        for cand in candidates:
            chunk = cand.chunk
            sentences = re.split(r'(?<=[.!?])\s+', chunk.content)
            for s in sentences:
                s_clean = s.strip()
                if not s_clean:
                    continue
                s_words = set(re.findall(r'[a-zA-Z0-9_-]+', s_clean.lower()))
                overlap = len(content_query_words.intersection(s_words))
                if overlap >= 1:
                    # Score boost for exact acronyms, numbers or codes in query
                    code_boost = 0
                    for qw in content_query_words:
                        if ("-" in qw or len(qw) <= 4 or qw.isupper()):
                            if qw in s_words:
                                code_boost += 2
                    total_score = overlap + code_boost
                    if total_score >= 2:
                        matched_sentences.append((s_clean, chunk.id, total_score))

        if not matched_sentences:
            return "I don't know. The provided context chunks do not contain sufficient information to answer this question."

        # Sort by relevance overlap descending
        matched_sentences.sort(key=lambda x: x[2], reverse=True)
        # Deduplicate sentences while maintaining order
        seen = set()
        top_sentences = []
        for text, cid, score in matched_sentences:
            if text not in seen:
                seen.add(text)
                top_sentences.append((text, cid, score))
            if len(top_sentences) >= 3:
                break

        answer_parts = []
        for text, chunk_id, _ in top_sentences:
            answer_parts.append(f"{text} [Source: {chunk_id}]")

        return " ".join(answer_parts)

    def generate(self, query: str, top_candidates: List[ScoredCandidate]) -> RAGResponse:
        """
        Executes generation with enforced citations.
        """
        if not top_candidates:
            return RAGResponse(
                query=query,
                answer="I don't know. No relevant document chunks were found in the knowledge base.",
                citations=[],
                retrieved_chunks=[],
                model_used="none"
            )

        context_text = self.build_context_prompt(top_candidates)
        model_used = "deterministic-rule-engine"
        answer = ""

        # Attempt OpenAI generation if key exists
        if self.api_key:
            try:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                user_content = f"Context:\n{context_text}\n\nQuestion: {query}\n\nAnswer with inline [Source: chunk_id] citations:"
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_content}
                    ],
                    "temperature": 0.0,
                    "max_tokens": 600
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    answer = data["choices"][0]["message"]["content"].strip()
                    model_used = f"OpenAI ({self.model})"
            except Exception as e:
                pass

        if not answer:
            answer = self._generate_deterministic_fallback(query, top_candidates)

        # Extract & verify citations
        citations = self.extract_citations(answer, top_candidates)

        # Serialize retrieved chunks for API response transparency
        retrieved_data = []
        for c in top_candidates:
            retrieved_data.append({
                "chunk_id": c.chunk.id,
                "doc_title": c.chunk.doc_title,
                "section_header": c.chunk.metadata.get("section_header", ""),
                "page_number": c.chunk.metadata.get("page_number", 1),
                "dense_rank": c.dense_rank,
                "dense_score": round(c.dense_score, 4),
                "sparse_rank": c.sparse_rank,
                "sparse_score": round(c.sparse_score, 4),
                "rrf_score": round(c.rrf_score, 5),
                "rerank_score": round(c.rerank_score, 4),
                "content": c.chunk.content
            })

        return RAGResponse(
            query=query,
            answer=answer,
            citations=citations,
            retrieved_chunks=retrieved_data,
            model_used=model_used,
            is_hallucination_guarded=True
        )

    async def generate_stream(self, query: str, top_candidates: List[ScoredCandidate]):
        """
        Asynchronously yields generated tokens word-by-word with progressive citation tags.
        """
        if not top_candidates:
            yield "I don't know. The provided context chunks do not contain sufficient information to answer this question."
            return

        rag_resp = self.generate(query, top_candidates)
        words = rag_resp.answer.split(" ")
        for i, w in enumerate(words):
            yield w + (" " if i < len(words) - 1 else "")
            import asyncio
            await asyncio.sleep(0.015)  # Smooth token stream pacing
