import datetime
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class CompiledDocumentResult(BaseModel):
    """Result of document compilation."""
    title: str
    doc_format: str  # "markdown", "latex", "html", "plain"
    citation_style: str  # "APA", "IEEE", "MLA", "Chicago"
    content: str
    citation_count: int
    word_count: int
    generated_at: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


class ScholarDocCompiler:
    """
    ScholarDoc Multi-Format Document Compiler (WisDev ARC Evolution).
    
    Transforms RAG syntheses and compliance audits into formal publication-grade
    manuscripts in Markdown, LaTeX, and HTML with IEEE/APA/MLA bibliographic citations.
    """

    def __init__(self):
        pass

    def format_citation(self, citation: Dict[str, Any], style: str = "APA", index: int = 1) -> str:
        """Formats a single chunk citation into formal bibliographic style."""
        doc_title = citation.get("doc_title", "Enterprise Standard Document")
        section = citation.get("section_header", "General Section")
        page = citation.get("page_number", 1)
        year = datetime.datetime.utcnow().year
        author = citation.get("author", "NexusRAG Enterprise Authority")

        if style.upper() == "APA":
            return f"{author}. ({year}). *{doc_title}* [Section: {section}, p. {page}]. Global Policy Vault."
        elif style.upper() == "IEEE":
            return f"[{index}] {author}, \"{doc_title},\" *Enterprise Standards*, sec. {section}, p. {page}, {year}."
        elif style.upper() == "MLA":
            return f"{author}. \"{doc_title}.\" *Enterprise Regulatory Vault*, sec. {section}, {year}, p. {page}."
        elif style.upper() == "CHICAGO":
            return f"{author}. {year}. \"{doc_title}.\" *Enterprise Policy Guidelines*, sec. {section}, {page}."
        else:
            return f"[{index}] {doc_title} - {section} (p. {page})"

    def compile_document(
        self,
        title: str,
        query: str,
        answer: str,
        citations: List[Dict[str, Any]],
        doc_format: str = "markdown",
        citation_style: str = "APA",
        author: str = "Enterprise Architecture & Governance AI",
        abstract: Optional[str] = None
    ) -> CompiledDocumentResult:
        """
        Compiles research findings into the requested output format.
        """
        fmt = doc_format.lower()
        style = citation_style.upper()
        now_str = datetime.datetime.utcnow().strftime("%B %d, %Y")
        abstract_text = abstract or f"This executive brief synthesizes verified regulatory, architectural, and operational findings addressing: '{query}'."

        formatted_citations = [self.format_citation(c, style=style, index=i+1) for i, c in enumerate(citations)]

        if fmt == "latex":
            content = self._compile_latex(
                title=title,
                author=author,
                date_str=now_str,
                abstract=abstract_text,
                query=query,
                answer=answer,
                citations=formatted_citations
            )
        elif fmt == "html":
            content = self._compile_html(
                title=title,
                author=author,
                date_str=now_str,
                abstract=abstract_text,
                query=query,
                answer=answer,
                citations=formatted_citations,
                style_name=style
            )
        else:
            # Default: Markdown
            content = self._compile_markdown(
                title=title,
                author=author,
                date_str=now_str,
                abstract=abstract_text,
                query=query,
                answer=answer,
                citations=formatted_citations,
                style_name=style
            )

        words = len(content.split())

        return CompiledDocumentResult(
            title=title,
            doc_format=fmt,
            citation_style=style,
            content=content,
            citation_count=len(citations),
            word_count=words
        )

    def _compile_markdown(
        self, title: str, author: str, date_str: str,
        abstract: str, query: str, answer: str,
        citations: List[str], style_name: str
    ) -> str:
        bib_lines = "\n".join([f"{i+1}. {c}" for i, c in enumerate(citations)]) if citations else "*No external citations registered.*"
        
        return f"""# {title}

**Author**: {author}  
**Date**: {date_str}  
**Classification**: Tier-1 Enterprise Compliance Brief  

---

## Executive Summary
> {abstract}

## 1. Context & Research Inquiry
**Inquiry**: *"{query}"*

## 2. Synthesized Findings & Governance Analysis
{answer}

---

## 3. Bibliographic References ({style_name} Style)
{bib_lines}
"""

    def _compile_latex(
        self, title: str, author: str, date_str: str,
        abstract: str, query: str, answer: str,
        citations: List[str]
    ) -> str:
        # Escape LaTeX special characters
        def tex_escape(t: str) -> str:
            t = t.replace("&", "\\&").replace("%", "\\%").replace("$", "\\$").replace("_", "\\_").replace("#", "\\#")
            return t

        safe_title = tex_escape(title)
        safe_author = tex_escape(author)
        safe_abstract = tex_escape(abstract)
        safe_query = tex_escape(query)
        
        # Convert markdown bold to latex bold
        clean_answer = re.sub(r'\*\*(.*?)\*\*', r'\\textbf{\1}', answer)
        safe_answer = tex_escape(clean_answer)

        bib_items = "\n".join([f"\\bibitem{{ref{i+1}}} {tex_escape(c)}" for i, c in enumerate(citations)])

        return f"""\\documentclass[11pt,a4paper]{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[margin=1in]{{geometry}}
\\usepackage{{hyperref}}
\\usepackage{{booktabs}}
\\usepackage{{amsmath}}

\\title{{{safe_title}}}
\\author{{{safe_author}}}
\\date{{{date_str}}}

\\begin{{document}}

\\maketitle

\\begin{{abstract}}
{safe_abstract}
\\end{{abstract}}

\\section{{Problem Statement}}
\\textbf{{Research Inquiry:}} \\textit{{{safe_query}}}

\\section{{Synthesized Findings}}
{safe_answer}

\\begin{{thebibliography}}{{99}}
{bib_items}
\\end{{thebibliography}}

\\end{{document}}
"""

    def _compile_html(
        self, title: str, author: str, date_str: str,
        abstract: str, query: str, answer: str,
        citations: List[str], style_name: str
    ) -> str:
        bib_items = "".join([f"<li>{c}</li>" for c in citations]) if citations else "<li>No external citations registered.</li>"
        
        # Convert line breaks and bolding to HTML
        html_answer = answer.replace("\n\n", "</p><p>").replace("\n", "<br>")
        html_answer = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_answer)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #1e293b;
            background-color: #f8fafc;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            background: #ffffff;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
            border: 1px solid #e2e8f0;
        }}
        h1 {{ color: #0f172a; border-bottom: 2px solid #3b82f6; padding-bottom: 12px; }}
        .meta {{ color: #64748b; font-size: 0.9em; margin-bottom: 24px; }}
        .abstract {{
            background: #eff6ff;
            border-left: 4px solid #3b82f6;
            padding: 16px;
            border-radius: 0 8px 8px 0;
            margin-bottom: 30px;
            font-style: italic;
        }}
        .findings {{ margin-bottom: 30px; }}
        .references {{ background: #f1f5f9; padding: 20px; border-radius: 8px; font-size: 0.9em; }}
        .references ol {{ padding-left: 20px; margin: 0; }}
        .references li {{ margin-bottom: 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <div class="meta">
            <strong>Author:</strong> {author} &bull; <strong>Date:</strong> {date_str}
        </div>
        <div class="abstract">
            <strong>Executive Summary:</strong> {abstract}
        </div>
        <h3>1. Inquiry</h3>
        <p><em>"{query}"</em></p>
        <h3>2. Synthesized Governance Findings</h3>
        <div class="findings">
            <p>{html_answer}</p>
        </div>
        <div class="references">
            <h3>3. References ({style_name} Style)</h3>
            <ol>
                {bib_items}
            </ol>
        </div>
    </div>
</body>
</html>
"""
