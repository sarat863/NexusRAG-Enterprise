import pytest
from benchmarks.hard_test_dataset import HARD_BENCHMARK_QUERIES, generate_synthetic_distractor_corpus
from benchmarks.metrics import (
    calculate_hit_at_k,
    calculate_recall_at_k,
    calculate_mrr,
    calculate_ndcg_at_k,
    is_refusal_response
)
from rag_engine.ingestion import DocumentIngestionPipeline, Chunk
from rag_engine.indexing import HybridIndex
from rag_engine.retriever import HybridRetriever
from rag_engine.reranker import CrossEncoderReranker
from rag_engine.generator import CitationEnforcedGenerator
from rag_engine.crag import CorrectiveRAGEvaluator
from rag_engine.query_expansion import AgenticQueryProcessor
from rag_engine.vault_manager import MultiVaultManager


@pytest.fixture(scope="module")
def benchmark_env():
    pipe = DocumentIngestionPipeline(chunk_size=100, chunk_overlap=20)
    vault_mgr = MultiVaultManager(ingestion_pipe=pipe)
    qp = AgenticQueryProcessor()
    reranker = CrossEncoderReranker(top_n=4)
    generator = CitationEnforcedGenerator()
    crag = CorrectiveRAGEvaluator()

    return {
        "pipe": pipe,
        "vault_mgr": vault_mgr,
        "query_processor": qp,
        "reranker": reranker,
        "generator": generator,
        "crag": crag
    }


def test_adversarial_hallucination_traps(benchmark_env):
    """Verify that fake forms and out-of-domain traps trigger zero-hallucination refusals."""
    vm = benchmark_env["vault_mgr"]
    qp = benchmark_env["query_processor"]
    reranker = benchmark_env["reranker"]
    generator = benchmark_env["generator"]
    crag = benchmark_env["crag"]

    unanswerable_cases = [q for q in HARD_BENCHMARK_QUERIES if q["is_unanswerable"]]
    assert len(unanswerable_cases) >= 5

    for case in unanswerable_cases:
        query = case["query"]
        vault = vm.vaults.get(case["vault_id"], vm.vaults["all"])
        retriever = HybridRetriever(vault["index"])

        q_analysis = qp.analyze(query)
        cands = retriever.retrieve(query, overfetch_k=10, expanded_queries=q_analysis.expanded_queries)
        reranked = reranker.rerank(query, cands, top_k=4)
        crag_res = crag.evaluate_retrieval_confidence(query, reranked)

        if crag_res.action == "INCORRECT":
            resp = generator.generate(query, [])
        else:
            resp = generator.generate(query, reranked)

        assert is_refusal_response(resp.answer), f"Failed to refuse unanswerable query: {query} -> {resp.answer}"
        assert len(resp.citations) == 0, f"Expected 0 citations for unanswerable query: {query}"


def test_needle_in_distractor_haystack(benchmark_env):
    """Verify needle retrieval accuracy when 50 distractor policy documents are indexed."""
    pipe = benchmark_env["pipe"]
    vm = benchmark_env["vault_mgr"]
    qp = benchmark_env["query_processor"]
    reranker = benchmark_env["reranker"]

    distractors = generate_synthetic_distractor_corpus(num_docs=50)
    real_docs = vm.vaults["all"]["documents"]
    all_docs = real_docs + distractors

    all_chunks = []
    for d in all_docs:
        all_chunks.extend(pipe.process_document(d))

    noisy_index = HybridIndex()
    noisy_index.build_index(all_docs, all_chunks)
    noisy_retriever = HybridRetriever(noisy_index)

    # Critical needles to locate
    needles = [
        ("What form is submitted for medical absences exceeding 3 days?", "HR-402"),
        ("Which rule bans SMS-based 2FA and mandates FIDO2 keys?", "SEC-881"),
        ("What form is required for quantum processor purchase orders?", "QPU-99"),
        ("What is the uptime SLA and database RTO for Tier-1 production?", "15 minutes")
    ]

    for q, needle in needles:
        q_analysis = qp.analyze(q)
        cands = noisy_retriever.retrieve(q, overfetch_k=25, expanded_queries=q_analysis.expanded_queries)
        reranked = reranker.rerank(q, cands, top_k=4)

        found = any(needle.lower() in c.chunk.content.lower() for c in reranked)
        assert found, f"Needle '{needle}' not found in top reranked chunks for query: {q}"


def test_noise_and_typo_resilience(benchmark_env):
    """Verify accurate extraction despite typos, lowercasing, and colloquial formulations."""
    vm = benchmark_env["vault_mgr"]
    qp = benchmark_env["query_processor"]
    reranker = benchmark_env["reranker"]
    generator = benchmark_env["generator"]

    noise_cases = [q for q in HARD_BENCHMARK_QUERIES if q["category"] == "noise_typo_colloquial"]
    for case in noise_cases:
        query = case["query"]
        vault = vm.vaults.get(case["vault_id"], vm.vaults["all"])
        retriever = HybridRetriever(vault["index"])

        q_analysis = qp.analyze(query)
        cands = retriever.retrieve(query, overfetch_k=15, expanded_queries=q_analysis.expanded_queries)
        reranked = reranker.rerank(query, cands, top_k=4)
        resp = generator.generate(query, reranked)

        for expected in case["expected_tokens"]:
            assert expected.lower() in resp.answer.lower(), (
                f"Missing token '{expected}' in answer '{resp.answer}' for query '{query}'"
            )
        assert len(resp.citations) > 0


def test_multi_hop_cross_vault_synthesis(benchmark_env):
    """Verify multi-hop queries across multiple vaults."""
    vm = benchmark_env["vault_mgr"]
    qp = benchmark_env["query_processor"]
    reranker = benchmark_env["reranker"]
    generator = benchmark_env["generator"]

    multi_cases = [q for q in HARD_BENCHMARK_QUERIES if q["category"] == "multi_hop_cross_vault"]
    for case in multi_cases:
        query = case["query"]
        unified_vault = vm.vaults["all"]
        retriever = HybridRetriever(unified_vault["index"])

        q_analysis = qp.analyze(query)
        cands = retriever.retrieve(query, overfetch_k=25, expanded_queries=q_analysis.expanded_queries)
        reranked = reranker.rerank(query, cands, top_k=4)
        resp = generator.generate(query, reranked)

        for expected in case["expected_tokens"]:
            assert expected.lower() in resp.answer.lower(), (
                f"Expected '{expected}' in multi-hop answer: '{resp.answer}'"
            )


def test_concurrency_stress(benchmark_env):
    """Stress test the pipeline with 20 parallel requests to ensure thread safety and no deadlock."""
    import concurrent.futures

    vm = benchmark_env["vault_mgr"]
    qp = benchmark_env["query_processor"]
    reranker = benchmark_env["reranker"]
    generator = benchmark_env["generator"]

    queries = [
        "What form is needed for medical absences exceeding 3 days?",
        "What is the RTO and RPO for Tier-1 databases?",
        "What rule bans SMS 2FA?",
        "What form is required for quantum processor purchases?"
    ] * 5  # 20 queries

    def execute_one(q):
        vault = vm.vaults["all"]
        retriever = HybridRetriever(vault["index"])
        q_analysis = qp.analyze(q)
        cands = retriever.retrieve(q, overfetch_k=10, expanded_queries=q_analysis.expanded_queries)
        reranked = reranker.rerank(q, cands, top_k=3)
        return generator.generate(q, reranked)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(execute_one, q) for q in queries]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 20
    for r in results:
        assert len(r.answer) > 0
