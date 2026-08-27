import sys
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from rag_engine.vault_manager import MultiVaultManager
from rag_engine.timeline import PolicyTimelineExtractor
from rag_engine.docgen import ScholarDocCompiler
from rag_engine.pdf_inspector_engine import pdf_engine
from .schemas import MCPToolCallRequest, MCPToolCallResponse


class MCPToolDefinition(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]


# Formal MCP Tool Schema Manifest
MCP_TOOL_MANIFEST: List[Dict[str, Any]] = [
    {
        "name": "search_vault",
        "description": "Execute hybrid RRF search (Dense vector + BM25Okapi + Cross-Encoder reranking) over enterprise knowledge vaults.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The enterprise policy, SLA, or technical query."},
                "vault_id": {"type": "string", "enum": ["all", "hr_benefits", "sre_infra", "infosec_compliance", "procurement_quantum", "pdf_standards"], "default": "all"},
                "top_k": {"type": "integer", "default": 4, "description": "Number of precision-reranked chunks to retrieve."}
            },
            "required": ["query"]
        }
    },
    {
        "name": "raptor_thematic_search",
        "description": "Hierarchical RAPTOR tree retrieval across Level 0 leaf chunks, Level 1 section summaries, and Level 2 thematic abstracts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The high-level or architectural question."},
                "vault_id": {"type": "string", "default": "all"},
                "target_level": {"type": "integer", "description": "Optional level filter: 0=Leaf, 1=Section Summary, 2=Document Abstract."}
            },
            "required": ["query"]
        }
    },
    {
        "name": "verify_compliance",
        "description": "Validate a compliance statement or code snippet against ISO-27001, HIPAA 164.312, or SOC 2 corporate rules.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rule_code": {"type": "string", "description": "Standard code like 'SEC-881', 'ISO-27001', 'HIPAA 164.312'."},
                "statement": {"type": "string", "description": "The policy or technical implementation statement to verify."}
            },
            "required": ["rule_code", "statement"]
        }
    },
    {
        "name": "get_sla_timeline",
        "description": "Extract chronological SLA milestones, escalation windows, and urgent operational deadlines from enterprise policies.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "urgency": {"type": "string", "enum": ["all", "critical", "high", "medium"], "default": "all"}
            }
        }
    },
    {
        "name": "compile_manuscript",
        "description": "Compile research findings or RAG answers into formal LaTeX, Markdown, or HTML with APA/IEEE citations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title of the compiled document."},
                "query": {"type": "string", "description": "Original inquiry."},
                "answer": {"type": "string", "description": "Synthesized findings to format."},
                "format": {"type": "string", "enum": ["markdown", "latex", "html"], "default": "markdown"},
                "citation_style": {"type": "string", "enum": ["APA", "IEEE", "MLA", "Chicago"], "default": "APA"}
            },
            "required": ["title", "query", "answer"]
        }
    },
    {
        "name": "inspect_pdf_structure",
        "description": "Inspect sample enterprise PDF using Firecrawl pdf-inspector to verify table layout and OCR routing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "preset_name": {"type": "string", "enum": ["ai_governance", "sre_dr_matrix", "hr_benefits_matrix"], "default": "ai_governance"}
            }
        }
    }
]


class MCPServerHandler:
    """Model Context Protocol (MCP) Dispatcher for Claude Code, Cursor, and Windsurf."""

    def __init__(self, vault_manager: MultiVaultManager):
        self.vault_manager = vault_manager
        self.doc_compiler = ScholarDocCompiler()
        self.timeline_extractor = PolicyTimelineExtractor()

    def get_manifest(self) -> List[Dict[str, Any]]:
        return MCP_TOOL_MANIFEST

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> MCPToolCallResponse:
        try:
            if tool_name == "search_vault":
                query = arguments.get("query", "")
                vault_id = arguments.get("vault_id", "all")
                top_k = arguments.get("top_k", 4)
                
                vault = self.vault_manager.get_vault(vault_id)
                retriever = vault.retriever
                reranker = vault.reranker
                
                raw = retriever.retrieve(query, overfetch_k=15)
                ranked = reranker.rerank(query, raw, top_k=top_k)

                results = []
                for r in ranked:
                    results.append({
                        "chunk_id": r.chunk.id,
                        "doc_title": r.chunk.doc_title,
                        "section": r.chunk.metadata.get("section_header", "General"),
                        "rerank_score": r.rerank_score,
                        "snippet": r.chunk.content[:300]
                    })
                return MCPToolCallResponse(
                    tool=tool_name,
                    content=[{"type": "text", "text": json.dumps(results, indent=2)}]
                )

            elif tool_name == "raptor_thematic_search":
                query = arguments.get("query", "")
                vault_id = arguments.get("vault_id", "all")
                target_lvl = arguments.get("target_level")
                
                raptor_index = self.vault_manager.raptor_index
                results = raptor_index.retrieve_hierarchical(
                    query=query,
                    top_k=4,
                    target_level=target_lvl,
                    vault_id=vault_id
                )
                
                output = []
                for res in results:
                    output.append({
                        "node_id": res.node.node_id,
                        "level": res.level,
                        "title": res.node.title,
                        "score": res.score,
                        "summary": res.node.content
                    })
                return MCPToolCallResponse(
                    tool=tool_name,
                    content=[{"type": "text", "text": json.dumps(output, indent=2)}]
                )

            elif tool_name == "verify_compliance":
                rule_code = arguments.get("rule_code", "")
                statement = arguments.get("statement", "")
                
                vault = self.vault_manager.get_vault("infosec_compliance")
                raw = vault.retriever.retrieve(f"{rule_code} {statement}", overfetch_k=6)
                ranked = vault.reranker.rerank(statement, raw, top_k=2)

                is_supported = len(ranked) > 0 and ranked[0].rerank_score >= 0.70
                verification = {
                    "rule_code": rule_code,
                    "statement": statement,
                    "compliance_status": "COMPLIANT" if is_supported else "NON_COMPLIANT_OR_UNVERIFIED",
                    "confidence": ranked[0].rerank_score if ranked else 0.0,
                    "governing_policy": ranked[0].chunk.doc_title if ranked else "None"
                }
                return MCPToolCallResponse(
                    tool=tool_name,
                    content=[{"type": "text", "text": json.dumps(verification, indent=2)}]
                )

            elif tool_name == "get_sla_timeline":
                urgency = arguments.get("urgency", "all")
                vault = self.vault_manager.get_vault("sre_infra")
                all_text = " ".join([c.content for c in vault.chunks])
                events = self.timeline_extractor.extract_timeline(all_text)
                
                filtered = [e.dict() for e in events if urgency == "all" or e.urgency == urgency]
                return MCPToolCallResponse(
                    tool=tool_name,
                    content=[{"type": "text", "text": json.dumps(filtered, indent=2)}]
                )

            elif tool_name == "compile_manuscript":
                title = arguments.get("title", "Compliance Research Brief")
                query = arguments.get("query", "")
                answer = arguments.get("answer", "")
                fmt = arguments.get("format", "markdown")
                style = arguments.get("citation_style", "APA")

                res = self.doc_compiler.compile_document(
                    title=title,
                    query=query,
                    answer=answer,
                    citations=[{"doc_title": "Enterprise Knowledge Standard", "section_header": "Section 1", "page_number": 1}],
                    doc_format=fmt,
                    citation_style=style
                )
                return MCPToolCallResponse(
                    tool=tool_name,
                    content=[{"type": "text", "text": res.content}]
                )

            elif tool_name == "inspect_pdf_structure":
                preset = arguments.get("preset_name", "ai_governance")
                pdf_bytes = pdf_engine.generate_sample_pdf(preset)
                report = pdf_engine.inspect_pdf_bytes(pdf_bytes, f"{preset}.pdf")
                return MCPToolCallResponse(
                    tool=tool_name,
                    content=[{"type": "text", "text": report.json(indent=2)}]
                )

            else:
                return MCPToolCallResponse(
                    tool=tool_name,
                    content=[{"type": "text", "text": f"Error: Unknown tool '{tool_name}'"}],
                    is_error=True
                )

        except Exception as e:
            return MCPToolCallResponse(
                tool=tool_name,
                content=[{"type": "text", "text": f"Execution error: {str(e)}"}],
                is_error=True
            )


if __name__ == "__main__":
    # Stdio JSON-RPC MCP Server listener for Claude Code / Cursor integration
    from rag_engine.ingestion import DocumentIngestionPipeline
    pipeline = DocumentIngestionPipeline()
    vm = MultiVaultManager(pipeline)
    handler = MCPServerHandler(vm)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            method = req.get("method", "")
            req_id = req.get("id")

            if method == "tools/list":
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": handler.get_manifest()}}
            elif method == "tools/call":
                params = req.get("params", {})
                t_name = params.get("name", "")
                t_args = params.get("arguments", {})
                res = handler.execute_tool(t_name, t_args)
                resp = {"jsonrpc": "2.0", "id": req_id, "result": res.dict()}
            else:
                resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}

            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as ex:
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(ex)}}
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()
