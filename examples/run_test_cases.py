#!/usr/bin/env python3
"""
NexusRAG Enterprise 4.0 Test Suite Runner.
Tests:
1. Multi-Collection Vault Registry & Knowledge Graph
2. Agentic Query Intelligence & HyDE Expansion
3. SRE Knowledge Vault with RAG Triad Observability
4. Corrective RAG (CRAG) Self-Reflection
5. A/B Strategy Experimentation Arena
6. Policy Timeline & SLA Extraction
7. Cryptographic Compliance Audit Certification
8. Server-Sent Events (SSE) Token Streaming
"""

import requests

BASE_URL = "http://localhost:8000/api/v1"


def print_header(title):
    print("\n" + "=" * 80)
    print(f" {title} ")
    print("=" * 80)


def run_full_enterprise_tests():
    print_header("⚡ NexusRAG Enterprise 4.0 End-to-End Test Suite ⚡")

    health = requests.get(f"{BASE_URL}/health").json()
    print(f"Platform: {health['platform']} | Status: {health['status'].upper()}")
    print(f"Active Vault: {health['active_vault']['name']} (ID: {health['active_vault']['id']})")
    print(f"Features: CRAG={health['crag_reflection_active']}, SSE={health['sse_streaming_ready']}, Timelines={health['timeline_extractor_active']}")

    passed = 0

    # 1. Multi-Vault Registry
    print_header("[TC-01] Multi-Collection Vault Registry & Knowledge Graph")
    vaults = requests.get(f"{BASE_URL}/vaults").json()
    print(f"Discovered {len(vaults)} isolated enterprise vaults:")
    for v in vaults:
        print(f"  - {v['icon']} [{v['id']}] {v['name']} ({v['document_count']} docs, {v['chunk_count']} chunks)")

    graph_res = requests.get(f"{BASE_URL}/graph?vault_id=hr_benefits").json()
    print(f"Knowledge Graph (HR Vault): {len(graph_res['nodes'])} Nodes, {len(graph_res['links'])} Directed Links")
    if len(vaults) >= 4 and len(graph_res['nodes']) > 0:
        print("✅ TC-01 PASSED: Multi-Vault & Graph verified.")
        passed += 1

    # 2. Agentic Query Expansion & HyDE
    print_header("[TC-02] Agentic Query Intelligence (Intent + HyDE + Multi-Query)")
    q_payload = {"query": "What form must employees submit for medical absences over 3 days?"}
    expansion = requests.post(f"{BASE_URL}/query/expand", json=q_payload).json()
    print(f"Query: \"{expansion['original_query']}\"")
    print(f"Intent: {expansion['intent'].upper()} | Detected Entities: {expansion['detected_entities']}")
    print(f"HyDE Document: {expansion['hyde_document'][:80]}...")
    if expansion['intent'] == 'policy_compliance' and len(expansion['expanded_queries']) >= 3:
        print("✅ TC-02 PASSED: Agentic query expansion verified.")
        passed += 1

    # 3. SRE Vault Query & CRAG Self-Reflection
    print_header("[TC-03] SRE Knowledge Vault & CRAG Self-Reflection")
    sre_query = {
        "query": "What is the RTO and RPO for Tier-1 production database systems?",
        "vault_id": "sre_infra"
    }
    sre_res = requests.post(f"{BASE_URL}/query", json=sre_query).json()
    print(f"Answer: {sre_res['answer']}")
    print(f"CRAG Reflection Action: {sre_res['crag_reflection']['action']}")
    print(f"CRAG Reasoning: {sre_res['crag_reflection']['reasoning']}")
    print(f"Faithfulness: {int(sre_res['evaluation']['faithfulness']*100)}% | Risk: {sre_res['evaluation']['hallucination_risk']}")
    if "15 minutes" in sre_res['answer'] and sre_res['crag_reflection']['action'] in ["CORRECT", "AMBIGUOUS"]:
        print("✅ TC-03 PASSED: CRAG reflection & synthesis verified.")
        passed += 1

    # 4. A/B Strategy Arena Benchmark
    print_header("[TC-04] RAG Strategy A/B Experimentation Arena")
    arena_query = {
        "query": "What rule governs SMS 2FA prohibition and what encryption standard protects PHI?",
        "vault_id": "infosec_compliance"
    }
    arena_res = requests.post(f"{BASE_URL}/arena", json=arena_query).json()
    print(f"Strategy A ({arena_res['strategy_a']['strategy_name']}): Faithfulness={int(arena_res['strategy_a']['faithfulness']*100)}%, Latency={arena_res['strategy_a']['latency_ms']}ms")
    print(f"Strategy B ({arena_res['strategy_b']['strategy_name']}): Faithfulness={int(arena_res['strategy_b']['faithfulness']*100)}%, Latency={arena_res['strategy_b']['latency_ms']}ms")
    print(f"🏆 Winner: {arena_res['winner_strategy']} (+{arena_res['accuracy_delta_percent']}% delta)")
    if "SEC-881" in arena_res['strategy_b']['answer']:
        print("✅ TC-04 PASSED: A/B Strategy Arena verified.")
        passed += 1

    # 5. Policy Timeline & SLA Extraction
    print_header("[TC-05] Policy Timeline & SLA Benchmark Extraction")
    timelines = requests.get(f"{BASE_URL}/timeline").json()
    print(f"Extracted {len(timelines)} temporal deadlines & SLAs:")
    for ev in timelines[:4]:
        print(f"  - [{ev['urgency_level']}] {ev['timeframe']} -> {ev['doc_title']}: \"{ev['action_or_rule'][:70]}...\"")
    if len(timelines) >= 3:
        print("✅ TC-05 PASSED: Policy Timeline extraction verified.")
        passed += 1

    # 6. Cryptographic Compliance Audit Certification
    print_header("[TC-06] Cryptographic Compliance Audit Certification")
    cert = requests.get(f"{BASE_URL}/audit/export?query=What+form+is+required+for+PTO&vault_id=hr_benefits").json()
    print(f"Audit ID: {cert['audit_id']}")
    print(f"Query Hash: {cert['query_hash']}")
    print(f"Faithfulness Score: {int(cert['faithfulness_score']*100)}%")
    print(f"Cryptographic Signature: {cert['cryptographic_signature'][:32]}...")
    if cert['audit_id'].startswith("AUDIT-NEXUS-") and len(cert['cryptographic_signature']) == 64:
        print("✅ TC-06 PASSED: Cryptographic Audit Certification verified.")
        passed += 1

    # 7. Real-Time SSE Token Streaming
    print_header("[TC-07] Server-Sent Events (SSE) Token-by-Token Streaming")
    stream_payload = {"query": "What form is required for quantum processor purchase orders?", "vault_id": "procurement_quantum"}
    stream_resp = requests.post(f"{BASE_URL}/query/stream", json=stream_payload, stream=True)
    tokens = []
    for chunk in stream_resp.iter_lines():
        if chunk:
            line = chunk.decode('utf-8')
            if line.startswith("data: "):
                tok = line.replace("data: ", "")
                if tok != "[DONE]":
                    tokens.append(tok)
    streamed_text = "".join(tokens)
    print(f"Streamed Tokens Received: {len(tokens)}")
    print(f"Streamed Text: \"{streamed_text}\"")
    if "QPU-99" in streamed_text and len(tokens) >= 5:
        print("✅ TC-07 PASSED: Real-time SSE streaming verified.")
        passed += 1

    print_header(f"🏁 Summary: {passed}/7 Enterprise 4.0 Test Suites PASSED 🏁")


if __name__ == "__main__":
    run_full_enterprise_tests()
