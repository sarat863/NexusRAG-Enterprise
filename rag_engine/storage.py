import os
import json
import sqlite3
import datetime
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel
from .ingestion import Document, Chunk


class SQLiteStorageManager:
    """
    Production-grade SQLite Storage & Persistence Layer for NexusRAG Enterprise.
    Provides ACID transaction guarantees, process restart durability, WAL mode concurrency,
    and structured storage for Vaults, Documents, Chunks, Audit Logs, and Chat Sessions.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            self.db_path = os.path.join(data_dir, "nexusrag.db")
        else:
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
            self.db_path = db_path

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high concurrent read/write throughput
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        """Initializes relational tables and performance indexes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Vaults table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vaults (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    icon TEXT,
                    created_at TEXT NOT NULL
                );
            """)

            # 2. Documents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    vault_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (vault_id) REFERENCES vaults(id) ON DELETE CASCADE
                );
            """)

            # 3. Chunks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    vault_id TEXT NOT NULL,
                    doc_title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    token_count INTEGER NOT NULL,
                    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE,
                    FOREIGN KEY (vault_id) REFERENCES vaults(id) ON DELETE CASCADE
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_vault_id ON chunks(vault_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);")

            # 4. Immutable Audit Ledger
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    audit_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    query_text TEXT NOT NULL,
                    synthesized_answer TEXT NOT NULL,
                    faithfulness_score REAL NOT NULL,
                    context_relevance_score REAL NOT NULL,
                    cited_chunk_ids_json TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    sha256_signature TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_tenant_id ON audit_logs(tenant_id);")

            # 5. Multi-Turn Chat Sessions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    vault_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # 6. Chat Messages
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_session_id ON chat_messages(session_id);")

            conn.commit()

    # --- Vault Operations ---
    def save_vault(self, vault_id: str, name: str, description: str, icon: str, created_at: Optional[str] = None):
        created_at = created_at or datetime.datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO vaults (id, name, description, icon, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    icon=excluded.icon;
            """, (vault_id, name, description, icon, created_at))
            conn.commit()

    def get_all_vaults(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, description, icon, created_at FROM vaults;")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def has_vault_data(self) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM vaults;")
            return cursor.fetchone()[0] > 0

    # --- Document & Chunk Operations ---
    def save_document(self, vault_id: str, doc: Document):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO documents (id, vault_id, title, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    content=excluded.content,
                    metadata_json=excluded.metadata_json;
            """, (doc.id, vault_id, doc.title, doc.content, json.dumps(doc.metadata), doc.created_at))
            conn.commit()

    def save_chunks(self, vault_id: str, chunks: List[Chunk]):
        if not chunks:
            return
        with self._get_connection() as conn:
            data = [
                (c.id, c.doc_id, vault_id, c.doc_title, c.content, json.dumps(c.metadata), c.token_count)
                for c in chunks
            ]
            conn.executemany("""
                INSERT INTO chunks (id, doc_id, vault_id, doc_title, content, metadata_json, token_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    content=excluded.content,
                    metadata_json=excluded.metadata_json,
                    token_count=excluded.token_count;
            """, data)
            conn.commit()

    def load_vault_documents_and_chunks(self, vault_id: str) -> Tuple[List[Document], List[Chunk]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, content, metadata_json, created_at FROM documents WHERE vault_id = ?;", (vault_id,))
            doc_rows = cursor.fetchall()
            docs = [
                Document(
                    id=r["id"],
                    title=r["title"],
                    content=r["content"],
                    metadata=json.loads(r["metadata_json"]),
                    created_at=r["created_at"]
                )
                for r in doc_rows
            ]

            cursor.execute("SELECT id, doc_id, doc_title, content, metadata_json, token_count FROM chunks WHERE vault_id = ?;", (vault_id,))
            chunk_rows = cursor.fetchall()
            chunks = [
                Chunk(
                    id=r["id"],
                    doc_id=r["doc_id"],
                    doc_title=r["doc_title"],
                    content=r["content"],
                    metadata=json.loads(r["metadata_json"]),
                    token_count=r["token_count"]
                )
                for r in chunk_rows
            ]
            return docs, chunks

    def load_all_persisted_vaults_data(self) -> Dict[str, Dict[str, Any]]:
        """Loads all vaults, documents, and chunks from SQLite database."""
        vaults_data = {}
        for v in self.get_all_vaults():
            vid = v["id"]
            docs, chunks = self.load_vault_documents_and_chunks(vid)
            vaults_data[vid] = {
                "name": v["name"],
                "description": v["description"],
                "icon": v["icon"],
                "documents": docs,
                "chunks": chunks
            }
        return vaults_data

    # --- Audit Ledger Operations ---
    def record_audit_entry(
        self,
        audit_id: str,
        tenant_id: str,
        user_id: str,
        query_text: str,
        synthesized_answer: str,
        faithfulness_score: float,
        context_relevance_score: float,
        cited_chunk_ids: List[str],
        latency_ms: float,
        sha256_signature: str,
        timestamp: str
    ):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO audit_logs (
                    audit_id, tenant_id, user_id, query_text, synthesized_answer,
                    faithfulness_score, context_relevance_score, cited_chunk_ids_json,
                    latency_ms, sha256_signature, timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                audit_id, tenant_id, user_id, query_text, synthesized_answer,
                faithfulness_score, context_relevance_score, json.dumps(cited_chunk_ids),
                latency_ms, sha256_signature, timestamp
            ))
            conn.commit()

    def get_audit_entry(self, audit_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_logs WHERE audit_id = ?;", (audit_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            res["cited_chunk_ids"] = json.loads(res["cited_chunk_ids_json"])
            return res

    def get_tenant_audit_logs(self, tenant_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if tenant_id == "all" or tenant_id == "enterprise_hq":
                cursor.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?;", (limit,))
            else:
                cursor.execute("SELECT * FROM audit_logs WHERE tenant_id = ? ORDER BY timestamp DESC LIMIT ?;", (tenant_id, limit))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["cited_chunk_ids"] = json.loads(d["cited_chunk_ids_json"])
                results.append(d)
            return results

    # --- Multi-Turn Chat Session Operations ---
    def create_or_get_chat_session(self, session_id: str, user_id: str = "guest", vault_id: str = "all") -> Dict[str, Any]:
        now = datetime.datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT session_id, user_id, vault_id, created_at, updated_at FROM chat_sessions WHERE session_id = ?;", (session_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            conn.execute("""
                INSERT INTO chat_sessions (session_id, user_id, vault_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?);
            """, (session_id, user_id, vault_id, now, now))
            conn.commit()
            return {
                "session_id": session_id,
                "user_id": user_id,
                "vault_id": vault_id,
                "created_at": now,
                "updated_at": now
            }

    def append_chat_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        now = datetime.datetime.utcnow().isoformat()
        meta_json = json.dumps(metadata or {})
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO chat_messages (session_id, role, content, metadata_json, timestamp)
                VALUES (?, ?, ?, ?, ?);
            """, (session_id, role, content, meta_json, now))
            conn.execute("UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?;", (now, session_id))
            conn.commit()

    def get_chat_history(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content, metadata_json, timestamp
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY id ASC
                LIMIT ?;
            """, (session_id, limit))
            rows = cursor.fetchall()
            return [
                {
                    "role": r["role"],
                    "content": r["content"],
                    "metadata": json.loads(r["metadata_json"]),
                    "timestamp": r["timestamp"]
                }
                for r in rows
            ]

    def clear_chat_history(self, session_id: str):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM chat_messages WHERE session_id = ?;", (session_id,))
            conn.commit()
