"""Shared helpers for the evaluation scripts."""
import json
import os
import sys
from typing import Dict, Iterable, List

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(EVAL_DIR)
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")

QUERIES_PATH = os.path.join(EVAL_DIR, "queries.jsonl")
QRELS_PATH = os.path.join(EVAL_DIR, "qrels.jsonl")
RUNS_DIR = os.path.join(EVAL_DIR, "runs")
CACHE_DIR = os.path.join(EVAL_DIR, ".cache")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from retrieval import title_key  # noqa: E402  (re-exported for the eval scripts)


def read_jsonl(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: str, rows: Iterable[Dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_env() -> None:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BACKEND_DIR, ".env"))
