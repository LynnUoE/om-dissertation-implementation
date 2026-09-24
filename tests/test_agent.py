import httpx2 as httpx
import openai

from agent import ResearchAgent

from conftest import FakeLLM, answer, completion, tool_call

SEARCH = {"query": "gnn drug discovery", "from_year": None, "to_year": None,
          "min_citations": None, "sort": "relevance", "limit": 5}


def make_agent(llm, openalex, max_steps=6):
    return ResearchAgent(
        llm_client=llm, model="test-model", openalex_client=openalex,
        format_paper=lambda work: {"id": work["id"], "title": work["title"]},
        max_steps=max_steps,
    )


def test_tool_call_then_grounded_answer(fake_openalex):
    llm = FakeLLM([
        completion(tool_calls=[tool_call("call_1", "search_papers", SEARCH)]),
        answer(["W2", "W1", "W404"]),  # W404 was never returned by a tool
    ])
    result = make_agent(llm, fake_openalex).run("gnn for drug discovery")

    assert result["status"] == "success"
    assert [r["title"] for r in result["results"]] == ["Paper 2", "Paper 1"]  # agent's ranking kept
    assert result["results"][0]["agent_reason"] == "W2 is relevant"
    assert result["results"][0]["relevance_score"] > result["results"][1]["relevance_score"]
    assert result["agent"]["dropped_ids"] == ["W404"]

    # Second request carries the assistant tool call and the matching tool result
    messages = llm.requests[1]["messages"]
    assert messages[2]["role"] == "assistant"
    assert messages[2]["tool_calls"][0]["id"] == "call_1"
    assert messages[3] == {"role": "tool", "tool_call_id": "call_1", "content": messages[3]["content"]}
    assert '"paper_id": "W1"' in messages[3]["content"]

    # Structured Outputs requested on every call, tools offered with auto choice
    assert llm.requests[0]["response_format"]["type"] == "json_schema"
    assert llm.requests[0]["tool_choice"] == "auto"
    assert result["agent"]["usage"] == {"prompt_tokens": 200, "completion_tokens": 40, "llm_calls": 2}


def test_invalid_arguments_are_returned_to_the_model_which_retries(fake_openalex):
    llm = FakeLLM([
        completion(tool_calls=[tool_call("call_1", "search_papers", '{"query": "gnn"}')]),
        completion(tool_calls=[tool_call("call_2", "search_papers", SEARCH)]),
        answer(["W1"]),
    ])
    result = make_agent(llm, fake_openalex).run("gnn")

    first_tool_result = llm.requests[1]["messages"][3]
    assert first_tool_result["tool_call_id"] == "call_1"
    assert "Invalid arguments for search_papers" in first_tool_result["content"]
    trace = result["agent"]["trace"]
    assert trace[0]["result"].startswith("error: Invalid arguments")
    assert trace[1]["result"] == "3 papers"
    assert result["status"] == "success" and len(result["results"]) == 1


def test_parallel_tool_calls_all_get_results_in_order(fake_openalex):
    llm = FakeLLM([
        completion(tool_calls=[
            tool_call("call_a", "search_papers", SEARCH),
            tool_call("call_b", "search_authors", {"name": "Ada", "limit": 2}),
            tool_call("call_c", "get_paper", {"paper_id": "W3"}),
        ]),
        answer(["W3"], authors=["A1"]),
    ])
    result = make_agent(llm, fake_openalex).run("who works on gnn")

    tool_messages = [m for m in llm.requests[1]["messages"] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_messages] == ["call_a", "call_b", "call_c"]
    assert result["authors"][0]["name"] == "Ada" and result["authors"][0]["reason"] == "expert"
    assert {t["step"] for t in result["agent"]["trace"]} == {1}


def test_last_step_forces_an_answer(fake_openalex):
    keep_searching = completion(tool_calls=[tool_call("call_x", "search_papers", SEARCH)])
    llm = FakeLLM([keep_searching, keep_searching, answer(["W1"])])
    result = make_agent(llm, fake_openalex, max_steps=3).run("gnn")

    assert [r["tool_choice"] for r in llm.requests] == ["auto", "auto", "none"]
    assert result["status"] == "success" and result["agent"]["steps"] == 3


def test_llm_api_error_becomes_502(fake_openalex):
    request = httpx.Request("POST", "https://fake.test/v1/chat/completions")
    error = openai.APIConnectionError(request=request)
    result = make_agent(FakeLLM([error]), fake_openalex).run("gnn")
    assert result["status"] == "error" and result["http_status"] == 502
    assert "LLM call failed" in result["message"]


def test_invalid_final_answer_becomes_502(fake_openalex):
    result = make_agent(FakeLLM([completion(content='{"summary": "missing fields"}')]), fake_openalex).run("gnn")
    assert result["status"] == "error" and result["http_status"] == 502
    assert "invalid final answer" in result["message"]
