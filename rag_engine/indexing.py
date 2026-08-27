import os
import re
import json
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
import requests

from .ingestion import Chunk, Document
from .config import default_config


def normalize_leetspeak(text: str) -> str:
    """Normalizes common leetspeak character substitutions inside words."""
    def de_leet_word(match):
        w = match.group(0)
        # Preserve pure numbers or short technical codes like P0, P1, V2, L1, H1
        if w.isdigit() or re.match(r"^\d+([.-]\d+)*$", w) or len(w) <= 2:
            return w
        if "-" in w:
            parts = w.split("-")
            trans = str.maketrans("01345@", "oieasa")
            return "-".join([p if (p.isdigit() or (len(p) >= 3 and p.isdigit())) else p.translate(trans) for p in parts])
        if any(c.isalpha() for c in w) and any(c in "01345@" for c in w):
            trans = str.maketrans("01345@", "oieasa")
            return w.translate(trans)
        return w

    return re.sub(r"[A-Za-z0-9_-]+", de_leet_word, text)


def specialized_tokenizer(text: str) -> List[str]:
    """
    Tokenizes text while strictly preserving:
    - Acronyms (e.g., PTO, SLA, HIPAA, RRF, RAG)
    - Form/Policy IDs (e.g., Form HR-402, ISO-27001, API-v2, Sec-14.3)
    - Alphanumeric codes and exact terms.
    - Normalizes leetspeak/obfuscation.
    """
    cleaned = normalize_leetspeak(text)
    # Matches words with hyphens, underscores, dots, or standalone words/numbers
    tokens = re.findall(r'[A-Za-z0-9]+(?:[-_.][A-Za-z0-9]+)*|[A-Za-z0-9]+', cleaned.lower())
    return tokens


class DenseEmbeddingModel:
    """
    Dense semantic embedding generator.
    Supports OpenAI text-embedding-3-small or localized high-dimensional semantic vectorizer.
    """

    def __init__(self, api_key: str = "", dimension: int = 384):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.dimension = dimension
        self.vectorizer = None
        self.svd = None
        self._fitted = False

    def _fit_fallback_model(self, corpus: List[str]):
        """Fits localized TF-IDF + Latent Semantic Analysis on the corpus for dense semantic representation."""
        if not corpus:
            return
        n_features = max(100, min(5000, len(corpus) * 20))
        self.vectorizer = TfidfVectorizer(
            tokenizer=specialized_tokenizer,
            token_pattern=None,
            ngram_range=(1, 2),
            max_features=n_features
        )
        tfidf_matrix = self.vectorizer.fit_transform(corpus)
        n_samples, n_feats = tfidf_matrix.shape
        max_possible_components = min(n_samples, n_feats)
        if max_possible_components >= 5:
            n_components = min(self.dimension, max_possible_components - 2)
            if n_components >= 1:
                algo = 'arpack' if max_possible_components > n_components else 'randomized'
                self.svd = TruncatedSVD(n_components=n_components, algorithm=algo, random_state=42)
                self.svd.fit(tfidf_matrix)
                self._fitted = True
            else:
                self.svd = None
                self._fitted = False
        else:
            self.svd = None
            self._fitted = False

    def get_embedding(self, text: str) -> np.ndarray:
        """Get dense vector for a single query or chunk."""
        # If OpenAI key is available, attempt remote embedding
        if self.api_key:
            try:
                url = "https://api.openai.com/v1/embeddings"
                headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
                payload = {"input": text, "model": "text-embedding-3-small"}
                resp = requests.post(url, headers=headers, json=payload, timeout=8)
                if resp.status_code == 200:
                    data = resp.json()
                    vec = np.array(data["data"][0]["embedding"], dtype=np.float32)
                    norm = np.linalg.norm(vec)
                    return vec / (norm + 1e-10)
            except Exception as e:
                pass

        # Fallback local semantic vector computation
        if self.vectorizer and self.svd and self._fitted:
            tfidf = self.vectorizer.transform([text])
            vec = self.svd.transform(tfidf)[0].astype(np.float32)
            norm = np.linalg.norm(vec)
            return vec / (norm + 1e-10)

        # Basic deterministic semantic projection
        vec = np.zeros(self.dimension, dtype=np.float32)
        tokens = specialized_tokenizer(text)
        for t in tokens:
            idx = abs(hash(t)) % self.dimension
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        return vec / (norm + 1e-10)

    def embed_corpus(self, texts: List[str]) -> np.ndarray:
        """Batch embed list of texts."""
        if not self.api_key:
            self._fit_fallback_model(texts)
        embeddings = [self.get_embedding(t) for t in texts]
        return np.array(embeddings, dtype=np.float32)


class HybridIndex:
    """
    Step 2: Hybrid Indexing Layer.
    Stores and manages Dense Semantic Vectors + Sparse BM25 Index.
    """

    def __init__(self, config=default_config):
        self.config = config
        self.chunks: List[Chunk] = []
        self.documents: Dict[str, Document] = {}
        
        # Dense Index
        self.embed_model = DenseEmbeddingModel(api_key=config.openai_api_key, dimension=config.embedding_dim)
        self.dense_embeddings: Optional[np.ndarray] = None
        
        # Sparse BM25 Index
        self.bm25_index: Optional[BM25Okapi] = None
        self.corpus_tokens: List[List[str]] = []

    def build_index(self, documents: List[Document], chunks: List[Chunk]):
        """Builds both dense and sparse representations for all document chunks."""
        self.documents = {d.id: d for d in documents}
        self.chunks = chunks
        
        if not chunks:
            self.dense_embeddings = None
            self.bm25_index = None
            self.corpus_tokens = []
            return

        texts = [c.content for c in chunks]
        
        # 1. Build Dense Index
        self.dense_embeddings = self.embed_model.embed_corpus(texts)
        
        # 2. Build Sparse BM25 Index with Specialized Acronym-Preserving Tokenizer
        self.corpus_tokens = [specialized_tokenizer(t) for t in texts]
        self.bm25_index = BM25Okapi(self.corpus_tokens)

    def add_chunks(self, new_chunks: List[Chunk], new_docs: List[Document]):
        """Incrementally adds new chunks and rebuilds indexes."""
        for d in new_docs:
            self.documents[d.id] = d
        updated_chunks = self.chunks + new_chunks
        self.build_index(list(self.documents.values()), updated_chunks)

    def search_dense(self, query: str, top_k: int = 20) -> List[Tuple[Chunk, float]]:
        """Dense semantic search using cosine similarity."""
        if not self.chunks or self.dense_embeddings is None:
            return []

        query_vec = self.embed_model.get_embedding(query)
        # Cosine similarity over normalized embeddings is dot product
        scores = np.dot(self.dense_embeddings, query_vec)
        
        # Get top-k indices
        top_k = min(top_k, len(self.chunks))
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = [(self.chunks[idx], float(scores[idx])) for idx in top_indices]
        return results

    def search_sparse(self, query: str, top_k: int = 20) -> List[Tuple[Chunk, float]]:
        """Sparse keyword search using BM25 with acronym preservation."""
        if not self.chunks or self.bm25_index is None:
            return []

        query_tokens = specialized_tokenizer(query)
        if not query_tokens:
            return []

        scores = self.bm25_index.get_scores(query_tokens)
        top_k = min(top_k, len(self.chunks))
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = [(self.chunks[idx], float(scores[idx])) for idx in top_indices]
        return results

    def save(self, filepath: str):
        """Persists the hybrid index and chunks to disk."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        data = {
            "documents": [d.model_dump() for d in self.documents.values()],
            "chunks": [c.model_dump() for c in self.chunks]
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self, filepath: str):
        """Loads index data from disk and rebuilds dense and sparse indices."""
        if not os.path.exists(filepath):
            return
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        docs = [Document(**d) for d in data.get("documents", [])]
        chunks = [Chunk(**c) for c in data.get("chunks", [])]
        self.build_index(docs, chunks)
