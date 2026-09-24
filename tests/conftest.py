"""
Test doubles for the LLM and OpenAlex, so tests run offline and deterministically.
"""
import json
from types import SimpleNamespace
from typing import Dict, List, Optional

import pytest

from openalex_client import OpenAlexResponse


def make_work(n: int, title: Optional[str] = None, abstract: str = "graph neural networks predict molecular properties") -> Dict:
    """A minimal raw OpenAlex work."""
    return {
        "id": f"https://openalex.org/W{n}",
        "doi": f"https://doi.org/10.1000/{n}",
        "title": title or f"Paper {n}",
        "publication_year": 2021,
        "publication_date": "2021-01-01",
        "type": "article",
        "cited_by_count": 100 + n,
        "authorships": [{"author": {"display_name": f"Author {n}"}}],
        "primary_location": {"source": {"display_name": "Journal of Tests", "type": "journal"}},
        "open_access": {"is_oa": True},
        "abstract_inverted_index": {w: [i] for i, w in enumerate(abstract.split())},
    }


class FakeOpenAlex:
    """Stands in for OpenAlexClient; records calls and returns canned works."""

    def __init__(self, works: Optional[List[Dict]] = None):
        self.works = works if works is not None else [make_work(1), make_work(2), make_work(3)]
        self.calls: List[Dict] = []

    def search_works(self, query="", **kwargs) -> OpenAlexResponse:
        self.calls.append({"method": "search_works", "query": query, **kwargs})
        return OpenAlexResponse(200, {"results": self.works}, meta={"count": len(self.works)})

    def get_work(self, work_id: str) -> OpenAlexResponse:
        self.calls.append({"method": "get_work", "work_id": work_id})
        for work in self.works:
            if work["id"].endswith(work_id):
                return OpenAlexResponse(200, work)
        return OpenAlexResponse(404, {}, error="HTTP 404")

    def search_authors(self, query: str, per_page: int = 10) -> OpenAlexResponse:
        self.calls.append({"method": "search_authors", "query": query, "per_page": per_page})
        author = {"id": "https://openalex.org/A1", "display_name": query, "works_count": 10,
                  "cited_by_count": 500, "summary_stats": {"h_index": 12},
                  "last_known_institutions": [{"display_name": "Test University"}], "topics": []}
        return OpenAlexResponse(200, {"results": [author]})


# -- fake chat completions ---------------------------------------------------

def tool_call(call_id: str, name: str, arguments) -> SimpleNamespace:
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments)
    return SimpleNamespace(id=call_id, type="function",
                           function=SimpleNamespace(name=name, arguments=arguments))


def completion(content: Optional[str] = None, tool_calls: Optional[List] = None) -> SimpleNamespace:
    message = SimpleNamespace(role="assistant", content=content, tool_calls=tool_calls, refusal=None)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
    )


def answer(papers: List[str], summary: str = "Found papers.", authors: Optional[List[str]] = None) -> SimpleNamespace:
    """A final AgentAnswer reply."""
    return completion(content=json.dumps({
        "summary": summary,
        "papers": [{"paper_id": p, "reason": f"{p} is relevant"} for p in papers],
        "authors": [{"author_id": a, "reason": "expert"} for a in (authors or [])],
    }))


class FakeLLM:
    """Stands in for an OpenAI client: replays scripted responses and records every request."""

    def __init__(self, responses: List):
        self.responses = list(responses)
        self.requests: List[Dict] = []
        self.base_url = "https://fake.test/v1"
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        # Snapshot messages: the agent keeps appending to the same list
        self.requests.append({**kwargs, "messages": json.loads(json.dumps(kwargs["messages"], default=str))})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def fake_openalex():
    return FakeOpenAlex()
