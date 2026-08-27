import re
import uuid
import datetime
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

from .pdf_inspector_engine import pdf_engine, PDFInspectionReport, PDFExtractionResult, extract_tables_from_markdown
from .format_parsers import DocumentFormatParsers, ParsedDocument


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
    Extracts raw text, PDF pages, Word documents (.docx), Excel sheets (.xlsx), CSV tables,
    and structural metadata (URL, page number, timestamp, section headers).
    Applies table-aware, layout-preserving, token-aware overlapping chunking.
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

    def _split_text_and_tables(self, text: str) -> List[Dict[str, Any]]:
        """
        Separates standard text paragraphs from markdown tables (| col | col |)
        to prevent table corruption during token sliding window splitting.
        """
        blocks = []
        lines = text.splitlines()
        current_text_lines = []
        current_table_lines = []
        in_table = False

        for line in lines:
            trimmed = line.strip()
            if trimmed.startswith("|") and trimmed.endswith("|"):
                if not in_table:
                    if current_text_lines:
                        blocks.append({"type": "text", "content": "\n".join(current_text_lines).strip()})
                        current_text_lines = []
                    in_table = True
                current_table_lines.append(line)
            else:
                if in_table:
                    if current_table_lines:
                        blocks.append({"type": "table", "content": "\n".join(current_table_lines).strip()})
                        current_table_lines = []
                    in_table = False
                current_text_lines.append(line)

        if in_table and current_table_lines:
            blocks.append({"type": "table", "content": "\n".join(current_table_lines).strip()})
        elif current_text_lines:
            blocks.append({"type": "text", "content": "\n".join(current_text_lines).strip()})

        return [b for b in blocks if b["content"]]

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
        Preserves complete sentences and isolated table structures.
        """
        blocks = self._split_text_and_tables(text)
        if not blocks:
            return []

        chunks: List[Chunk] = []
        chunk_idx = start_chunk_idx

        for block in blocks:
            if block["type"] == "table":
                # Tables are preserved intact as high-fidelity structured chunks
                table_text = block["content"]
                words = table_text.split()
                chunk_id = f"chunk_{doc_id}_{chunk_idx}"
                
                chunk_metadata = {
                    **base_metadata,
                    "source": base_metadata.get("source", doc_title),
                    "url": base_metadata.get("url", ""),
                    "page_number": base_metadata.get("page_number", page_num),
                    "section_header": section_header,
                    "timestamp": base_metadata.get("timestamp", datetime.datetime.utcnow().isoformat()),
                    "chunk_index": chunk_idx,
                    "token_estimate": len(words),
                    "has_table": True,
                    "layout_type": "table_block"
                }

                chunks.append(Chunk(
                    id=chunk_id,
                    doc_id=doc_id,
                    doc_title=doc_title,
                    content=table_text,
                    metadata=chunk_metadata,
                    token_count=len(words)
                ))
                chunk_idx += 1
            else:
                # Text block sliding window
                words = block["content"].split()
                if not words:
                    continue

                step = max(1, self.chunk_size - self.chunk_overlap)
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
                        "token_estimate": len(chunk_words),
                        "has_table": False,
                        "layout_type": "standard_text"
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
        Processes a standard text/markdown document by extracting sections and generating overlapping chunks
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

    def process_pdf(
        self,
        pdf_bytes: bytes,
        filename: str = "document.pdf",
        vault_id: str = "default",
        base_metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[Document, List[Chunk], PDFInspectionReport]:
        """
        High-speed layout-aware PDF ingestion pipeline powered by firecrawl/pdf-inspector.
        """
        extraction_res: PDFExtractionResult = pdf_engine.extract_structured_markdown(pdf_bytes, filename)
        report: PDFInspectionReport = extraction_res.inspection_report

        title = extraction_res.title or filename
        meta = base_metadata.copy() if base_metadata else {}
        meta.update({
            "doc_format": "pdf",
            "filename": filename,
            "vault_id": vault_id,
            "pdf_type": report.pdf_type,
            "confidence": report.confidence,
            "page_count": report.page_count,
            "table_count": report.table_count,
            "has_tables": len(report.pages_with_tables) > 0,
            "has_columns": len(report.pages_with_columns) > 0,
            "is_complex_layout": report.is_complex_layout,
            "ocr_routing_action": report.ocr_routing_action,
            "inspection_time_ms": report.processing_time_ms
        })

        doc = Document(
            title=title,
            content=extraction_res.full_markdown,
            metadata=meta
        )

        all_chunks: List[Chunk] = []

        for page_data in extraction_res.pages:
            p_num = page_data.page_number
            p_text = page_data.markdown.strip()
            if not p_text:
                continue

            page_meta = meta.copy()
            page_meta.update({
                "page_number": p_num,
                "needs_ocr": page_data.needs_ocr,
                "page_has_tables": page_data.has_tables,
                "page_has_columns": page_data.has_columns
            })

            sections = self.extract_section_headers(p_text)
            for sec in sections:
                header = sec["header"]
                sec_text = sec["text"]
                if not sec_text.strip():
                    continue

                page_chunks = self.chunk_text_sliding_window(
                    text=sec_text,
                    doc_id=doc.id,
                    doc_title=doc.title,
                    base_metadata=page_meta,
                    section_header=header,
                    page_num=p_num,
                    start_chunk_idx=len(all_chunks)
                )
                all_chunks.extend(page_chunks)

        if not all_chunks and doc.content.strip():
            all_chunks = self.process_document(doc)

        return doc, all_chunks, report

    def process_docx(
        self,
        docx_bytes: bytes,
        filename: str = "document.docx",
        vault_id: str = "default",
        base_metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[Document, List[Chunk]]:
        """Parses Microsoft Word (.docx) file into structured document and chunks."""
        parsed: ParsedDocument = DocumentFormatParsers.parse_docx(docx_bytes, filename)
        meta = base_metadata.copy() if base_metadata else {}
        meta.update(parsed.metadata)
        meta.update({"doc_format": "docx", "vault_id": vault_id})

        doc = Document(
            title=parsed.title,
            content=parsed.markdown_content,
            metadata=meta
        )
        chunks = self.process_document(doc)
        return doc, chunks

    def process_xlsx(
        self,
        xlsx_bytes: bytes,
        filename: str = "spreadsheet.xlsx",
        vault_id: str = "default",
        base_metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[Document, List[Chunk]]:
        """Parses Microsoft Excel (.xlsx) workbook into structured document and chunks."""
        parsed: ParsedDocument = DocumentFormatParsers.parse_xlsx(xlsx_bytes, filename)
        meta = base_metadata.copy() if base_metadata else {}
        meta.update(parsed.metadata)
        meta.update({"doc_format": "xlsx", "vault_id": vault_id})

        doc = Document(
            title=parsed.title,
            content=parsed.markdown_content,
            metadata=meta
        )
        chunks = self.process_document(doc)
        return doc, chunks

    def process_csv(
        self,
        csv_bytes: bytes,
        filename: str = "dataset.csv",
        vault_id: str = "default",
        base_metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[Document, List[Chunk]]:
        """Parses CSV tabular file into structured document and chunks."""
        parsed: ParsedDocument = DocumentFormatParsers.parse_csv(csv_bytes, filename)
        meta = base_metadata.copy() if base_metadata else {}
        meta.update(parsed.metadata)
        meta.update({"doc_format": "csv", "vault_id": vault_id})

        doc = Document(
            title=parsed.title,
            content=parsed.markdown_content,
            metadata=meta
        )
        chunks = self.process_document(doc)
        return doc, chunks

    def process_any_file(
        self,
        file_bytes: bytes,
        filename: str,
        vault_id: str = "default",
        base_metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[Document, List[Chunk], Dict[str, Any]]:
        """
        Universal format router: Handles PDF, DOCX, XLSX, CSV, Markdown, and TXT.
        """
        ext = filename.lower().split(".")[-1] if "." in filename else "txt"
        info = {"format": ext, "filename": filename}

        if ext == "pdf":
            doc, chunks, report = self.process_pdf(file_bytes, filename, vault_id, base_metadata)
            info["pdf_report"] = report.model_dump()
            return doc, chunks, info
        elif ext == "docx":
            doc, chunks = self.process_docx(file_bytes, filename, vault_id, base_metadata)
            return doc, chunks, info
        elif ext in ["xlsx", "xls"]:
            doc, chunks = self.process_xlsx(file_bytes, filename, vault_id, base_metadata)
            return doc, chunks, info
        elif ext == "csv":
            doc, chunks = self.process_csv(file_bytes, filename, vault_id, base_metadata)
            return doc, chunks, info
        else:
            # Text / Markdown
            content = file_bytes.decode("utf-8", errors="replace")
            meta = base_metadata.copy() if base_metadata else {}
            meta.update({"doc_format": ext, "vault_id": vault_id, "filename": filename})
            title = filename.rsplit(".", 1)[0].replace("_", " ").title()
            doc = Document(title=title, content=content, metadata=meta)
            chunks = self.process_document(doc)
            return doc, chunks, info
