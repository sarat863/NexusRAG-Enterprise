import os
import tempfile
import pytest
from rag_engine.storage import SQLiteStorageManager
from rag_engine.ingestion import Document, Chunk, DocumentIngestionPipeline
from rag_engine.vault_manager import MultiVaultManager
from rag_engine.audit_vault import AuditVaultManager


def test_sqlite_storage_initialization():
    """Verify SQLite database file is created with WAL mode and proper schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_nexusrag.db")
        storage = SQLiteStorageManager(db_path=db_path)

        assert os.path.exists(db_path)
        assert storage.has_vault_data() is False

        # Save a vault
        storage.save_vault("hr_benefits", "HR Vault", "HR policies", "👥")
        assert storage.has_vault_data() is True
        vaults = storage.get_all_vaults()
        assert len(vaults) == 1
        assert vaults[0]["id"] == "hr_benefits"


def test_document_and_chunk_persistence_across_restart():
    """Verify documents and chunks survive process restart simulation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_nexusrag.db")
        
        # 1. Process 1: Save data
        storage1 = SQLiteStorageManager(db_path=db_path)
        storage1.save_vault("sre_infra", "SRE SLAs", "SRE documentation", "⚡")

        doc = Document(
            id="doc_sre_001",
            title="Database Disaster Recovery",
            content="Tier-1 RTO target is 15 minutes with 60 seconds RPO.",
            metadata={"author": "SRE Lead", "version": "4.0"}
        )
        chunk = Chunk(
            id="chunk_sre_001_0",
            doc_id="doc_sre_001",
            doc_title="Database Disaster Recovery",
            content="Tier-1 RTO target is 15 minutes with 60 seconds RPO.",
            metadata={"section_header": "Disaster Recovery", "page_number": 1},
            token_count=10
        )
        storage1.save_document("sre_infra", doc)
        storage1.save_chunks("sre_infra", [chunk])

        # 2. Process 2: New manager instance pointing to same SQLite DB
        storage2 = SQLiteStorageManager(db_path=db_path)
        docs, chunks = storage2.load_vault_documents_and_chunks("sre_infra")

        assert len(docs) == 1
        assert docs[0].id == "doc_sre_001"
        assert docs[0].title == "Database Disaster Recovery"
        assert docs[0].metadata["version"] == "4.0"

        assert len(chunks) == 1
        assert chunks[0].id == "chunk_sre_001_0"
        assert chunks[0].content == "Tier-1 RTO target is 15 minutes with 60 seconds RPO."
        assert chunks[0].metadata["section_header"] == "Disaster Recovery"


def test_audit_ledger_sqlite_durability():
    """Verify cryptographic audit transactions are stored in SQLite and can be verified across restarts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "audit_test.db")
        storage = SQLiteStorageManager(db_path=db_path)
        audit_mgr = AuditVaultManager(storage=storage)

        entry = audit_mgr.record_transaction(
            tenant_id="infosec_compliance",
            user_id="compliance_auditor@nexusrag.com",
            query_text="What rule mandates FIDO2 keys?",
            synthesized_answer="Rule SEC-881 mandates FIDO2 hardware authentication.",
            faithfulness_score=0.99,
            context_relevance_score=0.97,
            cited_chunk_ids=["chunk_sec_0"],
            latency_ms=15.2
        )

        assert entry.audit_id.startswith("AUDIT-NEXUS-")
        assert len(entry.sha256_signature) == 64

        # Verify from fresh manager instance loading from DB
        fresh_mgr = AuditVaultManager(storage=storage)
        assert fresh_mgr.verify_audit_seal(entry.audit_id) is True

        logs = fresh_mgr.get_tenant_audit_logs("infosec_compliance")
        assert len(logs) == 1
        assert logs[0].audit_id == entry.audit_id
        assert logs[0].sha256_signature == entry.sha256_signature


def test_vault_manager_sqlite_hydration():
    """Verify MultiVaultManager hydrates all seed and dynamic vaults from SQLite."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "vault_hydration.db")
        storage = SQLiteStorageManager(db_path=db_path)
        pipe = DocumentIngestionPipeline(chunk_size=100, chunk_overlap=20)

        # First boot: seeds SQLite
        vm1 = MultiVaultManager(ingestion_pipe=pipe, storage=storage)
        initial_vaults = vm1.list_vaults()
        assert len(initial_vaults) >= 5

        # Ingest a custom dynamic document
        custom_doc = Document(
            id="custom_001",
            title="Custom Security Directive",
            content="All access tokens must be rotated every 24 hours under SEC-999.",
            metadata={"classification": "RESTRICTED"}
        )
        custom_chunks = pipe.process_document(custom_doc)
        vm1.add_document_to_vault("infosec_compliance", custom_doc, custom_chunks)

        # Second boot (simulating process restart)
        vm2 = MultiVaultManager(ingestion_pipe=pipe, storage=storage)
        v = vm2.vaults["infosec_compliance"]
        doc_ids = [d.id for d in v["documents"]]
        assert "custom_001" in doc_ids

        # Search index should contain the newly persisted document
        res = v["index"].search_sparse("SEC-999", top_k=2)
        assert len(res) > 0
        assert "SEC-999" in res[0][0].content
