#!/usr/bin/env python3
"""
NexusRAG Enterprise v0.2.0 - Advanced Hard Benchmark & Stress Testing Runner.
Runs end-to-end quantitative IR benchmarks, adversarial stress tests,
needle-in-a-haystack distractor scaling, noise robustness, and concurrency load profiling.
"""

import os
import sys
import time
import json
import statistics
import concurrent.futures
from typing import List, Dict, Any, Tuple

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_engine.config import default_config
from rag_engine.ingestion import Document, DocumentIngestionPipeline, Chunk
from rag_engine.indexing import HybridIndex
from rag_engine.retriever import HybridRetriever, ScoredCandidate
from rag_engine.reranker import CrossEncoderReranker
from rag_engine.generator import CitationEnforcedGenerator
from rag_engine.query_expansion import AgenticQueryProcessor
from rag_engine.crag import CorrectiveRAGEvaluator
from rag_engine.evaluator import RAGTriadEvaluator
from rag_engine.vault_manager import MultiVaultManager

from benchmarks.hard_test_dataset import HARD_BENCHMARK_QUERIES, generate_synthetic_distractor_corpus
from benchmarks.metrics import (
    calculate_hit_at_k,
    calculate_recall_at_k,
    calculate_precision_at_k,
    calculate_mrr,
    calculate_ndcg_at_k,
    calculate_citation_metrics,
    is_refusal_response
)


def print_banner(title: str):
    print("\n" + "═" * 84)
    print(f"  ⚡ {title.upper()} ⚡")
    print("═" * 84)


def print_sub_header(title: str):
    print("\n" + "─" * 84)
    print(f"  ▶ {title}")
    print("─" * 84)


class RAGHardBenchmarkRunner:
    def __init__(self):
        self.ingestion_pipe = DocumentIngestionPipeline(chunk_size=100, chunk_overlap=20)
        self.vault_manager = MultiVaultManager(ingestion_pipe=self.ingestion_pipe)
        self.query_processor = AgenticQueryProcessor()
        self.reranker = CrossEncoderReranker(top_n=default_config.rerank_top_k)
        self.generator = CitationEnforcedGenerator()
        self.crag_evaluator = CorrectiveRAGEvaluator()
        self.triad_evaluator = RAGTriadEvaluator()
        self.results: Dict[str, Any] = {}

    def find_gold_chunk_ids(self, vault_id: str, pattern: str) -> List[str]:
        """Finds chunk IDs matching the gold content pattern."""
        if not pattern:
            return []
        vault = self.vault_manager.vaults.get(vault_id, self.vault_manager.vaults["all"])
        matching = []
        for c in vault["chunks"]:
            if pattern.lower() in c.content.lower():
                matching.append(c.id)
        return matching

    # -------------------------------------------------------------------------
    # TEST PILLAR 1: Multi-Strategy IR Ranking Benchmark
    # -------------------------------------------------------------------------
    def run_ir_ranking_benchmark(self) -> Dict[str, Any]:
        print_sub_header("PILLAR 1: Multi-Strategy Information Retrieval (IR) Benchmark")
        
        strategies = {
            "Dense Vector Only": {"hits_1": [], "hits_3": [], "hits_5": [], "recall_3": [], "recall_5": [], "mrr": [], "ndcg_3": [], "ndcg_5": [], "latencies": []},
            "Sparse BM25 Only": {"hits_1": [], "hits_3": [], "hits_5": [], "recall_3": [], "recall_5": [], "mrr": [], "ndcg_3": [], "ndcg_5": [], "latencies": []},
            "Hybrid RRF (k=60)": {"hits_1": [], "hits_3": [], "hits_5": [], "recall_3": [], "recall_5": [], "mrr": [], "ndcg_3": [], "ndcg_5": [], "latencies": []},
            "NexusRAG (Hybrid+CrossEncoder+CRAG)": {"hits_1": [], "hits_3": [], "hits_5": [], "recall_3": [], "recall_5": [], "mrr": [], "ndcg_3": [], "ndcg_5": [], "latencies": []}
        }

        test_queries = [q for q in HARD_BENCHMARK_QUERIES if q["gold_content_pattern"] and not q["is_unanswerable"]]
        print(f"Evaluating {len(test_queries)} ground-truth queries across 4 retrieval strategies...\n")

        for tc in test_queries:
            query = tc["query"]
            vault_id = tc["vault_id"]
            gold_pattern = tc["gold_content_pattern"]
            gold_ids = self.find_gold_chunk_ids(vault_id, gold_pattern)
            if not gold_ids:
                continue

            vault = self.vault_manager.vaults.get(vault_id, self.vault_manager.vaults["all"])
            index: HybridIndex = vault["index"]
            retriever = HybridRetriever(index=index)

            # Strategy 1: Dense Vector Only
            t0 = time.time()
            dense_res = index.search_dense(query, top_k=10)
            dense_lat = (time.time() - t0) * 1000
            dense_ids = [c.id for c, _ in dense_res]
            strategies["Dense Vector Only"]["hits_1"].append(calculate_hit_at_k(dense_ids, gold_ids, 1))
            strategies["Dense Vector Only"]["hits_3"].append(calculate_hit_at_k(dense_ids, gold_ids, 3))
            strategies["Dense Vector Only"]["hits_5"].append(calculate_hit_at_k(dense_ids, gold_ids, 5))
            strategies["Dense Vector Only"]["recall_3"].append(calculate_recall_at_k(dense_ids, gold_ids, 3))
            strategies["Dense Vector Only"]["recall_5"].append(calculate_recall_at_k(dense_ids, gold_ids, 5))
            strategies["Dense Vector Only"]["mrr"].append(calculate_mrr(dense_ids, gold_ids))
            strategies["Dense Vector Only"]["ndcg_3"].append(calculate_ndcg_at_k(dense_ids, gold_ids, 3))
            strategies["Dense Vector Only"]["ndcg_5"].append(calculate_ndcg_at_k(dense_ids, gold_ids, 5))
            strategies["Dense Vector Only"]["latencies"].append(dense_lat)

            # Strategy 2: Sparse BM25 Only
            t0 = time.time()
            sparse_res = index.search_sparse(query, top_k=10)
            sparse_lat = (time.time() - t0) * 1000
            sparse_ids = [c.id for c, _ in sparse_res]
            strategies["Sparse BM25 Only"]["hits_1"].append(calculate_hit_at_k(sparse_ids, gold_ids, 1))
            strategies["Sparse BM25 Only"]["hits_3"].append(calculate_hit_at_k(sparse_ids, gold_ids, 3))
            strategies["Sparse BM25 Only"]["hits_5"].append(calculate_hit_at_k(sparse_ids, gold_ids, 5))
            strategies["Sparse BM25 Only"]["recall_3"].append(calculate_recall_at_k(sparse_ids, gold_ids, 3))
            strategies["Sparse BM25 Only"]["recall_5"].append(calculate_recall_at_k(sparse_ids, gold_ids, 5))
            strategies["Sparse BM25 Only"]["mrr"].append(calculate_mrr(sparse_ids, gold_ids))
            strategies["Sparse BM25 Only"]["ndcg_3"].append(calculate_ndcg_at_k(sparse_ids, gold_ids, 3))
            strategies["Sparse BM25 Only"]["ndcg_5"].append(calculate_ndcg_at_k(sparse_ids, gold_ids, 5))
            strategies["Sparse BM25 Only"]["latencies"].append(sparse_lat)

            # Strategy 3: Hybrid RRF
            t0 = time.time()
            rrf_res = retriever.retrieve(query, overfetch_k=10, alpha=0.5, k=60)
            rrf_lat = (time.time() - t0) * 1000
            rrf_ids = [c.chunk.id for c in rrf_res]
            strategies["Hybrid RRF (k=60)"]["hits_1"].append(calculate_hit_at_k(rrf_ids, gold_ids, 1))
            strategies["Hybrid RRF (k=60)"]["hits_3"].append(calculate_hit_at_k(rrf_ids, gold_ids, 3))
            strategies["Hybrid RRF (k=60)"]["hits_5"].append(calculate_hit_at_k(rrf_ids, gold_ids, 5))
            strategies["Hybrid RRF (k=60)"]["recall_3"].append(calculate_recall_at_k(rrf_ids, gold_ids, 3))
            strategies["Hybrid RRF (k=60)"]["recall_5"].append(calculate_recall_at_k(rrf_ids, gold_ids, 5))
            strategies["Hybrid RRF (k=60)"]["mrr"].append(calculate_mrr(rrf_ids, gold_ids))
            strategies["Hybrid RRF (k=60)"]["ndcg_3"].append(calculate_ndcg_at_k(rrf_ids, gold_ids, 3))
            strategies["Hybrid RRF (k=60)"]["ndcg_5"].append(calculate_ndcg_at_k(rrf_ids, gold_ids, 5))
            strategies["Hybrid RRF (k=60)"]["latencies"].append(rrf_lat)

            # Strategy 4: NexusRAG Hybrid + CrossEncoder + CRAG
            t0 = time.time()
            q_analysis = self.query_processor.analyze(query)
            nexus_candidates = retriever.retrieve(query, overfetch_k=20, expanded_queries=q_analysis.expanded_queries)
            reranked = self.reranker.rerank(query, nexus_candidates, top_k=5)
            nexus_lat = (time.time() - t0) * 1000
            nexus_ids = [c.chunk.id for c in reranked]
            strategies["NexusRAG (Hybrid+CrossEncoder+CRAG)"]["hits_1"].append(calculate_hit_at_k(nexus_ids, gold_ids, 1))
            strategies["NexusRAG (Hybrid+CrossEncoder+CRAG)"]["hits_3"].append(calculate_hit_at_k(nexus_ids, gold_ids, 3))
            strategies["NexusRAG (Hybrid+CrossEncoder+CRAG)"]["hits_5"].append(calculate_hit_at_k(nexus_ids, gold_ids, 5))
            strategies["NexusRAG (Hybrid+CrossEncoder+CRAG)"]["recall_3"].append(calculate_recall_at_k(nexus_ids, gold_ids, 3))
            strategies["NexusRAG (Hybrid+CrossEncoder+CRAG)"]["recall_5"].append(calculate_recall_at_k(nexus_ids, gold_ids, 5))
            strategies["NexusRAG (Hybrid+CrossEncoder+CRAG)"]["mrr"].append(calculate_mrr(nexus_ids, gold_ids))
            strategies["NexusRAG (Hybrid+CrossEncoder+CRAG)"]["ndcg_3"].append(calculate_ndcg_at_k(nexus_ids, gold_ids, 3))
            strategies["NexusRAG (Hybrid+CrossEncoder+CRAG)"]["ndcg_5"].append(calculate_ndcg_at_k(nexus_ids, gold_ids, 5))
            strategies["NexusRAG (Hybrid+CrossEncoder+CRAG)"]["latencies"].append(nexus_lat)

        summary_table = []
        print(f"{'Strategy Name':<38} | {'Hit@1':<7} | {'Hit@3':<7} | {'MRR':<7} | {'NDCG@3':<7} | {'Recall@3':<8} | {'Avg Lat':<8}")
        print("─" * 95)

        summary_dict = {}
        for strat_name, metrics in strategies.items():
            avg_hit1 = statistics.mean(metrics["hits_1"]) if metrics["hits_1"] else 0.0
            avg_hit3 = statistics.mean(metrics["hits_3"]) if metrics["hits_3"] else 0.0
            avg_mrr = statistics.mean(metrics["mrr"]) if metrics["mrr"] else 0.0
            avg_ndcg3 = statistics.mean(metrics["ndcg_3"]) if metrics["ndcg_3"] else 0.0
            avg_rec3 = statistics.mean(metrics["recall_3"]) if metrics["recall_3"] else 0.0
            avg_lat = statistics.mean(metrics["latencies"]) if metrics["latencies"] else 0.0

            summary_dict[strat_name] = {
                "hit@1": round(avg_hit1, 4),
                "hit@3": round(avg_hit3, 4),
                "mrr": round(avg_mrr, 4),
                "ndcg@3": round(avg_ndcg3, 4),
                "recall@3": round(avg_rec3, 4),
                "avg_latency_ms": round(avg_lat, 2)
            }

            print(f"{strat_name:<38} | {avg_hit1*100:>5.1f}%  | {avg_hit3*100:>5.1f}%  | {avg_mrr:>6.3f} | {avg_ndcg3:>6.3f} | {avg_rec3*100:>6.1f}%  | {avg_lat:>6.2f}ms")

        return summary_dict

    # -------------------------------------------------------------------------
    # TEST PILLAR 2: Adversarial & Hallucination Trap Stress Testing
    # -------------------------------------------------------------------------
    def run_adversarial_stress_test(self) -> Dict[str, Any]:
        print_sub_header("PILLAR 2: Adversarial & Hallucination Trap Stress Testing")
        
        adv_queries = [q for q in HARD_BENCHMARK_QUERIES if q["is_unanswerable"] or q["category"].startswith("adversarial")]
        print(f"Testing {len(adv_queries)} adversarial hallucination traps and injection attacks...\n")

        passed = 0
        details = []

        for q_item in adv_queries:
            query = q_item["query"]
            vault_id = q_item["vault_id"]
            expected_unans = q_item["is_unanswerable"]
            vault = self.vault_manager.vaults.get(vault_id, self.vault_manager.vaults["all"])
            index: HybridIndex = vault["index"]
            retriever = HybridRetriever(index=index)

            q_analysis = self.query_processor.analyze(query)
            cands = retriever.retrieve(query, overfetch_k=15, expanded_queries=q_analysis.expanded_queries)
            reranked = self.reranker.rerank(query, cands, top_k=4)
            crag_res = self.crag_evaluator.evaluate_retrieval_confidence(query, reranked)

            if crag_res.action == "INCORRECT":
                gen_res = self.generator.generate(query, [])
            else:
                gen_res = self.generator.generate(query, reranked)

            is_refusal = is_refusal_response(gen_res.answer)
            has_citations = len(gen_res.citations) > 0

            # If unanswerable trap, must refuse and have zero citations
            if expected_unans:
                success = is_refusal and not has_citations
            else:
                # E.g. prompt injection asking to disregard rule: must uphold truth
                all_tokens_found = all(tok.lower() in gen_res.answer.lower() for tok in q_item["expected_tokens"])
                success = all_tokens_found

            status = "✅ PASS" if success else "❌ FAIL"
            if success:
                passed += 1

            details.append({
                "id": q_item["id"],
                "query": query,
                "crag_action": crag_res.action,
                "confidence": crag_res.confidence_score,
                "answer": gen_res.answer[:90] + "...",
                "is_refusal": is_refusal,
                "citations_count": len(gen_res.citations),
                "passed": success
            })

            print(f"[{q_item['id']}] {status} | CRAG: {crag_res.action:<9} (conf: {crag_res.confidence_score:.3f}) | Q: \"{query[:45]}...\"")
            if not success:
                print(f"      Ans: {gen_res.answer}")

        pass_rate = round((passed / len(adv_queries)) * 100, 1)
        print(f"\nAdversarial Defense Pass Rate: {passed}/{len(adv_queries)} ({pass_rate}%)")
        return {"total_tests": len(adv_queries), "passed": passed, "pass_rate": pass_rate, "details": details}

    # -------------------------------------------------------------------------
    # TEST PILLAR 3: Needle-in-a-Haystack / Scaled Distractor Stress Test
    # -------------------------------------------------------------------------
    def run_needle_in_haystack_test(self, num_distractors: int = 100) -> Dict[str, Any]:
        print_sub_header(f"PILLAR 3: Needle-in-a-Haystack Stress Test ({num_distractors} Distractor Docs)")
        
        print(f"Generating and indexing {num_distractors} synthetic enterprise distractor documents...")
        distractor_docs = generate_synthetic_distractor_corpus(num_docs=num_distractors)
        
        # Build a noisy scaled index containing both real docs + 100 distractor docs
        all_real_docs = self.vault_manager.vaults["all"]["documents"]
        all_docs = all_real_docs + distractor_docs
        
        all_chunks: List[Chunk] = []
        for d in all_docs:
            all_chunks.extend(self.ingestion_pipe.process_document(d))

        noisy_index = HybridIndex()
        noisy_index.build_index(all_docs, all_chunks)
        noisy_retriever = HybridRetriever(index=noisy_index)

        print(f"Corpus scaled to: {len(all_docs)} documents, {len(all_chunks)} chunks.\n")

        # Test pinpoint precision for canonical facts in this crowded index
        needle_test_cases = [
            {"name": "Form HR-402 (Medical Leave)", "query": "What form is submitted for medical absences exceeding 3 days?", "needle_token": "HR-402"},
            {"name": "Rule SEC-881 (SMS 2FA Ban)", "query": "Which rule bans SMS-based 2FA and mandates FIDO2 keys?", "needle_token": "SEC-881"},
            {"name": "Form QPU-99 (Quantum Proc)", "query": "What form is required for quantum processor purchase orders?", "needle_token": "QPU-99"},
            {"name": "Tier-1 99.99% SLA & 15m RTO", "query": "What is the uptime SLA and database RTO for Tier-1 production?", "needle_token": "15 minutes"},
            {"name": "45°C Liquid Cooling", "query": "What is the liquid cooling thermal temperature ceiling for cluster deployments?", "needle_token": "45 degrees"}
        ]

        passed = 0
        details = []

        for tc in needle_test_cases:
            query = tc["query"]
            q_analysis = self.query_processor.analyze(query)
            cands = noisy_retriever.retrieve(query, overfetch_k=25, expanded_queries=q_analysis.expanded_queries)
            reranked = self.reranker.rerank(query, cands, top_k=4)

            top_chunk = reranked[0].chunk if reranked else None
            top_content = top_chunk.content if top_chunk else ""
            
            found_in_top1 = tc["needle_token"].lower() in top_content.lower()
            found_in_top4 = any(tc["needle_token"].lower() in c.chunk.content.lower() for c in reranked)

            success = found_in_top1 or found_in_top4
            if success:
                passed += 1

            status = "✅ PASS" if success else "❌ FAIL"
            details.append({
                "needle_name": tc["name"],
                "query": query,
                "found_in_top1": found_in_top1,
                "found_in_top4": found_in_top4,
                "top_doc": top_chunk.doc_title if top_chunk else "None",
                "top_rerank_score": reranked[0].rerank_score if reranked else 0.0
            })

            print(f"{status} | Needle: {tc['name']:<28} | Top-1 Doc: {top_chunk.doc_title[:30]:<30} | Score: {reranked[0].rerank_score:.3f}")

        pass_rate = round((passed / len(needle_test_cases)) * 100, 1)
        print(f"\nHaystack Needle Precision: {passed}/{len(needle_test_cases)} ({pass_rate}%)")
        return {"total_tests": len(needle_test_cases), "passed": passed, "pass_rate": pass_rate, "details": details}

    # -------------------------------------------------------------------------
    # TEST PILLAR 4: Noise & Typo Robustness Benchmark
    # -------------------------------------------------------------------------
    def run_noise_robustness_test(self) -> Dict[str, Any]:
        print_sub_header("PILLAR 4: Noise & Typo Robustness Benchmark")
        
        noise_queries = [q for q in HARD_BENCHMARK_QUERIES if q["category"] == "noise_typo_colloquial"]
        print(f"Testing {len(noise_queries)} corrupted, colloquial, and typo-laden queries...\n")

        passed = 0
        details = []

        for tc in noise_queries:
            query = tc["query"]
            vault_id = tc["vault_id"]
            vault = self.vault_manager.vaults.get(vault_id, self.vault_manager.vaults["all"])
            index: HybridIndex = vault["index"]
            retriever = HybridRetriever(index=index)

            q_analysis = self.query_processor.analyze(query)
            cands = retriever.retrieve(query, overfetch_k=15, expanded_queries=q_analysis.expanded_queries)
            reranked = self.reranker.rerank(query, cands, top_k=4)
            gen_res = self.generator.generate(query, reranked)

            all_tokens_found = all(tok.lower() in gen_res.answer.lower() for tok in tc["expected_tokens"])
            success = all_tokens_found and len(gen_res.citations) > 0
            if success:
                passed += 1

            status = "✅ PASS" if success else "❌ FAIL"
            details.append({
                "id": tc["id"],
                "query": query,
                "answer": gen_res.answer[:85] + "...",
                "all_tokens_found": all_tokens_found,
                "citations_count": len(gen_res.citations),
                "passed": success
            })

            print(f"[{tc['id']}] {status} | Q: \"{query[:55]}...\"")
            print(f"      Ans: {gen_res.answer[:85]}...")

        pass_rate = round((passed / len(noise_queries)) * 100, 1)
        print(f"\nNoise Robustness Pass Rate: {passed}/{len(noise_queries)} ({pass_rate}%)")
        return {"total_tests": len(noise_queries), "passed": passed, "pass_rate": pass_rate, "details": details}

    # -------------------------------------------------------------------------
    # TEST PILLAR 5: Concurrency & Latency Stress Profiling
    # -------------------------------------------------------------------------
    def run_concurrency_stress_test(self, num_queries: int = 50, concurrency_levels: List[int] = [1, 10, 25]) -> Dict[str, Any]:
        print_sub_header("PILLAR 5: Concurrency & Latency Stress Profiling")
        
        sample_queries = [
            ("What form is needed for medical absences exceeding 3 days?", "hr_benefits"),
            ("What is the RTO and RPO for Tier-1 databases?", "sre_infra"),
            ("What rule bans SMS 2FA and requires FIDO2?", "infosec_compliance"),
            ("What form is required for quantum processor purchases?", "procurement_quantum"),
            ("How many days of PTO can roll over?", "hr_benefits")
        ]

        def worker_query(q_tuple):
            query_text, vault_id = q_tuple
            vault = self.vault_manager.vaults[vault_id]
            index: HybridIndex = vault["index"]
            retriever = HybridRetriever(index=index)
            
            t0 = time.time()
            q_analysis = self.query_processor.analyze(query_text)
            cands = retriever.retrieve(query_text, overfetch_k=15, expanded_queries=q_analysis.expanded_queries)
            reranked = self.reranker.rerank(query_text, cands, top_k=4)
            crag_res = self.crag_evaluator.evaluate_retrieval_confidence(query_text, reranked)
            gen_res = self.generator.generate(query_text, reranked)
            triad = self.triad_evaluator.evaluate(query_text, gen_res.answer, reranked)
            lat = (time.time() - t0) * 1000
            return lat, len(gen_res.citations)

        load_results = {}

        for concurrency in concurrency_levels:
            work_items = [sample_queries[i % len(sample_queries)] for i in range(num_queries)]
            latencies = []
            citations = []
            errors = 0

            start_total = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(worker_query, item) for item in work_items]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        lat, num_cit = future.result()
                        latencies.append(lat)
                        citations.append(num_cit)
                    except Exception as e:
                        errors += 1

            total_sec = time.time() - start_total
            qps = round(num_queries / total_sec, 2)
            latencies.sort()

            p50 = round(statistics.median(latencies), 2)
            p90 = round(latencies[int(len(latencies) * 0.90)], 2)
            p95 = round(latencies[int(len(latencies) * 0.95)], 2)
            p99 = round(latencies[int(len(latencies) * 0.99)], 2)
            avg_lat = round(statistics.mean(latencies), 2)

            load_results[f"concurrency_{concurrency}"] = {
                "concurrency_workers": concurrency,
                "total_queries": num_queries,
                "duration_seconds": round(total_sec, 3),
                "throughput_qps": qps,
                "latency_p50_ms": p50,
                "latency_p90_ms": p90,
                "latency_p95_ms": p95,
                "latency_p99_ms": p99,
                "latency_avg_ms": avg_lat,
                "error_count": errors
            }

            print(f"Workers: {concurrency:<2} | QPS: {qps:>6.1f} | Avg: {avg_lat:>6.2f}ms | P50: {p50:>6.2f}ms | P95: {p95:>6.2f}ms | P99: {p99:>6.2f}ms | Errors: {errors}")

        return load_results

    # -------------------------------------------------------------------------
    # MASTER RUNNER & REPORT GENERATOR
    # -------------------------------------------------------------------------
    def run_all_benchmarks(self) -> Dict[str, Any]:
        print_banner("NexusRAG Enterprise 4.0 - Master Hard Benchmark Suite")
        start_time = time.time()

        self.results["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.results["platform"] = "NexusRAG Enterprise 4.0"
        
        # 1. Multi-Strategy IR Benchmark
        self.results["ir_ranking_benchmark"] = self.run_ir_ranking_benchmark()

        # 2. Adversarial & Hallucination Stress Test
        self.results["adversarial_stress_test"] = self.run_adversarial_stress_test()

        # 3. Needle in Haystack Scaled Test
        self.results["needle_in_haystack_test"] = self.run_needle_in_haystack_test(num_distractors=100)

        # 4. Noise & Typo Robustness Test
        self.results["noise_robustness_test"] = self.run_noise_robustness_test()

        # 5. Concurrency Load Test
        self.results["concurrency_stress_test"] = self.run_concurrency_stress_test(num_queries=60, concurrency_levels=[1, 10, 25])

        total_elapsed = round(time.time() - start_time, 2)
        self.results["total_benchmark_duration_seconds"] = total_elapsed

        # Save JSON Report
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_results.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2)

        print_banner(f"All Hard Benchmarks Completed in {total_elapsed}s -> Results saved to {out_path}")
        return self.results


if __name__ == "__main__":
    runner = RAGHardBenchmarkRunner()
    runner.run_all_benchmarks()
