import math
from typing import List, Dict, Any, Set, Tuple


def calculate_hit_at_k(retrieved_ids: List[str], gold_ids: List[str], k: int = 3) -> float:
    """Returns 1.0 if at least one gold chunk is in top-k retrieved chunks, else 0.0."""
    if not gold_ids:
        return 1.0
    top_k = retrieved_ids[:k]
    gold_set = set(gold_ids)
    return 1.0 if any(cid in gold_set for cid in top_k) else 0.0


def calculate_recall_at_k(retrieved_ids: List[str], gold_ids: List[str], k: int = 3) -> float:
    """Calculates recall@k: proportion of gold chunks present in top-k."""
    if not gold_ids:
        return 1.0
    top_k = set(retrieved_ids[:k])
    gold_set = set(gold_ids)
    hits = len(top_k.intersection(gold_set))
    return hits / len(gold_set)


def calculate_precision_at_k(retrieved_ids: List[str], gold_ids: List[str], k: int = 3) -> float:
    """Calculates precision@k: proportion of top-k chunks that are relevant."""
    if k == 0:
        return 0.0
    if not gold_ids:
        return 1.0
    top_k = set(retrieved_ids[:k])
    gold_set = set(gold_ids)
    hits = len(top_k.intersection(gold_set))
    return hits / min(k, len(retrieved_ids)) if retrieved_ids else 0.0


def calculate_mrr(retrieved_ids: List[str], gold_ids: List[str]) -> float:
    """Calculates Mean Reciprocal Rank (MRR): 1 / rank of the first relevant chunk."""
    if not gold_ids:
        return 1.0
    gold_set = set(gold_ids)
    for rank, cid in enumerate(retrieved_ids, start=1):
        if cid in gold_set:
            return 1.0 / rank
    return 0.0


def calculate_ndcg_at_k(retrieved_ids: List[str], gold_ids: List[str], k: int = 5) -> float:
    """
    Calculates Normalized Discounted Cumulative Gain (NDCG@K) with binary relevance.
    DCG = sum_{i=1}^k (rel_i / log2(i + 1))
    IDCG = sum_{i=1}^{min(k, |gold|)} (1 / log2(i + 1))
    """
    if not gold_ids:
        return 1.0
    gold_set = set(gold_ids)
    top_k = retrieved_ids[:k]

    dcg = 0.0
    for i, cid in enumerate(top_k, start=1):
        rel = 1.0 if cid in gold_set else 0.0
        if rel > 0:
            dcg += rel / math.log2(i + 1)

    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(k, len(gold_set)) + 1))
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def calculate_citation_metrics(
    cited_ids: List[str],
    gold_ids: List[str]
) -> Dict[str, float]:
    """Evaluates citation precision, recall, and F1."""
    if not gold_ids:
        # If query has no gold sources (e.g. out of domain), 0 citations is perfect
        return {
            "citation_precision": 1.0 if not cited_ids else 0.0,
            "citation_recall": 1.0 if not cited_ids else 0.0,
            "citation_f1": 1.0 if not cited_ids else 0.0
        }

    if not cited_ids:
        return {
            "citation_precision": 0.0,
            "citation_recall": 0.0,
            "citation_f1": 0.0
        }

    cited_set = set(cited_ids)
    gold_set = set(gold_ids)

    true_positives = len(cited_set.intersection(gold_set))
    precision = true_positives / len(cited_set)
    recall = true_positives / len(gold_set)
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "citation_precision": round(precision, 4),
        "citation_recall": round(recall, 4),
        "citation_f1": round(f1, 4)
    }


def is_refusal_response(answer: str) -> bool:
    """Checks if the model correctly gave a refusal response without hallucination."""
    refusal_phrases = [
        "i don't know",
        "i do not know",
        "not found in the provided context",
        "no relevant document chunks",
        "does not contain sufficient information",
        "not present in the context",
        "cannot answer based on"
    ]
    ans_lower = answer.lower()
    return any(p in ans_lower for p in refusal_phrases)
