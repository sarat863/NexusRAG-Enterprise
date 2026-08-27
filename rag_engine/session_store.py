import uuid
import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from .storage import SQLiteStorageManager


class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


class ConversationSessionStore:
    """
    Manages multi-turn conversation sessions with persistent SQLite storage.
    Provides session creation, sliding-window history extraction, and message buffering.
    """

    def __init__(self, storage: Optional[SQLiteStorageManager] = None):
        self.storage = storage or SQLiteStorageManager()

    def get_or_create_session(self, session_id: Optional[str] = None, user_id: str = "guest", vault_id: str = "all") -> str:
        """Retrieves an existing session or provisions a new unique session identifier."""
        sid = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        self.storage.create_or_get_chat_session(sid, user_id=user_id, vault_id=vault_id)
        return sid

    def add_user_message(self, session_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Records a user query turn to persistent session history."""
        self.storage.append_chat_message(session_id, role="user", content=content, metadata=metadata)

    def add_assistant_message(self, session_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Records a synthesized assistant response turn with citations metadata."""
        self.storage.append_chat_message(session_id, role="assistant", content=content, metadata=metadata)

    def get_session_history(self, session_id: str, limit: int = 10) -> List[ChatMessage]:
        """Fetches the last N turns of conversation history for prompt and coreference injection."""
        raw_msgs = self.storage.get_chat_history(session_id, limit=limit)
        return [
            ChatMessage(
                role=m["role"],
                content=m["content"],
                metadata=m.get("metadata", {}),
                timestamp=m.get("timestamp", "")
            )
            for m in raw_msgs
        ]

    def clear_session(self, session_id: str):
        """Clears the chat history for a session."""
        self.storage.clear_chat_history(session_id)
