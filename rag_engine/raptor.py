import uuid
import re
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import AgglomerativeClustering

from .ingestion import Chunk, Document
from .indexing import DenseEmbeddingModel, specialized_tokenizer


class RAPTORNode(BaseModel):
    """A node in the RAPTOR Hierarchical Tree."""
    node_id: str = Field(default_factory=lambda: f"raptor_{uuid.uuid4().hex[:8]}")
    level: int  # 0 = granular leaf chunk, 1 = section cluster summary, 2 = document abstract
    title: str
    content: str
    children_ids: List[str] = Field(default_factory=list)
    parent_id: Optional[str] = None
    doc_id: str = ""
    vault_id: str = "default"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0


class RAPTORSearchResult(BaseModel):
    """Result from hierarchical RAPTOR tree traversal."""
    node: RAPTORNode
    score: float
    level: int
    matched_children: List[str] = Field(default_factory=list)


class RAPTORIndex:
    """
    RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval.
    
    Builds a 3-layer hierarchical tree:
      Level 0: Granular atomic leaf chunks (500 tokens, tables, section headers)
      Level 1: Clustered section abstractions & summary nodes
      Level 2: Holistic document-level thematic overviews
      
    Retrieval adaptively traverses between high-level thematic summaries and leaf facts.
    """

    def __init__(self, embedding_model: Optional[DenseEmbeddingModel] = None):
        self.embedding_model = embedding_model or DenseEmbeddingModel()
        self.nodes: Dict[str, RAPTORNode] = {}
        self.node_embeddings: Dict[str, np.ndarray] = {}
        self.level_nodes: Dict[int, List[str]] = {0: [], 1: [], 2: []}

    def _summarize_cluster(self, title: str, chunks_text: List[str], level: int) -> str:
        """
        Synthesizes an abstractive cluster summary capturing policies, standards,
        SLA numbers, forms, and constraints across child chunks.
        """
        combined = "\n\n".join(chunks_text)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', combined) if len(s.strip()) > 20]
        
        # Extract salient entities: codes, SLAs, forms, numbers, headers
        salient_lines = []
        seen = set()
        for s in sentences:
            # Prioritize sentences with numbers, acronyms, table lines, or policy rules
            if any(k in s for k in ["SLA", "ISO-", "SEC-", "HR-", "Form", "Tier", "RTO", "RPO", "%", "P0", "P1", "P2", "P3", "|"]) or len(salient_lines) < 4:
                cleaned = s.replace("\n", " ").strip()
                if cleaned not in seen:
                    seen.add(cleaned)
                    salient_lines.append(cleaned)
            if len(salient_lines) >= 6:
                break

        if not salient_lines:
            salient_lines = sentences[:4]

        summary_body = " ".join(salient_lines)
        if level == 1:
            return f"**Section Cluster Summary [{title}]**: {summary_body}"
        elif level == 2:
            return f"**Document Thematic Abstract [{title}]**: Key architectural and regulatory policies established. {summary_body}"
        return summary_body

    def build_raptor_tree(self, chunks: List[Chunk], documents: Optional[List[Document]] = None) -> Dict[str, RAPTORNode]:
        """
        Constructs the full 3-level RAPTOR tree from input leaf chunks.
        """
        self.nodes.clear()
        self.node_embeddings.clear()
        self.level_nodes = {0: [], 1: [], 2: []}

        if not chunks:
            return self.nodes

        # Fit localized fallback embedding model on corpus if needed
        all_texts = [c.content for c in chunks]
        if not self.embedding_model.api_key:
            self.embedding_model._fit_fallback_model(all_texts)

        # -------------------------------------------------------------
        # 1. Level 0: Ingest Leaf Chunks
        # -------------------------------------------------------------
        l0_node_ids = []
        l0_embeddings = []

        for chunk in chunks:
            node = RAPTORNode(
                node_id=chunk.id,
                level=0,
                title=f"{chunk.doc_title} - {chunk.metadata.get('section_header', 'Section')}",
                content=chunk.content,
                children_ids=[],
                parent_id=None,
                doc_id=chunk.doc_id,
                vault_id=chunk.metadata.get("vault_id", "default"),
                metadata=chunk.metadata.copy()
            )
            vec = self.embedding_model.get_embedding(chunk.content)
            
            self.nodes[node.node_id] = node
            self.node_embeddings[node.node_id] = vec
            self.level_nodes[0].append(node.node_id)
            
            l0_node_ids.append(node.node_id)
            l0_embeddings.append(vec)

        # -------------------------------------------------------------
        # 2. Level 1: Cluster Leaf Chunks & Build Section Summaries
        # -------------------------------------------------------------
        l1_node_ids = []
        if len(l0_node_ids) >= 2:
            matrix = np.vstack(l0_embeddings)
            # Normalize for cosine clustering
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            norm_matrix = matrix / norms

            # Dynamic cluster count (approx 2 to 4 chunks per cluster)
            n_clusters = max(1, min(len(l0_node_ids) // 2, 8))
            
            if n_clusters > 1 and len(l0_node_ids) > n_clusters:
                try:
                    clustering = AgglomerativeClustering(
                        n_clusters=n_clusters,
                        metric="cosine",
                        linkage="average"
                    )
                    labels = clustering.fit_predict(norm_matrix)
                except Exception:
                    labels = np.array([i % n_clusters for i in range(len(l0_node_ids))])
            else:
                labels = np.zeros(len(l0_node_ids), dtype=int)

            # Group leaf nodes by cluster label
            clusters: Dict[int, List[str]] = {}
            for idx, label in enumerate(labels):
                clusters.setdefault(int(label), []).append(l0_node_ids[idx])

            # Create Level 1 Summary Nodes
            for cluster_idx, child_ids in clusters.items():
                child_nodes = [self.nodes[cid] for cid in child_ids]
                child_texts = [cn.content for cn in child_nodes]
                
                # Representative title from first child or common header
                common_title = child_nodes[0].title.split(" - ")[0] if child_nodes else f"Cluster {cluster_idx+1}"
                section_title = f"{common_title} (Cluster {cluster_idx+1})"
                
                summary_text = self._summarize_cluster(section_title, child_texts, level=1)
                l1_id = f"raptor_l1_{cluster_idx}_{uuid.uuid4().hex[:6]}"
                
                l1_node = RAPTORNode(
                    node_id=l1_id,
                    level=1,
                    title=section_title,
                    content=summary_text,
                    children_ids=child_ids,
                    parent_id=None,
                    doc_id=child_nodes[0].doc_id,
                    vault_id=child_nodes[0].vault_id,
                    metadata={"child_count": len(child_ids), "cluster_id": cluster_idx, "level": 1}
                )
                
                # Link parents in L0 children
                for cid in child_ids:
                    self.nodes[cid].parent_id = l1_id

                vec = self.embedding_model.get_embedding(summary_text)
                self.nodes[l1_id] = l1_node
                self.node_embeddings[l1_id] = vec
                self.level_nodes[1].append(l1_id)
                l1_node_ids.append(l1_id)
        else:
            l1_node_ids = l0_node_ids

        # -------------------------------------------------------------
        # 3. Level 2: Holistic Document-Level Thematic Abstracts
        # -------------------------------------------------------------
        if l1_node_ids:
            doc_groups: Dict[str, List[str]] = {}
            for l1_id in l1_node_ids:
                doc_id = self.nodes[l1_id].doc_id or "global"
                doc_groups.setdefault(doc_id, []).append(l1_id)

            for doc_id, cluster_ids in doc_groups.items():
                cluster_nodes = [self.nodes[cid] for cid in cluster_ids]
                cluster_texts = [cn.content for cn in cluster_nodes]
                
                doc_title = cluster_nodes[0].title.split(" (Cluster")[0] if cluster_nodes else "Enterprise Policy Document"
                summary_text = self._summarize_cluster(doc_title, cluster_texts, level=2)
                l2_id = f"raptor_l2_{doc_id}_{uuid.uuid4().hex[:6]}"

                l2_node = RAPTORNode(
                    node_id=l2_id,
                    level=2,
                    title=f"Thematic Abstract: {doc_title}",
                    content=summary_text,
                    children_ids=cluster_ids,
                    parent_id=None,
                    doc_id=doc_id,
                    vault_id=cluster_nodes[0].vault_id,
                    metadata={"level": 2, "is_thematic_root": True, "section_count": len(cluster_ids)}
                )

                for cid in cluster_ids:
                    self.nodes[cid].parent_id = l2_id

                vec = self.embedding_model.get_embedding(summary_text)
                self.nodes[l2_id] = l2_node
                self.node_embeddings[l2_id] = vec
                self.level_nodes[2].append(l2_id)

        return self.nodes

    def retrieve_hierarchical(
        self,
        query: str,
        top_k: int = 4,
        target_level: Optional[int] = None,
        vault_id: Optional[str] = None
    ) -> List[RAPTORSearchResult]:
        """
        Hierarchical RAPTOR tree search.
        
        If target_level is None, automatically detects query scope:
        - Thematic queries ("Summarize", "Overview", "Compare", "All SLAs") -> prioritizes Level 1 & 2 summaries.
        - Granular queries ("Form HR-402", "P0 target", specific codes) -> prioritizes Level 0 leaf facts.
        """
        if not self.nodes:
            return []

        query_vec = self.embedding_model.get_embedding(query)
        q_lower = query.lower()
        
        # Scope detection
        is_thematic = any(kw in q_lower for kw in ["summarize", "overview", "compare", "all ", "matrix", "structure", "high-level", "architecture"])
        
        node_scores: List[Tuple[float, RAPTORNode]] = []

        for node_id, node in self.nodes.items():
            if vault_id and vault_id != "all" and node.vault_id not in [vault_id, "default", "all"]:
                continue

            if target_level is not None and node.level != target_level:
                continue

            vec = self.node_embeddings.get(node_id)
            if vec is None:
                continue

            # Cosine similarity
            denom = (np.linalg.norm(query_vec) * np.linalg.norm(vec))
            sim = float(np.dot(query_vec, vec) / denom) if denom > 0 else 0.0

            # Lexical exact match boost
            q_tokens = specialized_tokenizer(query)
            node_tokens = set(specialized_tokenizer(node.content))
            overlap = len([t for t in q_tokens if t in node_tokens]) / max(1, len(q_tokens))
            
            final_score = (0.7 * sim) + (0.3 * overlap)

            # Level-adaptive score bias
            if is_thematic:
                if node.level == 2:
                    final_score += 0.25
                elif node.level == 1:
                    final_score += 0.15
            else:
                if node.level == 0:
                    final_score += 0.20

            node_scores.append((final_score, node))

        # Sort descending
        node_scores.sort(key=lambda x: x[0], reverse=True)
        top_matches = node_scores[:top_k]

        results = []
        for score, node in top_matches:
            node_copy = node.model_copy() if hasattr(node, "model_copy") else node.copy()
            node_copy.score = round(score, 4)
            results.append(RAPTORSearchResult(
                node=node_copy,
                score=round(score, 4),
                level=node.level,
                matched_children=node.children_ids
            ))

        return results

    def get_tree_visualization(self) -> Dict[str, Any]:
        """Exports tree nodes and parent-child links for D3 / UI rendering."""
        nodes_data = []
        links_data = []

        for nid, node in self.nodes.items():
            nodes_data.append({
                "id": node.node_id,
                "label": node.title[:30] + ("..." if len(node.title) > 30 else ""),
                "level": node.level,
                "content_preview": node.content[:100] + "...",
                "vault_id": node.vault_id
            })
            if node.parent_id and node.parent_id in self.nodes:
                links_data.append({
                    "source": node.parent_id,
                    "target": node.node_id,
                    "type": "RAPTOR_CHILD"
                })

        return {
            "total_nodes": len(self.nodes),
            "level_counts": {lvl: len(nids) for lvl, nids in self.level_nodes.items()},
            "nodes": nodes_data,
            "links": links_data
        }
