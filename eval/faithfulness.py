"""
Are the agent's reasons faithful to the papers? For every recommended paper
with a saved reason, an LLM judge compares the reason with the paper's title
and abstract:

  supported            every claim about the paper is stated or directly implied
  partially_supported  the main claim holds, but some detail isn't in the abstract
  unsupported          a key claim is missing from or contradicts the abstract

Papers without an abstract, or with only a one-line teaser (OpenAlex has
some), can't be checked and are counted separately.

    python eval/faithfulness.py --systems agent-v2.run2 agent-v2@gpt-4o-mini.run2

Verdicts are saved in faithfulness.jsonl and never re-judged; the summary is
written to faithfulness.md.
"""
import argparse
import json
import os
from collections import Counter
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from common import CACHE_DIR, EVAL_DIR, QUERIES_PATH, RUNS_DIR, load_env, read_jsonl

VERDICTS_PATH = os.path.join(EVAL_DIR, "faithfulness.jsonl")
REPORT_PATH = os.path.join(EVAL_DIR, "faithfulness.md")
LEVELS = ("supported", "partially_supported", "unsupported")
MIN_ABSTRACT_CHARS = 100  # Shorter "abstracts" are teasers like "Addressing fake news requires a multidisciplinary effort"

RUBRIC = """You check whether a research assistant's explanation of why it recommended a paper is faithful to that paper.
You get the user's search request, the paper's title and abstract, and the assistant's reason.

Judge only the claims the reason makes about the paper (what it studies, proposes, finds or uses), against the title and abstract:
- supported: every claim about the paper is stated in or directly implied by the title or abstract.
- partially_supported: the main claim holds, but the reason adds a detail the abstract doesn't mention or overstates something.
- unsupported: a key claim is not in the abstract or contradicts it, e.g. it says the paper uses a method or covers a topic it doesn't.

Whether the paper fits the request is not your concern, only whether the description of the paper is accurate."""


class Verdict(BaseModel):
    explanation: str = Field(description="One sentence naming the claim that decided the verdict")
    verdict: Literal["supported", "partially_supported", "unsupported"]


def prompt(query: str, doc: Dict, reason: str) -> str:
    abstract = (doc.get("abstract") or "").strip()[:3000]
    return (f"Search request: {query}\n\nPaper title: {doc.get('title')}\nAbstract: {abstract}\n\n"
            f"Assistant's reason for recommending it: {reason}")


def summarize(verdicts: List[Dict], no_abstract: int) -> Dict:
    """Share of each verdict among checkable reasons, plus counts."""
    counts = Counter(v["verdict"] for v in verdicts)
    n = sum(counts.values())
    return {"checked": n, "no_abstract": no_abstract,
            **{level: (counts[level] / n if n else None) for level in LEVELS}}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--systems", nargs="+", required=True)
    parser.add_argument("--judge-model", default="gpt-4.1")
    args = parser.parse_args()

    queries = {q["id"]: q["query"] for q in read_jsonl(QUERIES_PATH)}
    docs = json.load(open(os.path.join(CACHE_DIR, "docs.json")))
    done = {(v["system"], v["qid"], v["key"]): v for v in read_jsonl(VERDICTS_PATH)}

    todo, checkable, no_abstract = [], set(), Counter()
    for system in args.systems:
        for run in read_jsonl(os.path.join(RUNS_DIR, f"{system}.jsonl")):
            for r in run["results"]:
                if not r.get("reason"):
                    continue
                doc = docs.get(r["key"], {})
                if len((doc.get("abstract") or "").strip()) < MIN_ABSTRACT_CHARS:
                    no_abstract[system] += 1
                    continue
                checkable.add((system, run["qid"], r["key"]))
                if (system, run["qid"], r["key"]) not in done:
                    todo.append({"system": system, "qid": run["qid"], "key": r["key"], "reason": r["reason"],
                                 "doc": doc})

    if todo:
        load_env()
        from api_server import Config
        from judge import judge_many  # Reuses the throttled, retrying worker pool
        from llm import create_llm_client, structured_completion

        def check(c, model, item):
            return structured_completion(
                c, model, [{"role": "system", "content": RUBRIC},
                           {"role": "user", "content": prompt(queries[item["qid"]], item["doc"], item["reason"])}],
                Verdict, temperature=0)

        client = create_llm_client(Config.LLM_API_KEY, Config.LLM_BASE_URL)
        print(f"Checking {len(todo)} reasons with {args.judge_model} ...")
        results = judge_many(client, args.judge_model, todo, judge_fn=check)
        with open(VERDICTS_PATH, "a", encoding="utf-8") as f:
            for t, v in zip(todo, results):
                if v is None:
                    continue
                row = {"system": t["system"], "qid": t["qid"], "key": t["key"], "title": t["doc"].get("title"),
                       "reason": t["reason"], "verdict": v.verdict, "explanation": v.explanation,
                       "judge": args.judge_model}
                done[(t["system"], t["qid"], t["key"])] = row
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    lines = ["# Agent reason faithfulness", "",
             "Share of the agent's reasons that the paper's title and abstract support (see `faithfulness.py`).", "",
             "| System | Reasons checked | Supported | Partially supported | Unsupported | No usable abstract (not checked) |",
             "|---|---|---|---|---|---|"]
    done = {k: v for k, v in done.items() if k in checkable}  # Ignore verdicts on papers no longer checkable
    for system in args.systems:
        s = summarize([v for v in done.values() if v["system"] == system], no_abstract[system])
        pct = lambda x: "–" if x is None else f"{x:.0%}"
        lines.append(f"| {system} | {s['checked']} | {pct(s['supported'])} | {pct(s['partially_supported'])} "
                     f"| {pct(s['unsupported'])} | {s['no_abstract']} |")
    unsupported = [v for v in done.values() if v["system"] in args.systems and v["verdict"] == "unsupported"]
    if unsupported:
        lines += ["", "## Unsupported reasons", ""]
        for v in sorted(unsupported, key=lambda v: (v["system"], v["qid"])):
            lines.append(f"- **{v['system']}**, {v['qid']}, *{v['title']}*: \"{v['reason']}\" — {v['explanation']}")
    report = "\n".join(lines) + "\n"
    print("\n" + report)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)


if __name__ == "__main__":
    main()
