"""
Retrieval evaluation: run each system on the query set, judge newly retrieved
papers with an LLM, and report ranking metrics.

    python eval/run_eval.py                          # all systems, judge, score
    python eval/run_eval.py --systems multi_query+bge-base agent
    python eval/run_eval.py --queries q01 q02        # a subset of queries
    python eval/run_eval.py --score-only             # recompute metrics from saved runs and labels

Runs are saved per system in eval/runs/ and a query is skipped if its run
already exists (use --force to redo it). The pipeline systems share one LLM
query analysis per query and the multi_query systems share one candidate
pool, both cached in eval/.cache/, so they differ only in the stage being
compared.
"""
import argparse
import json
import os
import time
from datetime import date
from typing import Dict, List, Optional

from common import (CACHE_DIR, QRELS_PATH, QUERIES_PATH, RUNS_DIR, load_env, read_jsonl, title_key,
                    write_jsonl)
from metrics import (canonical_recall_at_k, mean, median, ndcg_at_k, paired_randomization_test,
                     precision_at_k, recall_at_k)

TOP_K = 20  # Results kept per query
BASELINE = "single_query"

MINILM = "cross-encoder:cross-encoder/ms-marco-MiniLM-L-6-v2"
BGE_BASE = "cross-encoder:BAAI/bge-reranker-base"
BGE_M3 = "cross-encoder:BAAI/bge-reranker-v2-m3"
EMBEDDING = "embedding:text-embedding-3-small"
# (sort, searched field) pairs of the first recall version
RECALL_V1 = (("relevance_score:desc", "fulltext"), ("cited_by_count:desc", "fulltext"))

SYSTEMS: Dict[str, Dict] = {
    "single_query": {"kind": "pipeline", "strategy": "single_query",
                     "about": "Original pipeline: one long keyword query, term-overlap scoring"},
    # Recall v1: the citation-sorted searches match full text
    "multi_query_v1": {"kind": "pipeline", "recall": "v1", "reranker": "none",
                       "about": "Focused queries (citation-sorted searches on full text), RRF order, no reranker"},
    "multi_query_v1+embedding": {"kind": "pipeline", "recall": "v1", "reranker": EMBEDDING,
                                 "about": "Recall v1 + OpenAI text-embedding-3-small cosine rerank"},
    "multi_query_v1+minilm": {"kind": "pipeline", "recall": "v1", "reranker": MINILM,
                              "about": "Recall v1 + ms-marco-MiniLM-L-6-v2 cross-encoder (22M)"},
    "multi_query_v1+bge-base": {"kind": "pipeline", "recall": "v1", "reranker": BGE_BASE,
                                "about": "Recall v1 + bge-reranker-base cross-encoder (278M)"},
    "multi_query_v1+bge-m3": {"kind": "pipeline", "recall": "v1", "reranker": BGE_M3,
                              "about": "Recall v1 + bge-reranker-v2-m3 cross-encoder (568M)"},
    # Recall v2: the citation-sorted searches match titles and abstracts only
    "multi_query": {"kind": "pipeline", "reranker": "none",
                    "about": "Focused queries (citation-sorted searches on titles/abstracts), RRF order"},
    "multi_query+embedding": {"kind": "pipeline", "reranker": EMBEDDING,
                              "about": "Recall v2 + text-embedding-3-small"},
    "multi_query+minilm": {"kind": "pipeline", "reranker": MINILM, "about": "Recall v2 + MiniLM cross-encoder"},
    "multi_query+bge-base": {"kind": "pipeline", "reranker": BGE_BASE, "about": "Recall v2 + bge-reranker-base"},
    "multi_query+bge-m3": {"kind": "pipeline", "reranker": BGE_M3, "about": "Recall v2 + bge-reranker-v2-m3"},
    "multi_query+minilm+expand": {"kind": "pipeline", "reranker": MINILM, "expand": True,
                                  "about": "Recall v2 + MiniLM + citation expansion"},
    "multi_query+bge-m3+expand": {"kind": "pipeline", "reranker": BGE_M3, "expand": True,
                                  "about": "Recall v2 + bge-reranker-v2-m3 + citation expansion"},
    "multi_query+minilm+cite0.1": {"kind": "pipeline", "reranker": MINILM, "citation_weight": 0.1,
                                   "about": "Recall v2 + MiniLM, 10% citation prior in the final score"},
    "multi_query+minilm+cite0.2": {"kind": "pipeline", "reranker": MINILM, "citation_weight": 0.2,
                                   "about": "Recall v2 + MiniLM, 20% citation prior"},
    "multi_query+minilm+cite0.3": {"kind": "pipeline", "reranker": MINILM, "citation_weight": 0.3,
                                   "about": "Recall v2 + MiniLM, 30% citation prior"},
    "agent": {"kind": "agent", "about": "Function-calling agent (returns up to ~10 papers)"},
    "agent+rerank": {"kind": "agent", "reranker": MINILM,
                     "about": "Agent whose search_papers tool reranks with the MiniLM cross-encoder"},
}

WORK_FIELDS = ("id", "doi", "title", "publication_year", "publication_date", "cited_by_count", "type",
               "open_access", "abstract_inverted_index", "referenced_works", "_rrf")


# ---------------------------------------------------------------------------
# Running systems
# ---------------------------------------------------------------------------

class Runner:
    def __init__(self, force: bool = False):
        load_env()
        from agent import ResearchAgent
        from api_server import Config
        from literature_searcher import create_literature_searcher

        self.force = force
        self.searcher = create_literature_searcher(
            Config.LLM_API_KEY, Config.RESEARCHER_EMAIL, Config.OPENALEX_API_KEY,
            llm_model=Config.LLM_MODEL, llm_base_url=Config.LLM_BASE_URL)
        self.searcher.logger.disabled = True
        self.searcher.openalex_client.logger.disabled = True
        self._watch_openalex_errors()
        self.llm = self.searcher.query_processor.client
        self.model = Config.LLM_MODEL
        self.agent_cls, self.max_steps = ResearchAgent, Config.AGENT_MAX_STEPS
        self._rerankers = {}
        self.docs_path = os.path.join(CACHE_DIR, "docs.json")
        self.docs: Dict[str, Dict] = json.load(open(self.docs_path)) if os.path.exists(self.docs_path) else {}

    def _watch_openalex_errors(self) -> None:
        """
        Record every failed OpenAlex request. Recall and the agent carry on after
        a failed search, which would silently save a degraded run (for example
        when the daily request budget runs out), so runs with errors are discarded.
        """
        client = self.searcher.openalex_client
        search_works = client.search_works
        self.openalex_errors: List[str] = []

        def watched(*args, **kwargs):
            response = search_works(*args, **kwargs)
            if response.error:
                self.openalex_errors.append(response.error)
            return response
        client.search_works = watched

    def _check_openalex(self, qid: str) -> None:
        errors, self.openalex_errors[:] = list(self.openalex_errors), []
        if errors:
            raise RuntimeError(f"{qid}: {len(errors)} OpenAlex request(s) failed, not saving: {errors[0]}")

    def reranker(self, spec: Optional[str]):
        from retrieval import create_reranker
        if spec not in self._rerankers:
            reranker = create_reranker(spec, llm_client=self.llm)
            if reranker is not None:
                reranker.score("warm up", ["load the model before timing"])
            self._rerankers[spec] = reranker
        return self._rerankers[spec]

    # -- cached shared stages ------------------------------------------------

    def _cached(self, kind: str, qid: str, compute):
        path = os.path.join(CACHE_DIR, kind, f"{qid}.json")
        if os.path.exists(path):
            return json.load(open(path))
        value = compute()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(value, open(path, "w"))
        return value

    def analysis(self, q: Dict) -> Dict:
        def compute():
            start = time.time()
            structured = self.searcher.query_processor.process_query(q["query"])
            if structured.get("error"):
                raise RuntimeError(f"{q['id']}: query analysis failed: {structured['error']}")
            return {"structured": structured, "seconds": time.time() - start}
        return self._cached("analysis", q["id"], compute)

    def candidates(self, q: Dict, structured: Dict, version: str) -> Dict:
        def compute():
            from retrieval import RECALL_SEARCHES
            self.searcher.recall_searches = RECALL_V1 if version == "v1" else RECALL_SEARCHES
            start = time.time()
            from_year, to_year = self.searcher.resolve_year_range(structured)
            works = self.searcher.retrieve_candidates(structured, from_year, to_year)
            self._check_openalex(q["id"])
            return {"works": [{f: w.get(f) for f in WORK_FIELDS} for w in works],
                    "seconds": time.time() - start}
        return self._cached("candidates_v1" if version == "v1" else "candidates", q["id"], compute)

    # -- systems -------------------------------------------------------------

    def run_pipeline(self, config: Dict, q: Dict) -> Dict:
        analysis = self.analysis(q)
        structured = analysis["structured"]
        if config.get("strategy") == "single_query":
            start = time.time()
            from_year, to_year = self.searcher.resolve_year_range(structured)
            n, results = self.searcher._single_query_search(structured, TOP_K, from_year, to_year,
                                                            None, None, False)
            retrieval_s = time.time() - start
        else:
            pool = self.candidates(q, structured, config.get("recall", "v2"))
            self.searcher.reranker = self.reranker(config.get("reranker"))
            self.searcher.citation_weight = config.get("citation_weight", 0.0)
            self.searcher.citation_expansion = config.get("expand", False)
            from_year, to_year = self.searcher.resolve_year_range(structured)
            start = time.time()
            results = self.searcher.rank_candidates(q["query"], pool["works"], structured, TOP_K,
                                                    from_year=from_year, to_year=to_year)
            n, retrieval_s = len(pool["works"]), pool["seconds"] + time.time() - start
        papers = [{"title": r.title, "year": (r.publication_date or "")[:4], "abstract": r.abstract}
                  for r in results]
        return {"papers": papers, "latency_s": analysis["seconds"] + retrieval_s,
                "llm_calls": 1, "llm_tokens": None, "candidates": n}

    def run_agent(self, config: Dict, q: Dict) -> Dict:
        agent = self.agent_cls(self.llm, self.model, self.searcher.openalex_client,
                               self.searcher.format_publication, max_steps=self.max_steps,
                               reranker=self.reranker(config.get("reranker")))
        result = agent.run(q["query"])
        if result["status"] != "success":
            raise RuntimeError(f"{q['id']}: agent failed: {result.get('message')}")
        usage = result["agent"]["usage"]
        papers = [{"title": p["title"], "year": (p.get("publication_date") or "")[:4], "abstract": p.get("abstract")}
                  for p in result["results"]]
        return {"papers": papers, "latency_s": result["metadata"]["processing_time"],
                "llm_calls": usage["llm_calls"], "llm_tokens": usage["prompt_tokens"] + usage["completion_tokens"],
                "tool_calls": len(result["agent"]["trace"]), "dropped_ids": len(result["agent"]["dropped_ids"])}

    def run(self, system: str, queries: List[Dict]) -> None:
        config = SYSTEMS[system]
        path = os.path.join(RUNS_DIR, f"{system}.jsonl")
        rows = {r["qid"]: r for r in read_jsonl(path)}
        for q in queries:
            if q["id"] in rows and not self.force:
                continue
            self.openalex_errors.clear()
            out = (self.run_agent if config["kind"] == "agent" else self.run_pipeline)(config, q)
            self._check_openalex(q["id"])
            for p in out["papers"]:
                self.docs.setdefault(title_key(p["title"]), p)
            rows[q["id"]] = {
                "qid": q["id"],
                "results": [{"key": title_key(p["title"]), "title": p["title"]} for p in out.pop("papers")][:TOP_K],
                **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in out.items()},
            }
            print(f"  {system} {q['id']}: {len(rows[q['id']]['results'])} results in {out['latency_s']:.1f}s")
            os.makedirs(RUNS_DIR, exist_ok=True)
            write_jsonl(path, [rows[k] for k in sorted(rows)])
            self.save_docs()

    def save_docs(self) -> None:
        os.makedirs(CACHE_DIR, exist_ok=True)
        json.dump(self.docs, open(self.docs_path, "w"))

    # -- judging -------------------------------------------------------------

    def judge(self, queries: List[Dict], judge_model: str) -> None:
        from judge import judge_many
        from tools import compact_paper

        labelled = {(r["qid"], r["key"]) for r in read_jsonl(QRELS_PATH)}
        items = []
        for q in queries:
            pool = {}
            for system in SYSTEMS:
                for row in read_jsonl(os.path.join(RUNS_DIR, f"{system}.jsonl")):
                    if row["qid"] == q["id"]:
                        pool.update({r["key"]: r["title"] for r in row["results"]})
            for paper in q["canonical"]:  # Label canonical papers too (judge sanity check)
                key = paper["keys"][0]
                if key not in self.docs:
                    work = self.searcher.openalex_client.get_work(paper["ids"][0]).data
                    c = compact_paper(work, abstract_chars=None)
                    self.docs[key] = {"title": c["title"], "year": c["year"], "abstract": c["abstract"]}
                pool.setdefault(key, self.docs[key]["title"])
            items += [{"qid": q["id"], "key": key, "query": q["query"], "doc": self.docs[key]}
                      for key in pool if (q["id"], key) not in labelled]
        self.save_docs()
        if not items:
            print("Nothing new to judge.")
            return
        print(f"Judging {len(items)} new (query, paper) pairs with {judge_model} ...")
        labelled_now = 0
        for start in range(0, len(items), 50):  # Save as we go, so an interrupted run keeps its labels
            batch = items[start:start + 50]
            judgements = judge_many(self.llm, judge_model, batch)
            with open(QRELS_PATH, "a", encoding="utf-8") as f:
                for item, j in zip(batch, judgements):
                    if j is not None:
                        f.write(json.dumps({"qid": item["qid"], "key": item["key"], "title": item["doc"]["title"],
                                            "grade": j.grade, "reason": j.reason, "judge": judge_model},
                                           ensure_ascii=False) + "\n")
            labelled_now += sum(j is not None for j in judgements)
            print(f"  labelled {labelled_now}/{len(items)}")
        print(f"Labelled {labelled_now} pairs.")


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def fmt(value: Optional[float], digits: int = 3) -> str:
    return "–" if value is None else f"{value:.{digits}f}"


def score(queries: List[Dict], systems: List[str]) -> str:
    qrels: Dict[str, Dict[str, int]] = {}
    for r in read_jsonl(QRELS_PATH):
        qrels.setdefault(r["qid"], {})[r["key"]] = r["grade"]
    qids = [q["id"] for q in queries]
    canonical = {q["id"]: q["canonical"] for q in queries}

    per_query: Dict[str, Dict[str, Dict]] = {}
    rows = []
    for system in systems:
        runs = {r["qid"]: r for r in read_jsonl(os.path.join(RUNS_DIR, f"{system}.jsonl")) if r["qid"] in qids}
        if not runs:
            continue
        stats = {}
        unjudged = 0
        for qid, run in runs.items():
            ranking = [r["key"] for r in run["results"]]
            grades = qrels.get(qid, {})
            unjudged += sum(1 for k in ranking if k not in grades)
            stats[qid] = {
                "ndcg10": ndcg_at_k(ranking, grades, 10),
                "p10": precision_at_k(ranking, grades, 10),
                "r20": recall_at_k(ranking, grades, 20),
                "canon20": canonical_recall_at_k(ranking, canonical[qid], 20),
                "latency": run["latency_s"],
                "tokens": run.get("llm_tokens"),
                "calls": run.get("llm_calls"),
            }
        per_query[system] = stats
        rows.append((system, len(runs), unjudged, {m: mean(s[m] for s in stats.values())
                                                   for m in ("ndcg10", "p10", "r20", "canon20", "tokens", "calls")},
                     median(s["latency"] for s in stats.values())))

    n_labels = sum(len(v) for v in qrels.values())
    lines = [
        "# Retrieval evaluation results",
        "",
        f"Generated by `eval/run_eval.py` on {date.today().isoformat()}: {len(qids)} queries, "
        f"{n_labels} graded (query, paper) labels.",
        "",
        "| System | nDCG@10 | P@10 | Recall@20 | Canonical R@20 | Median latency (s) | LLM calls | LLM tokens | p (nDCG@10 vs baseline) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    base = per_query.get(BASELINE)
    for system, n, unjudged, m, lat in rows:
        p = "–"
        if base and system != BASELINE:
            common = [q for q in per_query[system] if q in base]
            p = fmt(paired_randomization_test([per_query[system][q]["ndcg10"] for q in common],
                                              [base[q]["ndcg10"] for q in common]), 4)
        tokens = "–" if m["tokens"] is None else f"{m['tokens']:,.0f}"
        name = system if n == len(qids) else f"{system} ({n} queries)"
        lines.append(f"| {name} | {fmt(m['ndcg10'])} | {fmt(m['p10'])} | {fmt(m['r20'])} | {fmt(m['canon20'])} "
                     f"| {fmt(lat, 1)} | {fmt(m['calls'], 1)} | {tokens} | {p} |")
        if unjudged:
            lines.append(f"<!-- {system}: {unjudged} unjudged results counted as not relevant -->")

    lines += ["", "Systems:", ""] + [f"- `{s}`: {SYSTEMS[s]['about']}" for s, *_ in rows]

    canon_grades = [qrels.get(q["id"], {}).get(p["keys"][0]) for q in queries for p in q["canonical"]]
    graded = [g for g in canon_grades if g is not None]
    if graded:
        lines += ["", f"Judge sanity check: of {len(graded)} hand-picked canonical papers, the judge graded "
                      f"{sum(g == 2 for g in graded)} as highly relevant, {sum(g == 1 for g in graded)} as "
                      f"partially relevant and {sum(g == 0 for g in graded)} as not relevant."]

    lines += ["", "## nDCG@10 per query", "", "| Query | " + " | ".join(per_query) + " |",
              "|---|" + "---|" * len(per_query)]
    text = {q["id"]: q["query"] for q in queries}
    for qid in qids:
        cells = [fmt(per_query[s][qid]["ndcg10"], 2) if qid in per_query[s] else "–" for s in per_query]
        lines.append(f"| {qid}: {text[qid][:60]} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--systems", nargs="+", choices=list(SYSTEMS), default=list(SYSTEMS))
    parser.add_argument("--queries", nargs="+", help="Query IDs to run (default: all)")
    parser.add_argument("--score-only", action="store_true", help="Only recompute metrics")
    parser.add_argument("--no-judge", action="store_true", help="Run systems but don't label new papers")
    parser.add_argument("--force", action="store_true", help="Re-run queries that already have runs")
    parser.add_argument("--judge-model", default=os.getenv("EVAL_JUDGE_MODEL", "gpt-4.1"))
    parser.add_argument("--output", default=os.path.join(os.path.dirname(QRELS_PATH), "results.md"))
    args = parser.parse_args()

    queries = read_jsonl(QUERIES_PATH)
    if args.queries:
        queries = [q for q in queries if q["id"] in set(args.queries)]

    if not args.score_only:
        runner = Runner(force=args.force)
        for system in args.systems:
            print(f"Running {system} ...")
            runner.run(system, queries)
        if not args.no_judge:
            runner.judge(queries, args.judge_model)

    report = score(queries, args.systems)
    print("\n" + report)
    if not args.queries:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
