import os
import tempfile
import pytest
from rag_engine.storage import SQLiteStorageManager
from rag_engine.session_store import ConversationSessionStore, ChatMessage
from rag_engine.query_expansion import AgenticQueryProcessor
from rag_engine.ingestion import DocumentIngestionPipeline
from rag_engine.vault_manager import MultiVaultManager
from rag_engine.generator import CitationEnforcedGenerator
from rag_engine.retriever import HybridRetriever
from rag_engine.reranker import CrossEncoderReranker


def test_session_store_message_recording():
    """Verify session creation, message logging, and history sliding window retrieval."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "session_test.db")
        storage = SQLiteStorageManager(db_path=db_path)
        session_store = ConversationSessionStore(storage=storage)

        sid = session_store.get_or_create_session(session_id="sess_demo_123", user_id="alice@corp.com", vault_id="hr_benefits")
        assert sid == "sess_demo_123"

        session_store.add_user_message(sid, "What is Form HR-402 used for?")
        session_store.add_assistant_message(sid, "Form HR-402 is used for medical absences exceeding 3 days.")

        history = session_store.get_session_history(sid)
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[0].content == "What is Form HR-402 used for?"
        assert history[1].role == "assistant"
        assert "Form HR-402" in history[1].content


def test_conversational_coreference_query_rewriting():
    """Verify follow-up query containing pronouns is accurately rewritten using conversation history."""
    qp = AgenticQueryProcessor()

    history = [
        {"role": "user", "content": "What is the filing process for Form HR-402?"},
        {"role": "assistant", "content": "Employees must submit Form HR-402 to HR within 48 hours for medical leave."}
    ]

    # Follow-up Turn 2: ambiguous pronoun "it"
    follow_up_query = "Who must sign it?"
    rewritten, was_resolved = qp.rewrite_conversational_query(follow_up_query, history)

    assert was_resolved is True
    assert "Form HR-402" in rewritten
    assert "who must sign" in rewritten.lower()

    # Full analysis pipeline check
    analysis = qp.analyze(follow_up_query, history=history)
    assert analysis.coreference_resolved is True
    assert analysis.rewritten_query is not None
    assert "Form HR-402" in analysis.rewritten_query
    assert any("Form HR-402" in q for q in analysis.expanded_queries)


def test_end_to_end_multi_turn_rag_flow():
    """Verify that a 2-turn conversation accurately retrieves contextual chunks on Turn 2."""
    pipe = DocumentIngestionPipeline(chunk_size=100, chunk_overlap=20)
    vault_mgr = MultiVaultManager(ingestion_pipe=pipe)
    qp = AgenticQueryProcessor()
    reranker = CrossEncoderReranker(top_n=3)
    generator = CitationEnforcedGenerator()

    # Turn 1
    t1_query = "What is the policy for medical leave exceeding 3 days?"
    t1_analysis = qp.analyze(t1_query)
    hr_vault = vault_mgr.vaults["hr_benefits"]
    retriever = HybridRetriever(index=hr_vault["index"])

    cands1 = retriever.retrieve(t1_query, overfetch_k=5, expanded_queries=t1_analysis.expanded_queries)
    top1 = reranker.rerank(t1_query, cands1, top_k=2)
    resp1 = generator.generate(t1_query, top1)
    assert "HR-402" in resp1.answer

    # Turn 2: Follow-up query with pronoun
    history = [
        {"role": "user", "content": t1_query},
        {"role": "assistant", "content": resp1.answer}
    ]
    t2_query = "Who must sign it?"
    t2_analysis = qp.analyze(t2_query, history=history)
    assert t2_analysis.coreference_resolved is True

    # Retrieve using rewritten query
    eff_query = t2_analysis.rewritten_query or t2_query
    cands2 = retriever.retrieve(eff_query, overfetch_k=5, expanded_queries=t2_analysis.expanded_queries)
    top2 = reranker.rerank(eff_query, cands2, top_k=2)
    resp2 = generator.generate(eff_query, top2)

    assert "healthcare provider" in resp2.answer.lower() or "physician" in resp2.answer.lower() or "certified" in resp2.answer.lower()
    assert len(resp2.citations) > 0
