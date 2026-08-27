import io
import os
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

try:
    import pdf_inspector
    HAS_PDF_INSPECTOR = True
except ImportError:
    HAS_PDF_INSPECTOR = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


class PDFInspectionReport(BaseModel):
    """Structural inspection, classification, and OCR routing report for a PDF."""
    pdf_type: str = "unknown"  # "text_based", "scanned", "image_based", "mixed"
    confidence: float = 1.0
    page_count: int = 0
    processing_time_ms: float = 0.0
    has_encoding_issues: bool = False
    is_complex_layout: bool = False
    pages_with_tables: List[int] = Field(default_factory=list)
    pages_with_columns: List[int] = Field(default_factory=list)
    pages_needing_ocr: List[int] = Field(default_factory=list)
    ocr_reasons_by_page: Dict[str, Any] = Field(default_factory=dict)
    table_count: int = 0
    heading_count: int = 0
    total_characters: int = 0
    ocr_routing_action: str = "NATIVE_PASS"  # "NATIVE_PASS", "SELECTIVE_OCR_REQUIRED", "FULL_OCR_REQUIRED"


class PDFPageMarkdown(BaseModel):
    """Position-aware Markdown and classification metadata for a single PDF page."""
    page_number: int  # 1-indexed for human readability and verifiable citations
    markdown: str
    needs_ocr: bool = False
    ocr_reason: Optional[str] = None
    has_tables: bool = False
    has_columns: bool = False


class PDFExtractionResult(BaseModel):
    """Full extraction results combining structured markdown with inspection report."""
    title: str
    full_markdown: str
    pages: List[PDFPageMarkdown]
    inspection_report: PDFInspectionReport
    table_blocks: List[str] = Field(default_factory=list)


class PDFBenchmarkScore(BaseModel):
    """Benchmark comparing PDF Inspector performance against naive baseline."""
    document_name: str
    page_count: int
    pdf_type: str
    inspection_latency_ms: float
    markdown_extraction_latency_ms: float
    tables_detected: int
    ocr_pages_saved: int
    ocr_cost_avoidance_pct: float
    speedup_factor_vs_ocr: float


def extract_tables_from_markdown(markdown_text: str) -> List[str]:
    """Extracts all markdown table blocks (| col | col |) from the markdown text."""
    if not markdown_text:
        return []
    
    tables = []
    current_table = []
    in_table = False

    for line in markdown_text.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("|") and trimmed.endswith("|"):
            in_table = True
            current_table.append(line)
        else:
            if in_table and current_table:
                tables.append("\n".join(current_table))
                current_table = []
            in_table = False

    if in_table and current_table:
        tables.append("\n".join(current_table))

    return tables


def count_markdown_headings(markdown_text: str) -> int:
    """Counts standard markdown headings (# Header) in text."""
    if not markdown_text:
        return 0
    return len(re.findall(r'^(#{1,6})\s+.*$', markdown_text, re.MULTILINE))


class PDFInspectorEngine:
    """
    High-Performance PDF Intelligence & Extraction Engine.
    Leverages firecrawl/pdf-inspector Rust core for sub-10ms classification,
    dual-mode table detection, column reading order recovery, and selective OCR routing.
    """

    def __init__(self):
        self.available = HAS_PDF_INSPECTOR

    def inspect_pdf_bytes(self, pdf_bytes: bytes, filename: str = "document.pdf") -> PDFInspectionReport:
        """
        Inspects PDF bytes and returns classification, table detection, and OCR requirements.
        Executes in 2-15ms.
        """
        start_time = time.time()
        
        if not self.available:
            # Fallback if binary bindings are unavailable
            return PDFInspectionReport(
                pdf_type="text_based",
                confidence=0.9,
                page_count=1,
                processing_time_ms=1.0,
                ocr_routing_action="NATIVE_PASS"
            )

        try:
            res = pdf_inspector.process_pdf_bytes(pdf_bytes)
            elapsed_ms = (time.time() - start_time) * 1000.0

            raw_type = getattr(res, "pdf_type", "text_based")
            # Normalize enum/string
            pdf_type = str(raw_type).lower().replace("pdftype.", "")
            confidence = float(getattr(res, "confidence", 1.0))
            page_count = int(getattr(res, "page_count", 1))
            has_encoding_issues = bool(getattr(res, "has_encoding_issues", False))
            is_complex_layout = bool(getattr(res, "is_complex_layout", False))
            
            pages_with_tables = list(getattr(res, "pages_with_tables", []))
            pages_with_columns = list(getattr(res, "pages_with_columns", []))
            pages_needing_ocr = list(getattr(res, "pages_needing_ocr", []))

            # Raw OCR reasons
            raw_reasons = getattr(res, "ocr_reasons_by_page", {})
            ocr_reasons = {}
            if isinstance(raw_reasons, dict):
                ocr_reasons = {str(k): str(v) for k, v in raw_reasons.items()}
            elif isinstance(raw_reasons, list):
                ocr_reasons = {str(i): str(r) for i, r in enumerate(raw_reasons)}

            # Markdown analysis
            md_text = getattr(res, "markdown", "") or ""
            table_blocks = extract_tables_from_markdown(md_text)
            headings_count = count_markdown_headings(md_text)

            # Determine OCR routing strategy
            if not pages_needing_ocr or len(pages_needing_ocr) == 0:
                ocr_action = "NATIVE_PASS"
            elif len(pages_needing_ocr) < page_count:
                ocr_action = "SELECTIVE_OCR_REQUIRED"
            else:
                ocr_action = "FULL_OCR_REQUIRED"

            return PDFInspectionReport(
                pdf_type=pdf_type,
                confidence=round(confidence, 3),
                page_count=page_count,
                processing_time_ms=round(elapsed_ms, 2),
                has_encoding_issues=has_encoding_issues,
                is_complex_layout=is_complex_layout,
                pages_with_tables=pages_with_tables,
                pages_with_columns=pages_with_columns,
                pages_needing_ocr=pages_needing_ocr,
                ocr_reasons_by_page=ocr_reasons,
                table_count=len(table_blocks),
                heading_count=headings_count,
                total_characters=len(md_text),
                ocr_routing_action=ocr_action
            )
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000.0
            return PDFInspectionReport(
                pdf_type="scanned",
                confidence=0.5,
                page_count=1,
                processing_time_ms=round(elapsed_ms, 2),
                pages_needing_ocr=[1],
                ocr_routing_action="FULL_OCR_REQUIRED"
            )

    def extract_structured_markdown(self, pdf_bytes: bytes, filename: str = "document.pdf") -> PDFExtractionResult:
        """
        Extracts position-aware Markdown with page-by-page mapping and table preservation.
        """
        inspection = self.inspect_pdf_bytes(pdf_bytes, filename)
        title = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title()

        if not self.available:
            return PDFExtractionResult(
                title=title,
                full_markdown="# Document\nNo PDF Inspector available.",
                pages=[PDFPageMarkdown(page_number=1, markdown="No content")],
                inspection_report=inspection,
                table_blocks=[]
            )

        pages_list: List[PDFPageMarkdown] = []
        full_md_parts: List[str] = []

        try:
            # Per-page extraction with exact layout classification
            pages_res = pdf_inspector.extract_pages_markdown_bytes(pdf_bytes)
            
            table_pages_set = set(getattr(pages_res, "pages_with_tables", []))
            column_pages_set = set(getattr(pages_res, "pages_with_columns", []))
            
            for p in pages_res.pages:
                raw_p_num = getattr(p, "page", 0)
                # Ensure 1-indexed page number
                p_num = raw_p_num + 1 if raw_p_num == 0 or raw_p_num < len(pages_res.pages) else raw_p_num
                if hasattr(p, "page"):
                    p_num = p.page + 1

                md = getattr(p, "markdown", "") or ""
                needs_ocr = bool(getattr(p, "needs_ocr", False))
                ocr_reason = getattr(p, "ocr_reason", None)
                if ocr_reason is not None:
                    ocr_reason = str(ocr_reason)

                has_tables = (p_num - 1) in table_pages_set or (p_num in table_pages_set) or bool(extract_tables_from_markdown(md))
                has_columns = (p_num - 1) in column_pages_set or (p_num in column_pages_set)

                page_obj = PDFPageMarkdown(
                    page_number=p_num,
                    markdown=md,
                    needs_ocr=needs_ocr,
                    ocr_reason=ocr_reason,
                    has_tables=has_tables,
                    has_columns=has_columns
                )
                pages_list.append(page_obj)
                if md.strip():
                    full_md_parts.append(f"<!-- Page {p_num} -->\n{md.strip()}")

        except Exception:
            # Fallback to full document process_pdf_bytes
            res = pdf_inspector.process_pdf_bytes(pdf_bytes)
            md_text = getattr(res, "markdown", "") or ""
            pages_list.append(PDFPageMarkdown(page_number=1, markdown=md_text))
            full_md_parts.append(md_text)

        full_markdown = "\n\n".join(full_md_parts)
        table_blocks = extract_tables_from_markdown(full_markdown)

        # Update inspection report character and table counts
        inspection.table_count = len(table_blocks)
        inspection.heading_count = count_markdown_headings(full_markdown)
        inspection.total_characters = len(full_markdown)

        return PDFExtractionResult(
            title=title,
            full_markdown=full_markdown,
            pages=pages_list,
            inspection_report=inspection,
            table_blocks=table_blocks
        )

    def generate_sample_pdf(self, preset_type: str = "ai_governance") -> bytes:
        """
        Generates realistic multi-page enterprise PDFs with titles, headings,
        tabular SLA matrices, and multi-column policies for testing and demonstrations.
        """
        if not HAS_REPORTLAB:
            # Return minimal fallback PDF bytes
            return (
                b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n'
                b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n'
                b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n'
                b'4 0 obj\n<< /Length 20 >>\nstream\nBT /F1 12 Tf (PDF) Tj ET\nendstream\nendobj\n'
                b'xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000214 00000 n \n'
                b'trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n285\n%%EOF'
            )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Title'],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#1e1b4b"),
            spaceAfter=12
        )
        h1_style = ParagraphStyle(
            'DocH1',
            parent=styles['Heading1'],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#312e81"),
            spaceBefore=14,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            'DocBody',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#1f2937"),
            spaceAfter=8
        )

        elements = []

        if preset_type == "ai_governance":
            elements.append(Paragraph("Enterprise AI Governance & Model Risk Standard 2026", title_style))
            elements.append(Paragraph("Document ID: GOV-AI-2026-V4 | Classification: Tier-1 Enterprise Standard | Author: CISO & AI Ethics Board", body_style))
            elements.append(Spacer(1, 10))

            elements.append(Paragraph("1. Model Risk Classification & Pre-Deployment Gates", h1_style))
            elements.append(Paragraph("Under Corporate Directive SEC-909, all generative AI models and autonomous agent workflows must complete adversarial red-teaming and bias audits before production sign-off. Form GOV-AI-88 must be signed by the VP of Engineering prior to production deployment.", body_style))
            elements.append(Spacer(1, 8))

            elements.append(Paragraph("2. Operational SLA & Escalation Thresholds", h1_style))
            table_data = [
                ["Incident Level", "Response SLA", "Resolution Target", "Mandatory Escalation Path", "Notification Rule"],
                ["P0 - Model Breach", "5 Minutes", "2 Hours", "Executive AI Security War Room", "Immediate SMS + PagerDuty"],
                ["P1 - High Drift", "15 Minutes", "6 Hours", "Lead MLOps Incident Commander", "Email & Slack #ai-ops"],
                ["P2 - Prompt Drift", "1 Hour", "24 Hours", "Domain Model Stewards", "Standard JIRA Ticket"],
                ["P3 - Low Impact", "4 Hours", "72 Hours", "Weekly Sprint Backlog Review", "Async Digest"]
            ]
            t = Table(table_data, colWidths=[105, 80, 85, 150, 110])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4338ca")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.HexColor("#e2e8f0")]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 10))

            elements.append(Paragraph("3. Data Residency and Privacy Guarantees", h1_style))
            elements.append(Paragraph("All inference requests containing Protected Health Information (PHI) or Personally Identifiable Information (PII) must be processed within isolated VPC enclaves conforming to ISO-27001 standard section 9.4. Customer data retention is strictly limited to 0 days under zero-data-retention agreements.", body_style))

        elif preset_type == "sre_dr_matrix":
            elements.append(Paragraph("Multi-Region Disaster Recovery & Uptime SLA Matrix", title_style))
            elements.append(Paragraph("Document ID: SRE-DR-2026-R8 | Scope: Global Kubernetes & Database Clusters", body_style))
            elements.append(Spacer(1, 10))

            elements.append(Paragraph("1. Recovery Objectives by Service Tier", h1_style))
            elements.append(Paragraph("This document establishes the Recovery Time Objective (RTO) and Recovery Point Objective (RPO) baselines across all production clusters.", body_style))
            elements.append(Spacer(1, 8))

            dr_table = [
                ["Service Tier", "RTO Target", "RPO Target", "Backup Frequency", "Failover Mechanism"],
                ["Tier-1 Relational DB", "15 Minutes", "60 Seconds", "Continuous WAL Replicate", "Automated Multi-AZ Flip"],
                ["Tier-1 Vector Index", "30 Minutes", "5 Minutes", "Hourly Snapshot to GCS", "DNS Route53 Shifting"],
                ["Tier-2 Analytics DB", "2 Hours", "1 Hour", "Daily Cold Storage", "Manual Terraform Apply"],
                ["Tier-3 Dev/Staging", "24 Hours", "24 Hours", "Weekly Archives", "Cold Image Rebuild"]
            ]
            t = Table(dr_table, colWidths=[110, 85, 85, 125, 125])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#f0fdf4"), colors.HexColor("#dcfce7")]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#86efac")),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(t)

        elif preset_type == "hr_benefits_matrix":
            elements.append(Paragraph("Executive Compensation & PTO Accrual Schedule 2026", title_style))
            elements.append(Paragraph("Document ID: HR-POL-BEN-2026 | Department: Global People Operations", body_style))
            elements.append(Spacer(1, 10))

            elements.append(Paragraph("1. Paid Leave Accrual Tiers", h1_style))
            elements.append(Paragraph("Employees accrue Paid Time Off on the 1st of each calendar month. Unused PTO up to 5 days rolls over automatically.", body_style))
            elements.append(Spacer(1, 8))

            pto_table = [
                ["Tenure Bracket", "Annual PTO Days", "Monthly Accrual", "Max Rollover Days", "Form Required for Roll"],
                ["0 - 2 Years", "20 Days", "1.66 Days", "5 Days", "Form HR-PTO-ROLL"],
                ["3 - 5 Years", "25 Days", "2.08 Days", "7 Days", "Form HR-PTO-ROLL"],
                ["5+ Years", "30 Days", "2.50 Days", "10 Days", "Form HR-PTO-ROLL"],
                ["Executive Tier", "Unlimited", "N/A", "N/A", "Board Approval"]
            ]
            t = Table(pto_table, colWidths=[100, 95, 95, 110, 130])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#7c2d12")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#fff7ed"), colors.HexColor("#ffedd5")]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#fed7aa")),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(t)

        doc.build(elements)
        return buffer.getvalue()


# Default singleton instance
pdf_engine = PDFInspectorEngine()
