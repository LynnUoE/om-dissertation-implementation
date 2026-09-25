"""
Ranking metrics over graded relevance labels (0 = not, 1 = partially, 2 = highly relevant).

A ranked list is a list of title keys. Duplicate keys count once (at their
first position); later copies earn nothing, as in standard IR evaluation.
"""
import math
import random
from typing import Dict, List, Optional, Sequence


def dedupe(ranking: Sequence[str]) -> List[Optional[str]]:
    """Replace repeated keys with None so they keep their position but earn no gain."""
    seen, out = set(), []
    for key in ranking:
        out.append(None if key in seen else key)
        seen.add(key)
    return out


def ndcg_at_k(ranking: Sequence[str], grades: Dict[str, int], k: int = 10) -> float:
    """nDCG@k with exponential gain 2^grade - 1; the ideal ranking uses every labelled document."""
    def dcg(gs: Sequence[int]) -> float:
        return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gs[:k]))

    gains = [grades.get(key, 0) if key else 0 for key in dedupe(ranking)]
    ideal = dcg(sorted(grades.values(), reverse=True))
    return dcg(gains) / ideal if ideal else 0.0


def precision_at_k(ranking: Sequence[str], grades: Dict[str, int], k: int = 10, min_grade: int = 1) -> float:
    """Share of the top k slots holding a relevant document; missing slots count as misses."""
    hits = sum(1 for key in dedupe(ranking)[:k] if key and grades.get(key, 0) >= min_grade)
    return hits / k


def recall_at_k(ranking: Sequence[str], grades: Dict[str, int], k: int = 20, min_grade: int = 2) -> Optional[float]:
    """Share of all labelled documents with grade >= min_grade found in the top k (None if there are none)."""
    relevant = {key for key, g in grades.items() if g >= min_grade}
    if not relevant:
        return None
    return len(relevant & set(ranking[:k])) / len(relevant)


def canonical_recall_at_k(ranking: Sequence[str], canonical: List[Dict], k: int = 20) -> float:
    """Share of the hand-picked canonical papers in the top k (each may have several title keys)."""
    top = set(ranking[:k])
    return sum(1 for paper in canonical if top & set(paper["keys"])) / len(canonical)


def mean(values) -> Optional[float]:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def median(values) -> Optional[float]:
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2


def paired_randomization_test(a: Sequence[float], b: Sequence[float], trials: int = 10000, seed: int = 0) -> float:
    """
    Two-sided p-value for the mean per-query difference between systems a and b:
    randomly swap each query's pair of scores and count how often the mean
    difference is at least as large as the observed one.
    """
    diffs = [x - y for x, y in zip(a, b)]
    observed = abs(sum(diffs))
    rng = random.Random(seed)
    extreme = sum(
        1 for _ in range(trials)
        if abs(sum(d if rng.random() < 0.5 else -d for d in diffs)) >= observed - 1e-12
    )
    return (extreme + 1) / (trials + 1)
