"""
Look up each query's canonical papers in OpenAlex and record their work IDs.

The canonical lists in queries.jsonl are hand-picked by title. This script
finds every OpenAlex work with that exact (normalized) title, so duplicates
such as an arXiv preprint and the conference version are all recorded.

    python eval/resolve_canonical.py
"""
import os
import re

from common import QUERIES_PATH, load_env, read_jsonl, title_key, write_jsonl
from openalex_client import create_client


def find_by_title(client, title: str) -> list:
    # Filter values can't contain commas or colons; the exact title check happens below
    words = re.sub(r"[^\w\s-]", " ", title)
    for kwargs in ({"query": "", "filter_string": f"title.search:{words}"}, {"query": words}):
        response = client.search_works(per_page=25, sort="cited_by_count:desc", **kwargs)
        if response.error:
            raise RuntimeError(f"OpenAlex error for '{title}': {response.error}")
        matches = [w for w in response.data.get("results", []) if title_key(w.get("title")) == title_key(title)]
        if matches:
            return matches
    return []


def resolve(client, item: dict) -> dict:
    """
    item: {"title": ...} or, when OpenAlex stores the paper under a wrong
    title, {"title": ..., "doi": ...}. "keys" holds the normalized titles as
    OpenAlex has them, which is what search results are matched against.
    """
    if item.get("doi"):
        response = client.get_work(item["doi"])
        if response.error:
            raise RuntimeError(f"OpenAlex error for DOI {item['doi']}: {response.error}")
        matches = [response.data]
    else:
        matches = find_by_title(client, item["title"])
    return {
        **{k: item[k] for k in ("title", "doi") if k in item},
        "ids": [w["id"].replace("https://openalex.org/", "") for w in matches],
        "keys": sorted({title_key(w.get("title")) for w in matches}),
        "year": min((w.get("publication_year") for w in matches), default=None),
        "citations": max((w.get("cited_by_count", 0) for w in matches), default=0),
    }


def main():
    load_env()
    client = create_client(os.getenv("RESEARCHER_EMAIL", "research@example.com"), os.getenv("OPENALEX_API_KEY"))
    client.logger.disabled = True
    queries = read_jsonl(QUERIES_PATH)
    missing = []
    for q in queries:
        resolved = []
        for item in q["canonical"]:
            entry = resolve(client, item if isinstance(item, dict) else {"title": item})
            if not entry["ids"]:
                missing.append((q["id"], entry["title"]))
            resolved.append(entry)
        q["canonical"] = resolved
        print(f"{q['id']}: " + ", ".join(f"{len(c['ids'])}" for c in resolved))
    write_jsonl(QUERIES_PATH, queries)
    if missing:
        print("\nNot found in OpenAlex (fix the title or drop it):")
        for qid, title in missing:
            print(f"  {qid}: {title}")


if __name__ == "__main__":
    main()
