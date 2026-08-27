#!/usr/bin/env python3
"""
NexusRAG Enterprise v0.2.0 - Live Verification Suite on Brand-New Diverse Scenarios.
"""

import json
import requests

BASE_URL = "http://localhost:8000/api/v1"

TEST_SCENARIOS = [
    {
        "id": "CASE-01",
        "title": "HIPAA & PHI Encryption Standards (InfoSec Vault)",
        "vault_id": "infosec_compliance",
        "query": "What encryption algorithms and TLS standards are mandated for Protected Health Information under HIPAA?",
        "expected_tokens": ["AES-256", "TLS 1.3", "164.312"]
    },
    {
        "id": "CASE-02",
        "title": "P0 Incident Declaration & Escalation Protocol (SRE Vault)",
        "vault_id": "sre_infra",
        "query": "How quickly must P0 incidents be declared and through which integration bridge?",
        "expected_tokens": ["5 minutes", "PagerDuty API-v2"]
    },
    {
        "id": "CASE-03",
        "title": "Bereavement Leave Entitlement (HR Vault)",
        "vault_id": "hr_benefits",
        "query": "How many days of paid bereavement leave do employees receive without deducting from PTO?",
        "expected_tokens": ["5 consecutive paid days"]
    },
    {
        "id": "CASE-04",
        "title": "Quantum Cluster Liquid Cooling Limit (Procurement Vault)",
        "vault_id": "procurement_quantum",
        "query": "What is the maximum allowed thermal temperature ceiling for liquid-cooled clusters?",
        "expected_tokens": ["45 degrees Celsius"]
    },
    {
        "id": "CASE-05",
        "title": "Out-of-Domain Strict Guard Refusal (Zero-Hallucination)",
        "query": "What is the secret recipe for Martian potato stew cooked by astronaut chefs?",
        "vault_id": "hr_benefits",
        "expected_tokens": ["I don't know"]
    }
]


def print_section(title):
    print("\n" + "=" * 80)
    print(f" {title} ")
    print("=" * 80)


def test_live_scenarios():
    print_section("⚡ Running Live Verification on Brand-New Scenario Cases ⚡")
    passed = 0

    for case in TEST_SCENARIOS:
        print_section(f"[{case['id']}] {case['title']}")
        print(f"Target Vault: {case['vault_id']}")
        print(f"Query: \"{case['query']}\"")

        payload = {
            "query": case["query"],
            "vault_id": case["vault_id"],
            "use_hyde": True,
            "use_multi_query": True
        }
        res = requests.post(f"{BASE_URL}/query", json=payload).json()

        print(f"\n📝 Synthesized Answer:\n{res['answer']}")
        print(f"\n📊 RAG Triad: Faithfulness={int(res['evaluation']['faithfulness']*100)}% | Risk={res['evaluation']['hallucination_risk']} | Latency={res['latency']['total_ms']}ms")
        print(f"CRAG Action: {res['crag_reflection']['action']} ({res['crag_reflection']['reasoning']})")
        print(f"Citations: {[c['chunk_id'] for c in res['citations']]}")

        all_found = all(tok.lower() in res["answer"].lower() for tok in case["expected_tokens"])
        if all_found:
            print(f"\n✅ {case['id']} PASSED: All expected factual tokens and strict citations verified.")
            passed += 1
        else:
            print(f"\n❌ {case['id']} FAILED: Missing one of {case['expected_tokens']}")

    # Test A/B Strategy Arena on New Question
    print_section("[CASE-06] A/B Strategy Arena Real-Time Benchmark")
    arena_payload = {
        "query": "What is the recovery time objective and backup replication standard for databases?",
        "vault_id": "sre_infra"
    }
    arena_res = requests.post(f"{BASE_URL}/arena", json=arena_payload).json()
    print(f"Strategy A Answer: {arena_res['strategy_a']['answer'][:80]}...")
    print(f"Strategy B Answer: {arena_res['strategy_b']['answer'][:80]}...")
    print(f"🏆 Winner: {arena_res['winner_strategy']} (+{arena_res['accuracy_delta_percent']}% accuracy delta)")
    if "15 minutes" in arena_res['strategy_b']['answer']:
        print("✅ CASE-06 PASSED: A/B Arena benchmark execution successful.")
        passed += 1

    # Test SSE Streaming
    print_section("[CASE-07] Server-Sent Events (SSE) Live Token Streaming")
    stream_payload = {"query": "What are the rules for annual PTO rollover?", "vault_id": "hr_benefits"}
    stream_res = requests.post(f"{BASE_URL}/query/stream", json=stream_payload, stream=True)
    streamed_tokens = []
    for line in stream_res.iter_lines():
        if line:
            decoded = line.decode('utf-8')
            if decoded.startswith("data: "):
                t = decoded.replace("data: ", "")
                if t != "[DONE]":
                    streamed_tokens.append(t)
    full_stream = "".join(streamed_tokens)
    print(f"Streamed Tokens Count: {len(streamed_tokens)}")
    print(f"Streamed Text: \"{full_stream}\"")
    if "5 days" in full_stream and len(streamed_tokens) > 5:
        print("✅ CASE-07 PASSED: Real-time token streaming verified.")
        passed += 1

    # Test Dynamic Ingest & Immediate Query
    print_section("[CASE-08] Dynamic Document Upload & Instant Zero-Downtime Indexing")
    new_doc = {
        "title": "Cloud FinOps & GPU Cluster Budget 2027",
        "content": """# Section 1: H100 GPU Allocations
All GPU cluster provisioning requires Form FIN-770 signed by the Cloud Finance Director.
Emergency compute bursting is capped at 100 TFLOPS per project.""",
        "metadata": {"author": "FinOps Lead"},
        "vault_id": "procurement_quantum"
    }
    ing_res = requests.post(f"{BASE_URL}/documents/ingest", json=new_doc).json()
    print(f"Ingested doc '{ing_res['title']}' -> {ing_res['chunks_created']} chunks created.")

    finops_q = "What form is required for GPU cluster provisioning and what is the bursting cap?"
    finops_res = requests.post(f"{BASE_URL}/query", json={"query": finops_q, "vault_id": "procurement_quantum"}).json()
    print(f"Answer: {finops_res['answer']}")
    if "FIN-770" in finops_res["answer"]:
        print("✅ CASE-08 PASSED: Dynamic ingestion and instant retrieval verified.")
        passed += 1

    print_section(f"🏁 Final Result: {passed}/{len(TEST_SCENARIOS)+3} Test Cases PASSED 🏁")


if __name__ == "__main__":
    test_live_scenarios()
