import json
from types import SimpleNamespace

import httpx2 as httpx
import openai
import pytest
from pydantic import BaseModel

import llm
from query_processor import QueryProcessor

from conftest import FakeLLM, completion


class Point(BaseModel):
    x: int
    y: int


def bad_request(message: str) -> openai.BadRequestError:
    response = httpx.Response(400, request=httpx.Request("POST", "https://fake.test/v1/chat/completions"))
    return openai.BadRequestError(message, response=response, body=None)


@pytest.fixture(autouse=True)
def reset_fallback_cache():
    llm._json_schema_unsupported.clear()


def test_structured_completion_sends_strict_schema():
    fake = FakeLLM([completion(content='{"x": 1, "y": 2}')])
    assert llm.structured_completion(fake, "m", [{"role": "user", "content": "hi"}], Point) == Point(x=1, y=2)
    fmt = fake.requests[0]["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True


def test_falls_back_to_json_mode_when_provider_rejects_schema():
    fake = FakeLLM([
        bad_request("response_format type json_schema is not supported by this model"),
        completion(content='```json\n{"x": 3, "y": 4}\n```'),
        completion(content='{"x": 5, "y": 6}'),
    ])
    messages = [{"role": "user", "content": "hi"}]
    assert llm.structured_completion(fake, "m", messages, Point) == Point(x=3, y=4)
    assert fake.requests[1]["response_format"] == {"type": "json_object"}
    assert "JSON Schema" in fake.requests[1]["messages"][-1]["content"]

    # Remembered: the next call skips straight to JSON mode
    llm.structured_completion(fake, "m", messages, Point)
    assert fake.requests[2]["response_format"] == {"type": "json_object"}


def test_unrelated_bad_request_is_not_swallowed():
    fake = FakeLLM([bad_request("maximum context length exceeded")])
    with pytest.raises(openai.BadRequestError):
        llm.structured_completion(fake, "m", [{"role": "user", "content": "hi"}], Point)


def test_refusal_raises():
    message = SimpleNamespace(content=None, refusal="I can't help with that")
    with pytest.raises(ValueError, match="refused"):
        llm.parse_reply(message, Point)


def make_processor(fake) -> QueryProcessor:
    processor = QueryProcessor(api_key="test", model="test-model")
    processor.client = fake
    return processor


def test_query_processor_single_structured_call():
    reply = {
        "research_areas": ["Computer Science"],
        "specific_topics": ["Graph Neural Networks"],
        "methodologies": ["Deep Learning"],
        "temporal_context": "current",
        "search_keywords": ["GNN"],
        "expanded_terms": [{"term": "Graph Neural Networks", "related_terms": ["GNNs", "gnns", "message passing"]}],
    }
    fake = FakeLLM([completion(content=json.dumps(reply))])
    result = make_processor(fake).process_query("  gnn   for drugs ")

    assert len(fake.requests) == 1  # analysis + expansion in one call
    assert fake.requests[0]["model"] == "test-model"
    assert result["research_areas"] == ["Computer Science"]
    assert result["expertise"] == ["Graph Neural Networks", "Deep Learning"]
    assert result["expanded_terms"] == {"Graph Neural Networks": ["GNNs", "message passing"]}  # deduped
    assert "temporal_context" not in result  # "current" is the default


def test_query_processor_reports_llm_errors():
    fake = FakeLLM([completion(content='{"research_areas": "not a list"}')])
    result = make_processor(fake).process_query("gnn")
    assert result["research_areas"] == [] and "error" in result
