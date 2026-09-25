import json

import pytest

from openalex_client import OpenAlexClient
from tools import MAX_LIMIT, ToolExecutor

from conftest import FakeOpenAlex, make_work


def search_args(**overrides):
    args = {"query": "graph neural networks", "from_year": None, "to_year": None,
            "min_citations": None, "sort": "relevance", "limit": 5}
    args.update(overrides)
    return json.dumps(args)


def test_tool_schemas_are_strict(fake_openalex):
    schemas = ToolExecutor(fake_openalex).tool_schemas
    assert [s["function"]["name"] for s in schemas] == [
        "search_papers", "get_paper", "search_authors", "get_author_papers"]
    for schema in schemas:
        params = schema["function"]["parameters"]
        assert schema["function"]["strict"] is True
        assert params["additionalProperties"] is False
        assert set(params["required"]) == set(params["properties"])  # strict mode: everything required


def test_search_papers_returns_compact_papers_and_remembers_them(fake_openalex):
    ex = ToolExecutor(fake_openalex)
    result = ex.execute("search_papers", search_args(sort="citations"))
    assert [p["paper_id"] for p in result["papers"]] == ["W1", "W2", "W3"]
    assert result["papers"][0]["abstract"] == "graph neural networks predict molecular properties"
    assert result["papers"][0]["venue"] == "Journal of Tests"
    assert set(ex.seen_papers) == {"W1", "W2", "W3"}
    assert fake_openalex.calls[0]["sort"] == "cited_by_count:desc"


def test_long_abstracts_are_truncated_in_search_results():
    long_abstract = " ".join(f"word{i}" for i in range(500))
    ex = ToolExecutor(FakeOpenAlex([make_work(1, abstract=long_abstract)]))
    paper = ex.execute("search_papers", search_args())["papers"][0]
    assert len(paper["abstract"]) <= 610 and paper["abstract"].endswith("...")


def test_limit_is_clamped(fake_openalex):
    ToolExecutor(fake_openalex).execute("search_papers", search_args(limit=500))
    assert fake_openalex.calls[0]["per_page"] == MAX_LIMIT


def test_invalid_json_arguments_return_error(fake_openalex):
    result = ToolExecutor(fake_openalex).execute("search_papers", "{not json")
    assert "Invalid arguments for search_papers" in result["error"]
    assert fake_openalex.calls == []


def test_missing_and_invalid_fields_are_listed(fake_openalex):
    result = ToolExecutor(fake_openalex).execute("search_papers", '{"query": "x", "sort": "newest"}')
    for field in ("from_year", "to_year", "min_citations", "limit", "sort"):
        assert field in result["error"]


def test_semantic_validation_rejects_bad_year_range(fake_openalex):
    result = ToolExecutor(fake_openalex).execute("search_papers", search_args(from_year=2024, to_year=2020))
    assert "from_year (2024) is after to_year (2020)" in result["error"]
    assert fake_openalex.calls == []  # never reached OpenAlex


def test_unknown_tool(fake_openalex):
    result = ToolExecutor(fake_openalex).execute("delete_database", "{}")
    assert "Unknown tool 'delete_database'" in result["error"]


def test_get_paper_validates_id_and_reports_not_found(fake_openalex):
    ex = ToolExecutor(fake_openalex)
    assert "must be an OpenAlex work ID" in ex.execute("get_paper", '{"paper_id": "hello"}')["error"]
    assert "No paper found" in ex.execute("get_paper", '{"paper_id": "W999"}')["error"]
    details = ex.execute("get_paper", '{"paper_id": "W2"}')
    assert details["paper_id"] == "W2" and "W2" in ex.seen_papers


def test_author_tools(fake_openalex):
    ex = ToolExecutor(fake_openalex)
    authors = ex.execute("search_authors", '{"name": "Ada Lovelace", "limit": 3}')["authors"]
    assert authors[0]["author_id"] == "A1" and authors[0]["h_index"] == 12
    assert "must be an OpenAlex author ID" in ex.execute(
        "get_author_papers", '{"author_id": "Ada", "sort": "citations", "limit": 3}')["error"]
    ex.execute("get_author_papers", '{"author_id": "A1", "sort": "recent", "limit": 3}')
    assert fake_openalex.calls[-1]["filter_string"] == "author.id:A1"


def test_min_citations_filter_means_at_least():
    client = OpenAlexClient("test@example.com")
    captured = {}
    client._make_request = lambda endpoint, params=None, method="GET": captured.update(params) or None
    client.search_works("x", min_citations=100)
    assert captured["filter"] == "cited_by_count:>99"


def test_duplicate_titles_are_collapsed():
    works = [make_work(1, title="SignalP 6.0"), make_work(2, title="signalp 6.0 "), make_work(3)]
    papers = ToolExecutor(FakeOpenAlex(works)).execute("search_papers", search_args())["papers"]
    assert [p["paper_id"] for p in papers] == ["W1", "W3"]


class FakeHTTPResponse:
    def __init__(self, status_code, headers=None, body=None):
        self.status_code, self.headers = status_code, headers or {}
        self.content = b"{}"
        self.text = "{}"
        self._body = body or {}

    def json(self):
        return self._body


def test_exhausted_daily_budget_fails_fast(monkeypatch):
    client = OpenAlexClient("test@example.com")
    client.logger.disabled = True
    responses = [FakeHTTPResponse(429, {"Retry-After": "17818"}, {"message": "Rate limit exceeded"})]
    client.session.request = lambda *a, **kw: responses.pop(0)
    monkeypatch.setattr("openalex_client.time.sleep", lambda s: pytest.fail(f"slept {s}s"))

    response = client.search_works("x")
    assert response.status_code == 429 and "resets in 4.9 hours" in response.error


def test_short_rate_limit_is_retried(monkeypatch):
    client = OpenAlexClient("test@example.com")
    client.logger.disabled = True
    responses = [FakeHTTPResponse(429, {"Retry-After": "2"}), FakeHTTPResponse(200, body={"results": []})]
    client.session.request = lambda *a, **kw: responses.pop(0)
    slept = []
    monkeypatch.setattr("openalex_client.time.sleep", slept.append)

    response = client.search_works("x")
    assert response.error is None and slept[0] == 2.0
