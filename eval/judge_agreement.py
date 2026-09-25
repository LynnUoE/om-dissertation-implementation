"""
Can a cheaper model replace the relevance judge? Re-label every (query, paper)
pair in qrels.jsonl with another model, then compare against the reference
labels: per-label agreement, and whether the systems still rank the same.

    python eval/judge_agreement.py --model gpt-4.1-mini
    python eval/judge_agreement.py --model gpt-4.1-nano --limit 300   # a random sample

The alternative labels are cached in .cache/qrels-<model>.jsonl.
"""
import argparse
import json
import os
import random
from collections import Counter
from typing import Dict, List

from common import CACHE_DIR, QRELS_PATH, QUERIES_PATH, RUNS_DIR, load_env, read_jsonl
from metrics import mean, ndcg_at_k, recall_at_k


def weighted_kappa(a: List[int], b: List[int], k: int = 3) -> float:
    """Cohen's kappa with quadratic weights: disagreeing by 2 grades costs 4x disagreeing by 1."""
    n = len(a)
    observed = sum((x - y) ** 2 for x, y in zip(a, b)) / n
    pa, pb = Counter(a), Counter(b)
    expected = sum(pa[i] * pb[j] * (i - j) ** 2 for i in range(k) for j in range(k)) / (n * n)
    return 1 - observed / expected if expected else 1.0


def kendall_tau(x: List[float], y: List[float]) -> float:
    pairs = [(i, j) for i in range(len(x)) for j in range(i + 1, len(x))]
    score = sum((x[i] - x[j]) * (y[i] - y[j]) > 0 for i, j in pairs) - \
        sum((x[i] - x[j]) * (y[i] - y[j]) < 0 for i, j in pairs)
    return score / len(pairs) if pairs else 1.0


def system_scores(labels: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, float]]:
    scores = {}
    for path in sorted(os.listdir(RUNS_DIR)):
        runs = read_jsonl(os.path.join(RUNS_DIR, path))
        rankings = [([r["key"] for r in run["results"]], labels.get(run["qid"], {})) for run in runs]
        scores[path.removesuffix(".jsonl")] = {
            "ndcg10": mean(ndcg_at_k(rk, g, 10) for rk, g in rankings),
            "r20": mean(recall_at_k(rk, g, 20) for rk, g in rankings),
        }
    return scores


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True)
    parser.add_argument("--limit", type=int, help="Only re-label a random sample of this many pairs")
    args = parser.parse_args()

    reference = read_jsonl(QRELS_PATH)
    if args.limit:
        reference = random.Random(0).sample(reference, min(args.limit, len(reference)))
    cache_path = os.path.join(CACHE_DIR, f"qrels-{args.model}.jsonl")
    cached = {(r["qid"], r["key"]): r for r in read_jsonl(cache_path)}

    todo = [r for r in reference if (r["qid"], r["key"]) not in cached]
    if todo:
        load_env()
        from api_server import Config
        from judge import judge_many
        from llm import create_llm_client

        queries = {q["id"]: q["query"] for q in read_jsonl(QUERIES_PATH)}
        docs = json.load(open(os.path.join(CACHE_DIR, "docs.json")))
        client = create_llm_client(Config.LLM_API_KEY, Config.LLM_BASE_URL)
        print(f"Labelling {len(todo)} pairs with {args.model} ...")
        for start in range(0, len(todo), 100):
            batch = todo[start:start + 100]
            items = [{"query": queries[r["qid"]], "doc": docs[r["key"]]} for r in batch]
            with open(cache_path, "a", encoding="utf-8") as f:
                for r, j in zip(batch, judge_many(client, args.model, items, workers=6)):
                    if j is not None:
                        row = {"qid": r["qid"], "key": r["key"], "grade": j.grade, "reason": j.reason}
                        cached[(r["qid"], r["key"])] = row
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"  {min(start + 100, len(todo))}/{len(todo)}")

    pairs = [(r["grade"], cached[(r["qid"], r["key"])]["grade"]) for r in reference if (r["qid"], r["key"]) in cached]
    ref, alt = [p[0] for p in pairs], [p[1] for p in pairs]
    print(f"\n{args.model} vs {reference[0].get('judge', 'reference')} on {len(pairs)} labels")
    print(f"  exact agreement: {sum(x == y for x, y in pairs) / len(pairs):.1%}")
    print(f"  weighted kappa:  {weighted_kappa(ref, alt):.3f}")
    print("  confusion (rows = reference grade, columns = new grade):")
    for g in (0, 1, 2):
        print(f"    {g}: " + "  ".join(f"{sum(1 for x, y in pairs if x == g and y == h):5d}" for h in (0, 1, 2)))

    if not args.limit:  # System-level comparison needs every label
        def as_dict(rows):
            out: Dict[str, Dict[str, int]] = {}
            for r in rows:
                out.setdefault(r["qid"], {})[r["key"]] = r["grade"]
            return out
        a, b = system_scores(as_dict(read_jsonl(QRELS_PATH))), system_scores(as_dict(cached.values()))
        names = sorted(a)
        print(f"\n  {'system':32s} nDCG@10 ref / new    R@20 ref / new")
        for s in names:
            print(f"  {s:32s} {a[s]['ndcg10']:.3f} / {b[s]['ndcg10']:.3f}      {a[s]['r20']:.3f} / {b[s]['r20']:.3f}")
        for m in ("ndcg10", "r20"):
            print(f"  Kendall tau of system ranking by {m}: {kendall_tau([a[s][m] for s in names], [b[s][m] for s in names]):.3f}")


if __name__ == "__main__":
    main()
