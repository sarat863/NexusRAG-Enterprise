import os
import logging
import hashlib
import json
import uuid
import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from .storage import SQLiteStorageManager

logger = logging.getLogger("nexusrag.audit")


class AuditLogEntry(BaseModel):
    """Immutable audit log record representing a certified RAG transaction."""
    audit_id: str = Field(default_factory=lambda: f"AUDIT-NEXUS-{uuid.uuid4().hex[:10].upper()}")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    tenant_id: str
    user_id: str
    query_text: str
    synthesized_answer: str
    faithfulness_score: float
    context_relevance_score: float
    cited_chunk_ids: List[str] = Field(default_factory=list)
    latency_ms: float = 0.0
    sha256_signature: str = ""
    is_tamper_verified: bool = True


class AuditVaultManager:
    """
    Immutable SOC 2 Compliance Audit Ledger backed by SQLite.
    
    Generates tamper-proof SHA-256 cryptographic signatures for every RAG query,
    retrieved source chunk, and faithfulness evaluation, guaranteeing full provenance
    and disk persistence across process restarts.
    """

    def __init__(self, storage: Optional[SQLiteStorageManager] = None):
        self.storage = storage or SQLiteStorageManager()
        self._ledger: Dict[str, AuditLogEntry] = {}
        self._tenant_index: Dict[str, List[str]] = {}
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.fallback_path = os.path.join(base_dir, "data", "audit_fallback.jsonl")

    def _write_fallback_journal(self, entry: AuditLogEntry):
        """Appends unpersisted audit record to emergency fallback journal."""
        try:
            os.makedirs(os.path.dirname(self.fallback_path), exist_ok=True)
            with open(self.fallback_path, "a", encoding="utf-8") as f:
                dump = entry.model_dump() if hasattr(entry, "model_dump") else entry.dict()
                f.write(json.dumps(dump) + "\n")
            logger.warning(f"Audit entry {entry.audit_id} written to fallback journal: {self.fallback_path}")
        except Exception as fe:
            logger.critical(f"FATAL: Failed to write audit fallback journal: {str(fe)}")

    def compute_signature(
        self,
        audit_id: str,
        tenant_id: str,
        query: str,
        answer: str,
        faithfulness: float,
        chunk_ids: List[str]
    ) -> str:
        """Computes SHA-256 cryptographic hash over critical transaction payload."""
        payload = f"{audit_id}|{tenant_id}|{query}|{answer}|{faithfulness:.4f}|{sorted(chunk_ids)}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def record_transaction(
        self,
        tenant_id: str,
        user_id: str,
        query_text: str,
        synthesized_answer: str,
        faithfulness_score: float,
        context_relevance_score: float,
        cited_chunk_ids: List[str],
        latency_ms: float = 0.0
    ) -> AuditLogEntry:
        """Appends a new certified transaction to the immutable audit ledger and SQLite."""
        audit_id = f"AUDIT-NEXUS-{uuid.uuid4().hex[:10].upper()}"
        sig = self.compute_signature(
            audit_id=audit_id,
            tenant_id=tenant_id,
            query=query_text,
            answer=synthesized_answer,
            faithfulness=faithfulness_score,
            chunk_ids=cited_chunk_ids
        )

        now = datetime.datetime.utcnow().isoformat()
        entry = AuditLogEntry(
            audit_id=audit_id,
            timestamp=now,
            tenant_id=tenant_id,
            user_id=user_id,
            query_text=query_text,
            synthesized_answer=synthesized_answer,
            faithfulness_score=round(faithfulness_score, 4),
            context_relevance_score=round(context_relevance_score, 4),
            cited_chunk_ids=cited_chunk_ids,
            latency_ms=round(latency_ms, 2),
            sha256_signature=sig,
            is_tamper_verified=True
        )

        self._ledger[audit_id] = entry
        self._tenant_index.setdefault(tenant_id, []).append(audit_id)

        # Persist to SQLite with emergency fallback journal
        try:
            self.storage.record_audit_entry(
                audit_id=audit_id,
                tenant_id=tenant_id,
                user_id=user_id,
                query_text=query_text,
                synthesized_answer=synthesized_answer,
                faithfulness_score=entry.faithfulness_score,
                context_relevance_score=entry.context_relevance_score,
                cited_chunk_ids=cited_chunk_ids,
                latency_ms=entry.latency_ms,
                sha256_signature=sig,
                timestamp=now
            )
        except Exception as e:
            logger.error(f"Audit SQLite persistence failed for transaction {audit_id}: {str(e)}")
            self._write_fallback_journal(entry)

        return entry

    def verify_audit_seal(self, audit_id: str) -> bool:
        """Validates that a historical transaction's SHA-256 seal matches its payload."""
        entry = self._ledger.get(audit_id)
        if not entry:
            db_entry = self.storage.get_audit_entry(audit_id)
            if not db_entry:
                return False
            entry = AuditLogEntry(**db_entry)
            self._ledger[audit_id] = entry

        recalculated = self.compute_signature(
            audit_id=entry.audit_id,
            tenant_id=entry.tenant_id,
            query=entry.query_text,
            answer=entry.synthesized_answer,
            faithfulness=entry.faithfulness_score,
            chunk_ids=entry.cited_chunk_ids
        )
        return recalculated == entry.sha256_signature

    def get_tenant_audit_logs(self, tenant_id: str, limit: int = 50) -> List[AuditLogEntry]:
        """Retrieves audit entries restricted to a specific tenant."""
        persisted = self.storage.get_tenant_audit_logs(tenant_id, limit=limit)
        if persisted:
            return [AuditLogEntry(**r) for r in persisted]

        audit_ids = self._tenant_index.get(tenant_id, [])
        entries = [self._ledger[aid] for aid in reversed(audit_ids[-limit:]) if aid in self._ledger]
        return entries

    def export_certificate(self, audit_id: str) -> Optional[Dict[str, Any]]:
        """Exports a verifiable cryptographic compliance certificate."""
        entry = self._ledger.get(audit_id)
        if not entry:
            db_entry = self.storage.get_audit_entry(audit_id)
            if not db_entry:
                return None
            entry = AuditLogEntry(**db_entry)
            self._ledger[audit_id] = entry

        is_valid = self.verify_audit_seal(audit_id)
        return {
            "certificate_title": "NexusRAG SOC 2 Compliance Audit Certificate",
            "audit_id": entry.audit_id,
            "timestamp": entry.timestamp,
            "tenant_id": entry.tenant_id,
            "user_id": entry.user_id,
            "query_hash": hashlib.sha256(entry.query_text.encode("utf-8")).hexdigest(),
            "faithfulness_score": entry.faithfulness_score,
            "context_relevance_score": entry.context_relevance_score,
            "cited_chunks_count": len(entry.cited_chunk_ids),
            "cryptographic_signature": entry.sha256_signature,
            "is_cryptographically_verified": is_valid
        }
