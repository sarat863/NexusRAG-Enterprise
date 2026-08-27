import io
import zipfile
import pytest
from rag_engine.format_parsers import DocumentFormatParsers, ParsedDocument
from rag_engine.ingestion import DocumentIngestionPipeline


def create_sample_docx_bytes() -> bytes:
    """Creates a valid in-memory Microsoft Word .docx file with headings, text, and tables."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # Minimal [Content_Types].xml
        z.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")

        # word/document.xml with heading, paragraph, and table
        z.writestr("word/document.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
      <w:r><w:t>Enterprise AI Architecture Guideline</w:t></w:r>
    </w:p>
    <w:p>
      <w:r><w:t>All neural deployments must conform to ISO-42001 governance controls.</w:t></w:r>
    </w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Tier Level</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Target Uptime</w:t></w:r></w:p></w:tc>
      </w:tr>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Tier 1</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>99.99%</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>""")

    buf.seek(0)
    return buf.read()


def create_sample_xlsx_bytes() -> bytes:
    """Creates a valid in-memory Microsoft Excel .xlsx file with shared strings and sheet table."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>""")

        z.writestr("xl/sharedStrings.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="4" uniqueCount="4">
  <si><t>Policy ID</t></si>
  <si><t>Accrual Rate</t></si>
  <si><t>HR-PTO-2026</t></si>
  <si><t>1.66 days/mo</t></si>
</sst>""")

        z.writestr("xl/worksheets/sheet1.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="s"><v>0</v></c>
      <c r="B1" t="s"><v>1</v></c>
    </row>
    <row r="2">
      <c r="A2" t="s"><v>2</v></c>
      <c r="B2" t="s"><v>3</v></c>
    </row>
  </sheetData>
</worksheet>""")

    buf.seek(0)
    return buf.read()


def test_docx_parser_and_ingestion():
    """Verify .docx parser extracts headings, paragraphs, and markdown tables."""
    docx_bytes = create_sample_docx_bytes()
    parsed: ParsedDocument = DocumentFormatParsers.parse_docx(docx_bytes, filename="Enterprise_AI.docx")

    assert "# Enterprise AI Architecture Guideline" in parsed.markdown_content
    assert "ISO-42001" in parsed.markdown_content
    assert "| Tier Level | Target Uptime |" in parsed.markdown_content
    assert "| Tier 1 | 99.99% |" in parsed.markdown_content
    assert parsed.table_count == 1

    # Ingest through pipeline
    pipe = DocumentIngestionPipeline(chunk_size=100, chunk_overlap=20)
    doc, chunks = pipe.process_docx(docx_bytes, filename="Enterprise_AI.docx")
    assert len(chunks) >= 2
    assert any(c.metadata.get("has_table", False) for c in chunks)


def test_xlsx_parser_and_ingestion():
    """Verify .xlsx parser converts spreadsheet sheets into structured markdown tables."""
    xlsx_bytes = create_sample_xlsx_bytes()
    parsed: ParsedDocument = DocumentFormatParsers.parse_xlsx(xlsx_bytes, filename="PTO_Matrix.xlsx")

    assert "| Policy ID | Accrual Rate |" in parsed.markdown_content
    assert "| HR-PTO-2026 | 1.66 days/mo |" in parsed.markdown_content
    assert parsed.table_count >= 1

    pipe = DocumentIngestionPipeline(chunk_size=100, chunk_overlap=20)
    doc, chunks = pipe.process_xlsx(xlsx_bytes, filename="PTO_Matrix.xlsx")
    assert len(chunks) >= 1
    assert any("HR-PTO-2026" in c.content for c in chunks)


def test_csv_parser_and_ingestion():
    """Verify CSV parser converts CSV tables into clean markdown chunks."""
    csv_content = b"Service Name,RTO Objective,RPO Objective\nPayment Gateway,5 minutes,30 seconds\nUser Auth,10 minutes,60 seconds"
    parsed: ParsedDocument = DocumentFormatParsers.parse_csv(csv_content, filename="SRE_Targets.csv")

    assert "| Service Name | RTO Objective | RPO Objective |" in parsed.markdown_content
    assert "| Payment Gateway | 5 minutes | 30 seconds |" in parsed.markdown_content

    pipe = DocumentIngestionPipeline(chunk_size=100, chunk_overlap=20)
    doc, chunks = pipe.process_csv(csv_content, filename="SRE_Targets.csv")
    assert len(chunks) >= 1
    assert any("Payment Gateway" in c.content for c in chunks)


def test_universal_process_any_file_routing():
    """Verify process_any_file automatically detects and routes formats appropriately."""
    pipe = DocumentIngestionPipeline(chunk_size=100, chunk_overlap=20)
    
    # 1. DOCX
    d_doc, d_chunks, d_info = pipe.process_any_file(create_sample_docx_bytes(), "test.docx")
    assert d_info["format"] == "docx"
    assert len(d_chunks) > 0

    # 2. XLSX
    x_doc, x_chunks, x_info = pipe.process_any_file(create_sample_xlsx_bytes(), "test.xlsx")
    assert x_info["format"] == "xlsx"
    assert len(x_chunks) > 0

    # 3. CSV
    c_doc, c_chunks, c_info = pipe.process_any_file(b"ColA,ColB\nVal1,Val2", "test.csv")
    assert c_info["format"] == "csv"
    assert len(c_chunks) > 0
