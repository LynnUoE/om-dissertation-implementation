import json

import pytest
from mcp import Client

from mcp_server import create_server
from tools import GetAuthorPapers, GetPaper, SearchAuthors, SearchPapers

from conftest import FakeOpenAlex

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def openalex():
    return FakeOpenAlex()


@pytest.fixture
async def client(openalex):
    async with Client(create_server(openalex)) as c:
        yield c


async def test_tools_mirror_the_function_calling_schemas(client):
    tools = {t.name: t for t in (await client.list_tools()).tools}
    expected = {"search_papers": SearchPapers, "get_paper": GetPaper,
                "search_authors": SearchAuthors, "get_author_papers": GetAuthorPapers}
    assert set(tools) == set(expected)
    for name, model in expected.items():
        tool = tools[name]
        # Same parameters and descriptions as the agent's tools, so the two can't drift apart
        assert set(tool.input_schema["properties"]) == set(model.model_fields)
        assert tool.description == model.__doc__
        for field, info in model.model_fields.items():
            assert tool.input_schema["properties"][field]["description"] == info.description
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False


async def test_only_query_is_required_for_search(client):
    tools = {t.name: t for t in (await client.list_tools()).tools}
    assert tools["search_papers"].input_schema["required"] == ["query"]


async def test_search_papers_uses_defaults(client, openalex):
    result = await client.call_tool("search_papers", {"query": "graph neural networks"})
    assert result.is_error is False
    payload = json.loads(result.content[0].text)
    assert [p["paper_id"] for p in payload["papers"]] == ["W1", "W2", "W3"]
    assert payload["total_matches"] == 3
    assert openalex.calls[0]["per_page"] == 10 and openalex.calls[0]["sort"] == "relevance_score:desc"


async def test_tool_errors_come_back_as_is_error_results(client, openalex):
    result = await client.call_tool("search_papers", {"query": "x", "from_year": 2024, "to_year": 2020})
    assert result.is_error is True
    assert "from_year (2024) is after to_year (2020)" in result.content[0].text
    assert openalex.calls == []

    result = await client.call_tool("get_paper", {"paper_id": "W999"})
    assert result.is_error is True and "No paper found" in result.content[0].text


async def test_schema_violations_are_rejected_before_the_tool_runs(client, openalex):
    result = await client.call_tool("search_papers", {"query": "x", "sort": "newest"})
    assert result.is_error is True and "sort" in result.content[0].text
    assert openalex.calls == []


async def test_author_tools(client, openalex):
    authors = json.loads((await client.call_tool("search_authors", {"name": "Ada"})).content[0].text)
    assert authors["authors"][0]["author_id"] == "A1"
    await client.call_tool("get_author_papers", {"author_id": "A1"})
    assert openalex.calls[-1]["filter_string"] == "author.id:A1"
    assert openalex.calls[-1]["sort"] == "cited_by_count:desc"


async def test_literature_review_prompt(client):
    assert [p.name for p in (await client.list_prompts()).prompts] == ["literature_review"]
    prompt = await client.get_prompt("literature_review", {"topic": "protein folding"})
    assert "protein folding" in prompt.messages[0].content.text
