from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from .ingestion import Document, DocumentIngestionPipeline, Chunk
from .indexing import HybridIndex
from .knowledge_graph import EntityKnowledgeGraph


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
        "docs": []
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
        ]
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
        ]
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
        ]
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
        ]
    }
}


class MultiVaultManager:
    """
    Manages multiple isolated knowledge vaults plus a unified cross-vault index.
    """

    def __init__(self, ingestion_pipe: DocumentIngestionPipeline):
        self.ingestion_pipe = ingestion_pipe
        self.vaults: Dict[str, Dict[str, Any]] = {}
        self.active_vault_id: str = "all"
        self._initialize_vaults()

    def _initialize_vaults(self):
        """Initializes departmental and unified vaults."""
        all_docs: List[Document] = []
        all_chunks: List[Chunk] = []

        for vault_id, data in DEFAULT_VAULTS_DATA.items():
            if vault_id == "all":
                continue

            index = HybridIndex()
            graph = EntityKnowledgeGraph()
            
            docs: List[Document] = []
            chunks: List[Chunk] = []

            for raw in data["docs"]:
                doc = Document(
                    title=raw["title"],
                    content=raw["content"],
                    metadata=raw["metadata"]
                )
                c = self.ingestion_pipe.process_document(doc)
                docs.append(doc)
                chunks.extend(c)

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
            all_docs.extend(docs)
            all_chunks.extend(chunks)

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

    def list_vaults(self) -> List[KnowledgeVaultInfo]:
        """Returns metadata for all available knowledge vaults."""
        result = []
        # Ensure 'all' is first
        order = ["all", "hr_benefits", "sre_infra", "infosec_compliance", "procurement_quantum"]
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
        return result

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
