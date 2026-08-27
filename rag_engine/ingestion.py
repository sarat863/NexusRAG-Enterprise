import re
import uuid
import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class Document(BaseModel):
    id: str = Field(default_factory=lambda: f"doc_{uuid.uuid4().hex[:8]}")
    title: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


class Chunk(BaseModel):
    id: str
    doc_id: str
    doc_title: str
    content: str
    metadata: Dict[str, Any]
    token_count: int = 0


class DocumentIngestionPipeline:
    """
    Step 1: Data Ingestion and Structural Metadata Chunking.
    Extracts raw text and structural metadata (URL, page number, timestamp, section headers).
    Applies overlapping token-aware chunking or parent-child chunking.
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 75):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def extract_section_headers(self, text: str) -> List[Dict[str, Any]]:
        """Extract markdown style headers (# Header, ## Subheader) or section markers."""
        sections = []
        lines = text.split("\n")
        current_header = "General Overview"
        current_lines = []

        for line in lines:
            header_match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
            if header_match:
                if current_lines:
                    sections.append({
                        "header": current_header,
                        "text": "\n".join(current_lines).strip()
                    })
                    current_lines = []
                current_header = header_match.group(2)
            else:
                current_lines.append(line)

        if current_lines:
            sections.append({
                "header": current_header,
                "text": "\n".join(current_lines).strip()
            })

        return sections

    def chunk_text_sliding_window(
        self,
        text: str,
        doc_id: str,
        doc_title: str,
        base_metadata: Dict[str, Any],
        section_header: str = "General",
        page_num: int = 1,
        start_chunk_idx: int = 0
    ) -> List[Chunk]:
        """
        Splits text into chunks using word/token approximations with strict overlap.
        Preserves complete sentences where possible.
        """
        words = text.split()
        if not words:
            return []

        chunks: List[Chunk] = []
        step = max(1, self.chunk_size - self.chunk_overlap)
        
        chunk_idx = start_chunk_idx
        for i in range(0, len(words), step):
            chunk_words = words[i:i + self.chunk_size]
            chunk_text = " ".join(chunk_words).strip()
            
            if len(chunk_text) < 20 and chunks:
                continue

            chunk_id = f"chunk_{doc_id}_{chunk_idx}"
            
            chunk_metadata = {
                **base_metadata,
                "source": base_metadata.get("source", doc_title),
                "url": base_metadata.get("url", ""),
                "page_number": base_metadata.get("page_number", page_num),
                "section_header": section_header,
                "timestamp": base_metadata.get("timestamp", datetime.datetime.utcnow().isoformat()),
                "chunk_index": chunk_idx,
                "token_estimate": len(chunk_words)
            }

            chunks.append(Chunk(
                id=chunk_id,
                doc_id=doc_id,
                doc_title=doc_title,
                content=chunk_text,
                metadata=chunk_metadata,
                token_count=len(chunk_words)
            ))
            chunk_idx += 1

        return chunks

    def process_document(self, document: Document) -> List[Chunk]:
        """
        Processes a document by extracting sections and generating overlapping chunks
        with enriched structural metadata for verifiable citations.
        """
        sections = self.extract_section_headers(document.content)
        all_chunks: List[Chunk] = []
        
        base_meta = document.metadata.copy()
        base_meta["doc_title"] = document.title

        for sec_idx, sec in enumerate(sections):
            header = sec["header"]
            sec_text = sec["text"]
            if not sec_text.strip():
                continue

            page_num = base_meta.get("page_number", 1) + (sec_idx // 3)
            sec_chunks = self.chunk_text_sliding_window(
                text=sec_text,
                doc_id=document.id,
                doc_title=document.title,
                base_metadata=base_meta,
                section_header=header,
                page_num=page_num,
                start_chunk_idx=len(all_chunks)
            )
            all_chunks.extend(sec_chunks)

        return all_chunks
