import io
import csv
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Tuple, Optional
from pydantic import BaseModel, Field


class ParsedDocument(BaseModel):
    title: str
    markdown_content: str
    doc_format: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    table_count: int = 0
    page_or_sheet_count: int = 1


class DocumentFormatParsers:
    """
    Extensible Document Format Parser Suite.
    Zero external heavy binary dependencies: Uses pure-Python XML/ZIP inspection
    for high-speed layout-aware parsing of Microsoft Word (.docx), Excel (.xlsx),
    and Structured Tabular CSV (.csv) documents.
    """

    @classmethod
    def parse_docx(cls, docx_bytes: bytes, filename: str = "document.docx") -> ParsedDocument:
        """
        Parses Microsoft Word (.docx) package by inspecting word/document.xml.
        Extracts headings (#, ##), standard body paragraphs, and structured tables.
        """
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
            if "word/document.xml" not in z.namelist():
                raise ValueError("Invalid DOCX format: missing word/document.xml")
            
            xml_content = z.read("word/document.xml")

        root = ET.fromstring(xml_content)
        # XML namespace for WordprocessingML
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

        markdown_lines = []
        table_count = 0
        doc_title = filename.replace(".docx", "").replace("_", " ").title()

        # Iterate over top-level body children (paragraphs and tables)
        body = root.find("w:body", ns)
        if body is None:
            return ParsedDocument(title=doc_title, markdown_content="", doc_format="docx")

        for child in body:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            if tag == "p":
                # Paragraph or Heading
                # Check for heading style in w:pPr/w:pStyle
                style_elem = child.find("w:pPr/w:pStyle", ns)
                style_val = style_elem.attrib.get(f"{{{ns['w']}}}val", "") if style_elem is not None else ""
                
                # Extract text runs
                texts = []
                for r in child.findall("w:r", ns):
                    t = r.find("w:t", ns)
                    if t is not None and t.text:
                        texts.append(t.text)
                
                p_text = "".join(texts).strip()
                if not p_text:
                    continue

                if "Heading1" in style_val or "heading 1" in style_val.lower() or style_val == "1":
                    markdown_lines.append(f"\n# {p_text}\n")
                elif "Heading2" in style_val or "heading 2" in style_val.lower() or style_val == "2":
                    markdown_lines.append(f"\n## {p_text}\n")
                elif "Heading3" in style_val or "heading 3" in style_val.lower() or style_val == "3":
                    markdown_lines.append(f"\n### {p_text}\n")
                else:
                    markdown_lines.append(p_text)

            elif tag == "tbl":
                # Table block
                table_count += 1
                rows_data = []
                for tr in child.findall("w:tr", ns):
                    row_cells = []
                    for tc in tr.findall("w:tc", ns):
                        cell_texts = []
                        for t in tc.findall(".//w:t", ns):
                            if t.text:
                                cell_texts.append(t.text)
                        row_cells.append(" ".join(cell_texts).strip())
                    if any(c for c in row_cells):
                        rows_data.append(row_cells)

                if rows_data:
                    # Normalize columns
                    max_cols = max(len(r) for r in rows_data)
                    norm_rows = [r + [""] * (max_cols - len(r)) for r in rows_data]

                    # Construct Markdown table
                    header_row = norm_rows[0]
                    markdown_lines.append("\n| " + " | ".join(header_row) + " |")
                    markdown_lines.append("| " + " | ".join(["---"] * max_cols) + " |")
                    for data_row in norm_rows[1:]:
                        markdown_lines.append("| " + " | ".join(data_row) + " |")
                    markdown_lines.append("\n")

        full_md = "\n".join(markdown_lines).strip()
        return ParsedDocument(
            title=doc_title,
            markdown_content=full_md,
            doc_format="docx",
            metadata={"filename": filename, "table_count": table_count},
            table_count=table_count
        )

    @classmethod
    def parse_xlsx(cls, xlsx_bytes: bytes, filename: str = "spreadsheet.xlsx") -> ParsedDocument:
        """
        Parses Microsoft Excel (.xlsx) workbook using pure-Python XML extraction.
        Converts spreadsheet sheets and rows into structured Markdown data tables.
        """
        with zipfile.ZipFile(io.BytesIO(xlsx_bytes)) as z:
            shared_strings = []
            if "xl/sharedStrings.xml" in z.namelist():
                ss_root = ET.fromstring(z.read("xl/sharedStrings.xml"))
                ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for si in ss_root.findall(".//s:si", ns) or ss_root.findall(".//si"):
                    t_nodes = si.findall(".//s:t", ns) or si.findall(".//t")
                    shared_strings.append("".join(t.text for t in t_nodes if t.text))

            sheet_names = [n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
            if not sheet_names:
                raise ValueError("Invalid XLSX file: no worksheets found")

            doc_title = filename.replace(".xlsx", "").replace("_", " ").title()
            markdown_sections = [f"# {doc_title}\n"]
            table_count = 0

            for sheet_idx, sname in enumerate(sorted(sheet_names)):
                s_root = ET.fromstring(z.read(sname))
                ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                
                rows_data = []
                rows = s_root.findall(".//s:row", ns) or s_root.findall(".//row")
                for r in rows:
                    cells = r.findall("s:c", ns) or r.findall("c")
                    row_vals = []
                    for c in cells:
                        cell_type = c.attrib.get("t", "")
                        v = c.find("s:v", ns) if c.find("s:v", ns) is not None else c.find("v")
                        val_str = v.text if v is not None and v.text else ""
                        if cell_type == "s" and val_str.isdigit():
                            idx = int(val_str)
                            val_str = shared_strings[idx] if idx < len(shared_strings) else val_str
                        row_vals.append(val_str.strip())
                    if any(c for c in row_vals):
                        rows_data.append(row_vals)

                if rows_data:
                    table_count += 1
                    sheet_label = f"Sheet {sheet_idx + 1}"
                    markdown_sections.append(f"\n## {sheet_label}\n")
                    max_cols = max(len(r) for r in rows_data)
                    norm_rows = [r + [""] * (max_cols - len(r)) for r in rows_data]

                    header = norm_rows[0]
                    markdown_sections.append("| " + " | ".join(header) + " |")
                    markdown_sections.append("| " + " | ".join(["---"] * max_cols) + " |")
                    for row in norm_rows[1:]:
                        markdown_sections.append("| " + " | ".join(row) + " |")
                    markdown_sections.append("\n")

        full_md = "\n".join(markdown_sections).strip()
        return ParsedDocument(
            title=doc_title,
            markdown_content=full_md,
            doc_format="xlsx",
            metadata={"filename": filename, "sheet_count": len(sheet_names), "table_count": table_count},
            table_count=table_count,
            page_or_sheet_count=len(sheet_names)
        )

    @classmethod
    def parse_csv(cls, csv_bytes: bytes, filename: str = "dataset.csv") -> ParsedDocument:
        """
        Parses Delimited CSV files into high-fidelity markdown tables.
        """
        text = csv_bytes.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = [r for r in reader if r and any(c.strip() for c in r)]

        doc_title = filename.replace(".csv", "").replace("_", " ").title()
        if not rows:
            return ParsedDocument(title=doc_title, markdown_content="", doc_format="csv")

        max_cols = max(len(r) for r in rows)
        norm_rows = [r + [""] * (max_cols - len(r)) for r in rows]

        md_lines = [f"# {doc_title}\n"]
        header = norm_rows[0]
        md_lines.append("| " + " | ".join(header) + " |")
        md_lines.append("| " + " | ".join(["---"] * max_cols) + " |")
        for r in norm_rows[1:]:
            md_lines.append("| " + " | ".join(r) + " |")

        return ParsedDocument(
            title=doc_title,
            markdown_content="\n".join(md_lines).strip(),
            doc_format="csv",
            metadata={"filename": filename, "row_count": len(rows), "table_count": 1},
            table_count=1
        )
