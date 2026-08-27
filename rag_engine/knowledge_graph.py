import re
from typing import List, Dict, Any, Set
from pydantic import BaseModel
from .ingestion import Chunk, Document


class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # "document", "chunk", "entity", "standard", "role"
    color: str
    size: int
    metadata: Dict[str, Any] = {}


class GraphLink(BaseModel):
    source: str
    target: str
    relation: str
    weight: float = 1.0


class GraphData(BaseModel):
    nodes: List[GraphNode]
    links: List[GraphLink]


class EntityKnowledgeGraph:
    """
    Knowledge Graph Indexer.
    Extracts structured entities (Forms, Acronyms, Standards, Roles) and builds
    a bidirectional graph connecting documents, chunks, and semantic concepts.
    """

    COLOR_PALETTE = {
        "document": "#6366f1",   # Indigo
        "chunk": "#8b5cf6",      # Purple
        "form": "#ec4899",       # Pink
        "standard": "#06b6d4",   # Cyan
        "acronym": "#10b981",    # Emerald
        "role": "#f59e0b"        # Amber
    }

    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.links: List[GraphLink] = []

    def extract_entities_from_text(self, text: str) -> Dict[str, Set[str]]:
        """Extracts typed domain entities using contextual regex patterns."""
        entities: Dict[str, Set[str]] = {
            "form": set(),
            "standard": set(),
            "acronym": set(),
            "role": set()
        }

        # Forms
        forms = re.findall(r'Form\s+[A-Za-z0-9-]+', text, re.IGNORECASE)
        for f in forms:
            entities["form"].add(f.strip())

        # Standards & Rules (e.g. ISO-27001, Rule SEC-881, HIPAA Rule 164.312, TLS 1.3, AES-256)
        standards = re.findall(r'(?:ISO|Rule|HIPAA|TLS|AES|IEEE|FIDO2)[-\s][A-Za-z0-9.]+', text, re.IGNORECASE)
        for s in standards:
            entities["standard"].add(s.strip())

        # Known Acronyms
        acronyms = re.findall(r'\b(?:PTO|SLA|RTO|RPO|MFA|PHI|QPU|SRE|CISO|DR|API|2FA)\b', text)
        for a in acronyms:
            entities["acronym"].add(a.strip())

        # Roles
        roles = re.findall(r'\b(?:HR Department|SRE Lead|CISO Office|VP of Engineering|Administrator)\b', text)
        for r in roles:
            entities["role"].add(r.strip())

        return entities

    def build_graph(self, documents: List[Document], chunks: List[Chunk]):
        """Constructs graph nodes and directed links."""
        self.nodes = {}
        self.links = []
        seen_links = set()

        # 1. Add Document Nodes
        for doc in documents:
            doc_node_id = f"node_doc_{doc.id}"
            self.nodes[doc_node_id] = GraphNode(
                id=doc_node_id,
                label=doc.title,
                type="document",
                color=self.COLOR_PALETTE["document"],
                size=22,
                metadata={"title": doc.title, "url": doc.metadata.get("url", "")}
            )

        # 2. Add Chunk Nodes and Link to Documents
        for chunk in chunks:
            chunk_node_id = f"node_{chunk.id}"
            doc_node_id = f"node_doc_{chunk.doc_id}"

            self.nodes[chunk_node_id] = GraphNode(
                id=chunk_node_id,
                label=chunk.metadata.get("section_header", chunk.id),
                type="chunk",
                color=self.COLOR_PALETTE["chunk"],
                size=14,
                metadata={
                    "doc_title": chunk.doc_title,
                    "section": chunk.metadata.get("section_header", ""),
                    "page": chunk.metadata.get("page_number", 1)
                }
            )

            # Link Document -> Chunk
            if doc_node_id in self.nodes:
                link_key = (doc_node_id, chunk_node_id)
                if link_key not in seen_links:
                    seen_links.add(link_key)
                    self.links.append(GraphLink(
                        source=doc_node_id,
                        target=chunk_node_id,
                        relation="HAS_CHUNK",
                        weight=1.5
                    ))

            # 3. Extract and link typed entities from chunk content
            entities = self.extract_entities_from_text(chunk.content)
            for ent_type, ent_set in entities.items():
                for ent_name in ent_set:
                    ent_node_id = f"ent_{ent_name.lower().replace(' ', '_')}"
                    
                    if ent_node_id not in self.nodes:
                        self.nodes[ent_node_id] = GraphNode(
                            id=ent_node_id,
                            label=ent_name,
                            type=ent_type,
                            color=self.COLOR_PALETTE.get(ent_type, "#10b981"),
                            size=18,
                            metadata={"entity_type": ent_type}
                        )

                    # Link Chunk -> Entity
                    ent_link_key = (chunk_node_id, ent_node_id)
                    if ent_link_key not in seen_links:
                        seen_links.add(ent_link_key)
                        self.links.append(GraphLink(
                            source=chunk_node_id,
                            target=ent_node_id,
                            relation="MENTIONS",
                            weight=1.0
                        ))

    def get_graph_data(self) -> GraphData:
        """Returns graph in D3/Canvas compatible JSON format."""
        return GraphData(
            nodes=list(self.nodes.values()),
            links=self.links
        )
