import os
from pydantic import BaseModel

class RAGConfig(BaseModel):
    # Ingestion & Chunking
    chunk_size: int = 500              # Target tokens per chunk
    chunk_overlap: int = 75           # 15% overlap
    min_chunk_len: int = 40           # Minimum characters to consider a valid chunk
    
    # Hybrid Retrieval
    vector_top_k: int = 20            # Over-fetch dense vector results
    bm25_top_k: int = 20              # Over-fetch sparse keyword results
    rrf_k: int = 60                   # Standard Reciprocal Rank Fusion constant
    
    # Cross-Encoder Reranking
    rerank_top_k: int = 4             # Final precision results sent to LLM (3-5 chunks)
    
    # Embedding & LLM
    embedding_dim: int = 384
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    # Storage paths
    data_dir: str = os.path.join(os.getcwd(), "data")
    index_file: str = os.path.join(os.getcwd(), "data", "hybrid_index.json")
    
    # PDF Inspector & OCR routing
    enable_pdf_inspector: bool = True
    pdf_ocr_routing_threshold: float = 0.5
    preserve_table_chunks: bool = True

default_config = RAGConfig()
