import re
import requests
from typing import List, Dict, Any
from pydantic import BaseModel
from .config import default_config


class QueryAnalysis(BaseModel):
    original_query: str
    intent: str
    hyde_document: str
    expanded_queries: List[str]
    detected_entities: List[str]


class AgenticQueryProcessor:
    """
    Step 1 of Advanced RAG: Agentic Query Intelligence.
    Provides:
    1. Query Intent Classification & Routing
    2. HyDE (Hypothetical Document Embeddings) Generation
    3. Multi-Query Perspective Expansion
    4. Entity & Acronym Detection
    """

    def __init__(self, api_key: str = "", model: str = ""):
        self.api_key = api_key or default_config.openai_api_key
        self.model = model or default_config.openai_model

    def classify_intent(self, query: str) -> str:
        """Classifies the query intent to customize retrieval weights and constraints."""
        q_lower = query.lower()

        if any(w in q_lower for w in ["martian", "alien", "magic", "recipe", "dragon", "superhero"]):
            return "out_of_domain"
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
        # Find uppercase acronyms or hyphenated codes
        entities = re.findall(r'[A-Z0-9]+(?:[-_.][A-Z0-9]+)+|[A-Z]{2,}', query)
        # Find form mentions like "Form HR-402"
        forms = re.findall(r'Form\s+[A-Za-z0-9-]+', query, re.IGNORECASE)
        combined = list(dict.fromkeys(entities + forms))
        return combined

    def generate_hyde_document(self, query: str) -> str:
        """
        Generates a hypothetical document answering the query.
        Used to bridge vocabulary mismatch between user questions and document corpora.
        """
        # If OpenAI API is available, generate neural hypothetical doc
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

        # High-speed deterministic HyDE template synthesis
        intent = self.classify_intent(query)
        entities = self.detect_entities(query)
        ent_str = f" regarding {', '.join(entities)}" if entities else ""

        if intent == "policy_compliance":
            return f"Official Corporate Policy Specification{ent_str}. In accordance with mandatory compliance rules and operational directives, all personnel must adhere to the prescribed guidelines, authorization forms, and filing timelines."
        elif intent == "sre_metrics":
            return f"Production Infrastructure Service Level Agreement Specification{ent_str}. Mission-critical Tier-1 services require strict uptime availability thresholds, automated incident triggers, and defined recovery targets."
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
        else:
            expansions.append(f"overview specifications guidelines principles{ent_phrase}")
            expansions.append(f"definitions requirements and operational details{ent_phrase}")

        return expansions[:3]

    def analyze(self, query: str) -> QueryAnalysis:
        """Full query intelligence analysis."""
        intent = self.classify_intent(query)
        detected = self.detect_entities(query)
        hyde = self.generate_hyde_document(query)
        expanded = self.expand_multi_query(query)

        return QueryAnalysis(
            original_query=query,
            intent=intent,
            hyde_document=hyde,
            expanded_queries=expanded,
            detected_entities=detected
        )
