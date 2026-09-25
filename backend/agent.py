"""
Research agent: the LLM decides which literature tools to call (function
calling) and finishes with a structured, grounded answer (Structured Outputs).

Loop:
  1. Send the conversation + tool schemas to the model.
  2. If it returns tool calls, run them (in parallel), append each result as a
     role="tool" message with the matching tool_call_id, and go to 1.
  3. Otherwise its reply is the final AgentAnswer. On the last allowed step we
     set tool_choice="none" so the model has to answer with what it has.

The final answer may only cite papers/authors that tools actually returned;
anything else is dropped and reported in the trace.
"""
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional

from openai import APIError, OpenAI
from pydantic import BaseModel, Field, ValidationError

from llm import create_with_schema, parse_reply
from openalex_client import OpenAlexClient
from retrieval import Reranker
from tools import ToolExecutor, tool_result_json

logger = logging.getLogger("ResearchAgent")

SYSTEM_PROMPT = """You are a research assistant that finds academic literature using tools backed by OpenAlex.

How to work:
- Break the request into its key concepts and run focused searches of 2-6 key terms. Several narrow searches beat one long query.
- Apply filters the request implies: publication years, "highly cited", "recent".
- If the request is about researchers (who works on X, papers by Y), use search_authors and get_author_papers.
- Judge relevance from titles and abstracts. Use get_paper when an abstract is missing or truncated and the paper looks promising.
- If a tool returns an error, fix the arguments and try again.
- Stop searching once you have enough evidence, usually after 2-4 rounds of tool calls.

Final answer:
- Recommend only papers and authors that appeared in tool results, using their exact IDs. Never invent IDs.
- Rank papers by how directly they address the request, not by citation count alone.
- Each reason must say what the paper actually does, based on its title and abstract."""


class SelectedPaper(BaseModel):
    paper_id: str = Field(description="paper_id exactly as returned by a tool, e.g. 'W2741809807'")
    reason: str = Field(description="One or two sentences on why this paper matches the request")


class SelectedAuthor(BaseModel):
    author_id: str = Field(description="author_id exactly as returned by a tool, e.g. 'A5023888391'")
    reason: str = Field(description="Why this researcher is relevant to the request")


class AgentAnswer(BaseModel):
    """Final answer of the research agent"""
    summary: str = Field(description="2-4 sentences on what was found and how it answers the request")
    papers: List[SelectedPaper] = Field(description="Most relevant papers, best first; usually 5-10")
    authors: List[SelectedAuthor] = Field(description="Relevant researchers if the request is about people, otherwise empty")


class ResearchAgent:
    def __init__(
        self,
        llm_client: OpenAI,
        model: str,
        openalex_client: OpenAlexClient,
        format_paper: Callable[[Dict], Dict],
        max_steps: int = 6,
        max_parallel_tools: int = 4,
        reranker: Optional[Reranker] = None,
    ):
        """
        Args:
            llm_client: OpenAI (or OpenAI-compatible) client
            model: Chat model that supports tool calling
            openalex_client: Client the tools query
            format_paper: Turns a raw OpenAlex work into the API's publication dict
            max_steps: Maximum number of LLM calls; the last one must answer
            max_parallel_tools: Maximum tool calls run concurrently
            reranker: Optional reranker for relevance-sorted search_papers results
        """
        self.llm = llm_client
        self.model = model
        self.openalex_client = openalex_client
        self.format_paper = format_paper
        self.max_steps = max_steps
        self.max_parallel_tools = max_parallel_tools
        self.reranker = reranker

    def run(self, query: str, max_steps: Optional[int] = None) -> Dict:
        start = time.time()
        max_steps = max(2, min(max_steps or self.max_steps, 10))
        executor = ToolExecutor(self.openalex_client, reranker=self.reranker)
        messages: List[Dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        trace: List[Dict] = []
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "llm_calls": 0}

        def agent_meta(steps: int) -> Dict:
            return {"model": self.model, "steps": steps, "trace": trace, "usage": usage}

        answer: Optional[AgentAnswer] = None
        for step in range(1, max_steps + 1):
            is_last_step = step == max_steps
            try:
                response = create_with_schema(
                    self.llm, self.model, messages, AgentAnswer,
                    tools=executor.tool_schemas,
                    tool_choice="none" if is_last_step else "auto",
                )
            except APIError as e:
                logger.error(f"LLM call failed at step {step}: {e}")
                return self._error(query, f"LLM call failed: {e}", agent_meta(step), start)

            usage["llm_calls"] += 1
            if response.usage:
                usage["prompt_tokens"] += response.usage.prompt_tokens
                usage["completion_tokens"] += response.usage.completion_tokens

            message = response.choices[0].message
            if message.tool_calls and not is_last_step:
                messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {"id": c.id, "type": "function",
                         "function": {"name": c.function.name, "arguments": c.function.arguments}}
                        for c in message.tool_calls
                    ],
                })
                # The API requires one role="tool" message per tool_call_id, in any order
                for call, result, duration in self._run_tool_calls(executor, message.tool_calls):
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": tool_result_json(result)})
                    trace.append(self._trace_entry(step, call, result, duration))
                continue

            try:
                answer = parse_reply(message, AgentAnswer)
            except (ValidationError, ValueError) as e:
                logger.error(f"Invalid final answer: {e}")
                return self._error(query, f"Model returned an invalid final answer: {e}", agent_meta(step), start)
            break

        return self._build_result(query, answer, executor, agent_meta(step), start)

    # -- helpers -------------------------------------------------------------

    def _run_tool_calls(self, executor: ToolExecutor, calls) -> List:
        """Run a turn's tool calls concurrently; returns (call, result, duration_ms) in call order."""
        def run_one(call):
            t = time.time()
            result = executor.execute(call.function.name, call.function.arguments)
            return call, result, int((time.time() - t) * 1000)

        if len(calls) == 1:
            return [run_one(calls[0])]
        with ThreadPoolExecutor(max_workers=min(len(calls), self.max_parallel_tools)) as pool:
            return list(pool.map(run_one, calls))

    @staticmethod
    def _trace_entry(step: int, call, result: Dict, duration_ms: int) -> Dict:
        try:
            arguments = json.loads(call.function.arguments)
        except (json.JSONDecodeError, TypeError):
            arguments = call.function.arguments
        if "error" in result:
            summary = f"error: {result['error']}"
        elif "papers" in result:
            summary = f"{len(result['papers'])} papers"
        elif "paper_id" in result:  # get_paper (its details also carry an 'authors' list)
            summary = result.get("title") or result["paper_id"]
        elif "authors" in result:
            summary = f"{len(result['authors'])} authors"
        else:
            summary = "ok"
        return {"step": step, "tool": call.function.name, "arguments": arguments,
                "result": summary, "duration_ms": duration_ms}

    def _build_result(self, query: str, answer: AgentAnswer, executor: ToolExecutor,
                      agent: Dict, start: float) -> Dict:
        # Grounding: keep only IDs the tools actually returned
        dropped: List[str] = []
        results, seen = [], set()
        for paper in answer.papers:
            paper_id = paper.paper_id.strip().replace("https://openalex.org/", "")
            if paper_id in seen:
                continue
            if paper_id not in executor.seen_papers:
                dropped.append(paper_id)
                continue
            seen.add(paper_id)
            publication = self.format_paper(executor.seen_papers[paper_id])
            publication["agent_reason"] = paper.reason
            results.append(publication)

        # Preserve the agent's ranking for clients that sort by relevance_score
        for rank, publication in enumerate(results):
            publication["relevance_score"] = round(1 - rank / max(len(results), 1), 3)

        authors = []
        for author in answer.authors:
            author_id = author.author_id.strip().replace("https://openalex.org/", "")
            if author_id in executor.seen_authors:
                authors.append({**executor.seen_authors[author_id], "reason": author.reason})
            else:
                dropped.append(author_id)

        if dropped:
            logger.warning(f"Dropped IDs not returned by any tool: {dropped}")
        agent["dropped_ids"] = dropped
        return {
            "status": "success",
            "original_query": query,
            "summary": answer.summary,
            "results": results,
            "authors": authors,
            "agent": agent,
            "metadata": {
                "total_results": len(results),
                "processing_time": round(time.time() - start, 2),
            },
        }

    @staticmethod
    def _error(query: str, message: str, agent: Dict, start: float) -> Dict:
        return {
            "status": "error",
            "message": message,
            "http_status": 502,
            "original_query": query,
            "results": [],
            "agent": agent,
            "metadata": {"total_results": 0, "processing_time": round(time.time() - start, 2)},
        }
