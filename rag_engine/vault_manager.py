from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from .ingestion import Document, DocumentIngestionPipeline, Chunk
from .indexing import HybridIndex
from .knowledge_graph import EntityKnowledgeGraph
from .pdf_inspector_engine import pdf_engine
from .raptor import RAPTORIndex
from .retriever import HybridRetriever
from .reranker import CrossEncoderReranker
from .storage import SQLiteStorageManager


class VaultComponents:
    """Encapsulates active retrieval components for a vault."""
    def __init__(self, vault_data: Dict[str, Any]):
        self.name = vault_data.get("name", "")
        self.description = vault_data.get("description", "")
        self.icon = vault_data.get("icon", "")
        self.index = vault_data.get("index")
        self.graph = vault_data.get("graph")
        self.documents = vault_data.get("documents", [])
        self.chunks = vault_data.get("chunks", [])
        self.retriever = HybridRetriever(index=self.index)
        self.reranker = CrossEncoderReranker(top_n=4)


class KnowledgeVaultInfo(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    document_count: int
    chunk_count: int


# Departmental Seed Vaults Data
DEFAULT_VAULTS_DATA = {
    "all": {
        "name": "All Enterprise Vaults (Unified)",
        "description": "Unified cross-departmental search across HR, SRE Infrastructure, InfoSec Compliance, and Procurement.",
        "icon": "🌐",
        "docs": [],
        "pdf_presets": []
    },
    "hr_benefits": {
        "name": "Human Resources & Benefits",
        "description": "Corporate PTO accrual, medical certifications, family leave, and bereavement guidelines.",
        "icon": "👥",
        "docs": [
            {
                "title": "Corporate PTO and Leave Policy 2026",
                "metadata": {"url": "https://intranet.corp/policies/pto-2026", "author": "HR Department", "page_number": 1},
                "content": """# Section 1: Paid Time Off (PTO) Entitlement
All full-time employees accrue 20 days of Paid Time Off (PTO) per calendar year. PTO accrues at a rate of 1.66 days per month. Unused PTO up to 5 days can roll over to the following fiscal year.

# Section 2: Extended Medical & Family Leave
For medical absences exceeding 3 consecutive days, employees must submit Form HR-402 (Medical Leave Certification) signed by a certified healthcare provider to HR within 48 hours. Bereavement leave provides up to 5 consecutive paid days without deducting from standard PTO balance."""
            }
        ],
        "pdf_presets": []
    },
    "sre_infra": {
        "name": "SRE & Infrastructure SLAs",
        "description": "Production uptime commitments, RTO/RPO targets, incident bridges, and ISO-27001 disaster recovery.",
        "icon": "⚡",
        "docs": [
            {
                "title": "Engineering Infrastructure & SLA Guidelines",
                "metadata": {"url": "https://wiki.corp/eng/sla-specs", "author": "SRE Lead", "page_number": 1},
                "content": """# Infrastructure Service Level Agreements (SLA)
Tier-1 production services must maintain 99.99% uptime availability. Any P0 outage requires an automated incident declaration within 5 minutes via the PagerDuty API-v2 bridge.

# Disaster Recovery (DR) and RTO Protocols
The Recovery Time Objective (RTO) for all Tier-1 relational databases is 15 minutes, with a Recovery Point Objective (RPO) of 60 seconds. Weekly snapshot backups are replicated to multi-region cold storage conforming to ISO-27001 standard section 9.4."""
            }
        ],
        "pdf_presets": []
    },
    "infosec_compliance": {
        "name": "Information Security & HIPAA",
        "description": "Mandatory authentication standards, FIDO2 MFA enforcement, Rule SEC-881, and HIPAA PHI safeguards.",
        "icon": "🛡️",
        "docs": [
            {
                "title": "Information Security & Access Management",
                "metadata": {"url": "https://infosec.corp/access-control", "author": "CISO Office", "page_number": 1},
                "content": """# Mandatory Authentication Standards
All access to internal portals requires Multi-Factor Authentication (MFA) via FIDO2 hardware keys or approved authenticator apps. SMS-based 2FA is strictly prohibited under Rule SEC-881.

# Data Encryption & HIPAA Safeguards
Customer Protected Health Information (PHI) must be encrypted at rest with AES-256 and in transit with TLS 1.3, adhering to HIPAA Compliance Rule 164.312. Production API keys must be rotated every 90 days using the Key Vault API."""
            }
        ],
        "pdf_presets": []
    },
    "procurement_quantum": {
        "name": "AI & Quantum Procurement",
        "description": "Hardware purchase authorizations, Form QPU-99, liquid cooling thermal limits, and cloud accelerator provisioning.",
        "icon": "🔬",
        "docs": [
            {
                "title": "Quantum AI Hardware Procurement Policy 2026",
                "metadata": {"url": "https://corp/quantum-procurement", "author": "Infrastructure VP", "page_number": 1},
                "content": """# Section 1: H100 and Quantum QPU Budgeting
All quantum processor purchase orders require Form QPU-99 signed by the VP of Engineering.
Cluster deployments must use liquid cooling with a thermal ceiling of 45 degrees Celsius."""
            }
        ],
        "pdf_presets": []
    },
    "pdf_standards": {
        "name": "PDF Standards & Policy Lab",
        "description": "Multi-page enterprise PDF documents, formal SLA escalation tables, and ISO-27001 disaster recovery matrices.",
        "icon": "📑",
        "docs": [],
        "pdf_presets": [
            {"preset": "ai_governance", "filename": "Enterprise_AI_Governance_Model_Risk_SEC909.pdf"},
            {"preset": "sre_dr_matrix", "filename": "Multi_Region_Disaster_Recovery_SLA_Matrix.pdf"},
            {"preset": "hr_benefits_matrix", "filename": "Executive_Compensation_PTO_Schedule_2026.pdf"}
        ]
    }
}


class MultiVaultManager:
    """
    Manages multiple isolated knowledge vaults plus a unified cross-vault index,
    backed by ACID SQLite persistence for restart durability.
    Supports heterogeneous document types (plain text, markdown, docx, xlsx, and layout-aware PDFs),
    hierarchical RAPTOR trees, and cross-vault multi-hop routing.
    """

    def __init__(self, ingestion_pipe: DocumentIngestionPipeline, storage: Optional[SQLiteStorageManager] = None):
        self.ingestion_pipe = ingestion_pipe
        self.storage = storage or SQLiteStorageManager()
        self.vaults: Dict[str, Dict[str, Any]] = {}
        self.active_vault_id: str = "all"
        self.raptor_index = RAPTORIndex()
        self._initialize_vaults()

    def _initialize_vaults(self):
        """Initializes departmental and unified vaults with seed text and PDF documents, synced with SQLite."""
        all_docs: List[Document] = []
        all_chunks: List[Chunk] = []

        vault_keys = ["hr_benefits", "sre_infra", "infosec_compliance", "procurement_quantum", "pdf_standards"]

        # Check if SQLite already has vault data
        has_persisted = self.storage.has_vault_data()

        if has_persisted:
            # Hydrate from SQLite
            persisted_vaults = self.storage.load_all_persisted_vaults_data()
            for vid, vdata in persisted_vaults.items():
                if vid == "all":
                    continue
                index = HybridIndex()
                graph = EntityKnowledgeGraph()
                docs = vdata["documents"]
                chunks = vdata["chunks"]
                index.build_index(docs, chunks)
                graph.build_graph(docs, chunks)

                self.vaults[vid] = {
                    "name": vdata["name"],
                    "description": vdata["description"],
                    "icon": vdata["icon"],
                    "index": index,
                    "graph": graph,
                    "documents": docs,
                    "chunks": chunks
                }

                if vid != "pdf_standards":
                    all_docs.extend(docs)
                    all_chunks.extend(chunks)

            # Ensure all default vaults exist
            for vault_id in vault_keys:
                if vault_id not in self.vaults and vault_id in DEFAULT_VAULTS_DATA:
                    data = DEFAULT_VAULTS_DATA[vault_id]
                    self.storage.save_vault(vault_id, data["name"], data["description"], data["icon"])
        else:
            # Seed from DEFAULT_VAULTS_DATA and write to SQLite
            for vault_id in vault_keys:
                if vault_id not in DEFAULT_VAULTS_DATA:
                    continue
                data = DEFAULT_VAULTS_DATA[vault_id]
                self.storage.save_vault(vault_id, data["name"], data["description"], data["icon"])

                index = HybridIndex()
                graph = EntityKnowledgeGraph()
                
                docs: List[Document] = []
                chunks: List[Chunk] = []

                # 1. Ingest Standard Documents
                for raw in data.get("docs", []):
                    doc = Document(
                        title=raw["title"],
                        content=raw["content"],
                        metadata=raw["metadata"]
                    )
                    c = self.ingestion_pipe.process_document(doc)
                    docs.append(doc)
                    chunks.extend(c)
                    self.storage.save_document(vault_id, doc)
                    self.storage.save_chunks(vault_id, c)

                # 2. Ingest Seed PDF Documents using PDF Inspector
                for pdf_info in data.get("pdf_presets", []):
                    try:
                        pdf_bytes = pdf_engine.generate_sample_pdf(pdf_info["preset"])
                        pdf_doc, pdf_chunks, _ = self.ingestion_pipe.process_pdf(
                            pdf_bytes=pdf_bytes,
                            filename=pdf_info["filename"],
                            vault_id=vault_id,
                            base_metadata={"preset": pdf_info["preset"]}
                        )
                        docs.append(pdf_doc)
                        chunks.extend(pdf_chunks)
                        self.storage.save_document(vault_id, pdf_doc)
                        self.storage.save_chunks(vault_id, pdf_chunks)
                    except Exception:
                        pass

                index.build_index(docs, chunks)
                graph.build_graph(docs, chunks)

                self.vaults[vault_id] = {
                    "name": data["name"],
                    "description": data["description"],
                    "icon": data["icon"],
                    "index": index,
                    "graph": graph,
                    "documents": docs,
                    "chunks": chunks
                }

                if vault_id != "pdf_standards":
                    all_docs.extend(docs)
                    all_chunks.extend(chunks)

            # Persist unified 'all' vault entry
            self.storage.save_vault("all", DEFAULT_VAULTS_DATA["all"]["name"], DEFAULT_VAULTS_DATA["all"]["description"], DEFAULT_VAULTS_DATA["all"]["icon"])

        # Build Unified "all" Vault
        unified_index = HybridIndex()
        unified_graph = EntityKnowledgeGraph()
        unified_index.build_index(all_docs, all_chunks)
        unified_graph.build_graph(all_docs, all_chunks)

        self.vaults["all"] = {
            "name": DEFAULT_VAULTS_DATA["all"]["name"],
            "description": DEFAULT_VAULTS_DATA["all"]["description"],
            "icon": DEFAULT_VAULTS_DATA["all"]["icon"],
            "index": unified_index,
            "graph": unified_graph,
            "documents": all_docs,
            "chunks": all_chunks
        }

        # Build RAPTOR Hierarchical Tree across all corpus chunks
        self.raptor_index.build_raptor_tree(all_chunks, all_docs)

    def add_document_to_vault(self, vault_id: str, doc: Document, chunks: List[Chunk]):
        """Persists document and chunks to SQLite and updates in-memory index structures."""
        target_vault_id = vault_id if vault_id in self.vaults else "all"
        vault = self.vaults[target_vault_id]

        # 1. Persist to SQLite
        self.storage.save_document(target_vault_id, doc)
        self.storage.save_chunks(target_vault_id, chunks)

        # 2. Update targeted vault memory
        vault["documents"].append(doc)
        vault["chunks"].extend(chunks)
        vault["index"].build_index(vault["documents"], vault["chunks"])
        vault["graph"].build_graph(vault["documents"], vault["chunks"])

        # 3. Update unified 'all' vault if ingested into specific vault
        if target_vault_id != "all":
            all_v = self.vaults["all"]
            all_v["documents"].append(doc)
            all_v["chunks"].extend(chunks)
            all_v["index"].build_index(all_v["documents"], all_v["chunks"])
            all_v["graph"].build_graph(all_v["documents"], all_v["chunks"])
            self.storage.save_document("all", doc)
            self.storage.save_chunks("all", chunks)

        # 4. Rebuild RAPTOR index
        self.raptor_index.build_raptor_tree(self.vaults["all"]["chunks"], self.vaults["all"]["documents"])

    def create_vault(self, vault_id: str, name: str, description: str = "", icon: str = "📁") -> bool:
        """Creates a new isolated knowledge vault and persists it to SQLite."""
        if vault_id in self.vaults:
            return False
        self.storage.save_vault(vault_id, name, description, icon)
        index = HybridIndex()
        graph = EntityKnowledgeGraph()
        self.vaults[vault_id] = {
            "name": name,
            "description": description,
            "icon": icon,
            "index": index,
            "graph": graph,
            "documents": [],
            "chunks": []
        }
        return True

    def list_vaults(self) -> List[KnowledgeVaultInfo]:
        """Returns metadata for all available knowledge vaults."""
        result = []
        # Predefined order first, then any custom vaults
        order = ["all", "hr_benefits", "sre_infra", "infosec_compliance", "procurement_quantum", "pdf_standards"]
        seen = set()
        for vid in order:
            if vid in self.vaults:
                v = self.vaults[vid]
                result.append(KnowledgeVaultInfo(
                    id=vid,
                    name=v["name"],
                    description=v["description"],
                    icon=v["icon"],
                    document_count=len(v["documents"]),
                    chunk_count=len(v["chunks"])
                ))
                seen.add(vid)
        for vid, v in self.vaults.items():
            if vid not in seen:
                result.append(KnowledgeVaultInfo(
                    id=vid,
                    name=v["name"],
                    description=v["description"],
                    icon=v["icon"],
                    document_count=len(v["documents"]),
                    chunk_count=len(v["chunks"])
                ))
        return result

    def get_vault(self, vault_id: str = "all") -> VaultComponents:
        """Returns encapsulated VaultComponents with retriever and reranker."""
        target_id = vault_id if vault_id in self.vaults else "all"
        return VaultComponents(self.vaults[target_id])

    def get_active_vault(self) -> Dict[str, Any]:
        """Returns the active knowledge vault components."""
        if self.active_vault_id not in self.vaults:
            self.active_vault_id = "all"
        return self.vaults[self.active_vault_id]

    def set_active_vault(self, vault_id: str) -> bool:
        """Switches active vault."""
        if vault_id in self.vaults:
            self.active_vault_id = vault_id
            return True
        return False
