"""
LLM relevance judge. Each (query, paper) pair is judged on its own from the
title and abstract, with a fixed rubric and temperature 0.

The judge model (default gpt-4.1) is deliberately not the model the systems
under test use (gpt-4o by default). Labels are appended to qrels.jsonl and
never re-judged, so adding a new system only judges the papers it newly
retrieves (incremental pooling).
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from llm import structured_completion

DEFAULT_JUDGE_MODEL = "gpt-4.1"
ABSTRACT_CHARS = 2000

RUBRIC = """You are an expert research librarian evaluating results of an academic literature search.
Given a researcher's search request and one paper, rate how relevant the paper is to the request.

2 = highly relevant: the paper is directly about the core topic of the request; a researcher would want it in a short reading list on this topic.
1 = partially relevant: the paper covers part of the request, a closely related topic, or useful background, but is not a core paper for it.
0 = not relevant: a different topic, or it only shares some keywords.

Rules:
- Judge by the paper's content, not by its citation count, venue or authors.
- If the request states a publication period, a paper outside it gets at most 1.
- A survey that is directly about the request's topic can be highly relevant.
- If the abstract is missing, judge from the title alone."""


class Judgement(BaseModel):
    reason: str = Field(description="One sentence explaining the grade")
    grade: Literal[0, 1, 2] = Field(description="0 = not relevant, 1 = partially relevant, 2 = highly relevant")


def paper_prompt(query: str, doc: Dict) -> str:
    abstract = (doc.get("abstract") or "").strip()
    if len(abstract) > ABSTRACT_CHARS:
        abstract = abstract[:ABSTRACT_CHARS].rsplit(" ", 1)[0] + " ..."
    return (
        f"Search request: {query}\n\n"
        f"Paper title: {doc.get('title')}\n"
        f"Year: {doc.get('year') or 'unknown'}\n"
        f"Abstract: {abstract or '(not available)'}"
    )


def judge_one(client, model: str, query: str, doc: Dict) -> Judgement:
    return structured_completion(
        client, model,
        [{"role": "system", "content": RUBRIC}, {"role": "user", "content": paper_prompt(query, doc)}],
        Judgement,
        temperature=0,
    )


def judge_many(client, model: str, items: List[Dict], workers: int = 3) -> List[Optional[Judgement]]:
    """
    items: [{"query": ..., "doc": {...}}]. Returns one Judgement per item, or
    None when the call failed (the pair stays unjudged and is retried next run).
    Few workers and patient retries, so low tokens-per-minute limits are respected.
    """
    client = client.with_options(max_retries=10)

    def run(item):
        try:
            return judge_one(client, model, item["query"], item["doc"])
        except Exception as e:  # noqa: BLE001 - keep judging the rest
            print(f"  judge failed for '{item['doc'].get('title', '')[:60]}': {e}")
            return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run, items))
