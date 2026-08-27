import re
import requests
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from .config import default_config


class QueryAnalysis(BaseModel):
    original_query: str
    rewritten_query: Optional[str] = None
    intent: str
    hyde_document: str
    expanded_queries: List[str]
    detected_entities: List[str]
    coreference_resolved: bool = False


class AgenticQueryProcessor:
    """
    Step 1 of Advanced RAG: Agentic Query Intelligence.
    Provides:
    1. Multi-Turn Coreference Resolution & Conversational Query Rewriting
    2. Query Intent Classification & Routing (including Quantitative Math)
    3. HyDE (Hypothetical Document Embeddings) Generation
    4. Multi-Query Perspective Expansion
    5. Entity & Acronym Detection
    """

    def __init__(self, api_key: str = "", model: str = ""):
        self.api_key = api_key or default_config.openai_api_key
        self.model = model or default_config.openai_model

    def rewrite_conversational_query(self, query: str, history: Optional[List[Dict[str, Any]]] = None) -> Tuple[str, bool]:
        """
        Resolves coreference pronouns and contextual omissions from conversational session history.
        Transforms ambiguous follow-up questions (e.g. 'Who must sign it?') into self-contained search queries
        (e.g. 'Who must sign Form HR-402?').
        """
        if not history:
            return query, False

        q_lower = query.lower().strip()
        coref_cues = [
            " it ", " it?", " it.", " its ", " this ", " that ", " they ", " them ", " these ", " those ",
            " the form", " the policy", " the requirement", " the deadline", " the sla",
            " the former", " the latter", " sign it", " submit it", " for it", " with it", " about it"
        ]
        has_coref = any(cue in f" {q_lower} " for cue in coref_cues) or q_lower.startswith(("who must sign", "how long", "what about", "who approves", "when is it", "why is it"))

        if not has_coref:
            return query, False

        # Attempt neural query rewriting if OpenAI key is present
        if self.api_key:
            try:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
                chat_context = "\n".join([f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}" for m in history[-6:]])
                prompt = (
                    f"Given the conversation history:\n{chat_context}\n\n"
                    f"Rewrite the follow-up user query into a standalone, unambiguous search query: '{query}'\n"
                    f"Return ONLY the rewritten query string without any quotes or explanation."
                )
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 80
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=5)
                if resp.status_code == 200:
                    rewritten = resp.json()["choices"][0]["message"]["content"].strip()
                    if rewritten and len(rewritten) > 3:
                        return rewritten, True
            except Exception:
                pass

        # High-precision deterministic coreference resolution
        # Scan history backwards for primary subject entities, forms, and acronyms
        extracted_entities = []
        for msg in reversed(history[-6:]):
            content = msg.get("content", "")
            ents = self.detect_entities(content)
            if ents:
                extracted_entities.extend(ents)
                break

        if not extracted_entities:
            # Check for general topic keywords
            for msg in reversed(history[-6:]):
                content = msg.get("content", "")
                for topic in ["PTO", "Medical Leave", "Disaster Recovery", "SLA", "HIPAA", "Quantum", "MFA", "FIDO2", "RTO", "RPO"]:
                    if topic.lower() in content.lower():
                        extracted_entities.append(topic)
                        break
                if extracted_entities:
                    break

        if not extracted_entities:
            return query, False

        primary_subject = extracted_entities[0]

        # Formulate rewritten query replacing pronoun or appending subject
        rewritten = query
        for pronoun in [" it?", " it.", " it", " this?", " this.", " this", " that?", " that.", " that"]:
            if pronoun in rewritten:
                rewritten = rewritten.replace(pronoun, f" {primary_subject}" + (pronoun[-1] if pronoun[-1] in "?." else ""))
                return rewritten.strip(), True

        rewritten = f"{query} for {primary_subject}"
        return rewritten.strip(), True

    def classify_intent(self, query: str) -> str:
        """Classifies the query intent to customize retrieval weights and constraints."""
        q_lower = query.lower()

        if any(w in q_lower for w in ["martian", "alien", "magic", "recipe", "dragon", "superhero"]):
            return "out_of_domain"
        elif any(w in q_lower for w in ["calculate", "accrue", "how many days will i have", "math", "total days", "compute", "sum", "deduct"]):
            return "quantitative_calculation"
        elif any(w in q_lower for w in ["form", "hr-", "rule", "standard", "policy", "iso-", "hipaa", "sec-"]):
            return "policy_compliance"
        elif any(w in q_lower for w in ["rto", "rpo", "sla", "uptime", "latency", "minutes", "seconds", "tier-"]):
            return "sre_metrics"
        elif any(w in q_lower for w in ["difference", "compare", "versus", "vs", "between"]):
            return "comparative_synthesis"
        elif any(w in q_lower for w in ["how to", "steps", "procedure", "process", "guide"]):
            return "procedural"
        else:
            return "factoid"

    def detect_entities(self, query: str) -> List[str]:
        """Detects key acronyms, form codes, and uppercase identifiers."""
        forms = re.findall(r'Form\s+[A-Za-z0-9-]+', query, re.IGNORECASE)
        entities = re.findall(r'[A-Z0-9]+(?:[-_.][A-Z0-9]+)+|[A-Z]{2,}', query)
        combined = list(dict.fromkeys(forms + entities))
        return combined

    def generate_hyde_document(self, query: str) -> str:
        """
        Generates a hypothetical document answering the query.
        Used to bridge vocabulary mismatch between user questions and document corpora.
        """
        if self.api_key:
            try:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
                prompt = f"Write a brief, hypothetical official corporate policy document passage that accurately answers this query: '{query}'."
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 120
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=6)
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception:
                pass

        intent = self.classify_intent(query)
        entities = self.detect_entities(query)
        ent_str = f" regarding {', '.join(entities)}" if entities else ""

        if intent == "policy_compliance":
            return f"Official Corporate Policy Specification{ent_str}. In accordance with mandatory compliance rules and operational directives, all personnel must adhere to the prescribed guidelines, authorization forms, and filing timelines."
        elif intent == "sre_metrics":
            return f"Production Infrastructure Service Level Agreement Specification{ent_str}. Mission-critical Tier-1 services require strict uptime availability thresholds, automated incident triggers, and defined recovery targets."
        elif intent == "quantitative_calculation":
            return f"Quantitative Policy Calculation and Entitlement Schedule{ent_str}. Governs the mathematical formulas for accruals, rollover limits, and calculated balances."
        else:
            return f"Standard Operating Procedure and Enterprise Knowledge Base Documentation{ent_str}. Outlines the relevant criteria, entitlements, and administrative protocols governing the requested inquiry."

    def expand_multi_query(self, query: str) -> List[str]:
        """
        Decomposes query into 3 distinct perspectives to maximize retrieval recall:
        1. Exact keyword & code formulation
        2. Semantic conceptual rephrasing
        3. Compliance / procedural perspective
        """
        intent = self.classify_intent(query)
        entities = self.detect_entities(query)
        ent_phrase = f" {' '.join(entities)}" if entities else ""

        expansions = [query]

        if intent == "policy_compliance":
            expansions.append(f"mandatory policy requirements rules filing procedure{ent_phrase}")
            expansions.append(f"official documentation form submission instructions{ent_phrase}")
        elif intent == "sre_metrics":
            expansions.append(f"service level agreement recovery objectives targets{ent_phrase}")
            expansions.append(f"production infrastructure availability standards and metrics{ent_phrase}")
        elif intent == "quantitative_calculation":
            expansions.append(f"accrual rate monthly entitlement days calculation{ent_phrase}")
            expansions.append(f"pto schedule deduction balance formula{ent_phrase}")
        else:
            expansions.append(f"overview specifications guidelines principles{ent_phrase}")
            expansions.append(f"definitions requirements and operational details{ent_phrase}")

        return expansions[:3]

    def analyze(self, query: str, history: Optional[List[Dict[str, Any]]] = None) -> QueryAnalysis:
        """Full query intelligence analysis with coreference resolution."""
        rewritten, was_resolved = self.rewrite_conversational_query(query, history)
        effective_query = rewritten if was_resolved else query

        intent = self.classify_intent(effective_query)
        detected = self.detect_entities(effective_query)
        hyde = self.generate_hyde_document(effective_query)
        expanded = self.expand_multi_query(effective_query)

        return QueryAnalysis(
            original_query=query,
            rewritten_query=rewritten if was_resolved else None,
            intent=intent,
            hyde_document=hyde,
            expanded_queries=expanded,
            detected_entities=detected,
            coreference_resolved=was_resolved
        )
