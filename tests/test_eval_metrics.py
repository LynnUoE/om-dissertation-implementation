import math

import pytest

from metrics import (canonical_recall_at_k, ndcg_at_k, paired_randomization_test, precision_at_k,
                     recall_at_k)

GRADES = {"a": 2, "b": 1, "c": 0, "d": 2}


def test_ndcg_perfect_and_graded():
    assert ndcg_at_k(["a", "d", "b"], GRADES) == pytest.approx(1.0)
    ideal = 3 + 3 / math.log2(3) + 1 / 2
    assert ndcg_at_k(["b", "a"], GRADES) == pytest.approx((1 + 3 / math.log2(3)) / ideal)
    assert ndcg_at_k([], GRADES) == 0.0
    assert ndcg_at_k(["a"], {}) == 0.0


def test_duplicates_earn_nothing():
    assert ndcg_at_k(["a", "a"], GRADES) == ndcg_at_k(["a", "x"], GRADES)
    assert precision_at_k(["a", "a"], GRADES, k=2) == 0.5


def test_precision_counts_missing_slots_as_misses():
    assert precision_at_k(["a", "b", "c"], GRADES, k=10) == pytest.approx(0.2)
    assert precision_at_k(["a", "b", "c"], GRADES, k=10, min_grade=2) == pytest.approx(0.1)


def test_recall_uses_highly_relevant_labels():
    assert recall_at_k(["a", "b"], GRADES, k=20) == 0.5
    assert recall_at_k(["a"], {"b": 1}, k=20) is None


def test_canonical_recall_matches_any_title_variant():
    canonical = [{"keys": ["a", "a preprint"]}, {"keys": ["z"]}]
    assert canonical_recall_at_k(["x", "a preprint"], canonical) == 0.5


def test_randomization_test():
    assert paired_randomization_test([0.5] * 10, [0.5] * 10) == 1.0
    assert paired_randomization_test([0.9] * 12, [0.1] * 12) < 0.001
