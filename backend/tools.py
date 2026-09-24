"""
Literature search tools exposed to the LLM via function calling.

Each tool has a Pydantic parameter model (which generates the strict JSON
Schema sent to the model) and a method on ToolExecutor that runs it against
OpenAlex. Results are compact dicts sized for an LLM context window.

ToolExecutor is created per request: it remembers every paper and author it
returned, so the agent can check that its final answer only cites real
results and can hydrate them for the frontend.
"""
import json
import re
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type

import openai
from pydantic import BaseModel, Field, ValidationError

from openalex_client import OpenAlexClient, reconstruct_abstract

MAX_LIMIT = 25
ABSTRACT_CHARS = 600

PAPER_SORTS = {
    "relevance": "relevance_score:desc",
    "citations": "cited_by_count:desc",
    "recent": "publication_date:desc",
}

_WORK_ID = re.compile(r"^(https://openalex\.org/)?W\d+$")
_AUTHOR_ID = re.compile(r"^(https://openalex\.org/)?A\d+$")


# ---------------------------------------------------------------------------
# Tool parameter schemas (docstrings become the tool descriptions)
# ---------------------------------------------------------------------------

class SearchPapers(BaseModel):
    """Search scholarly papers in OpenAlex by keywords. Use a focused query of 2-6 key terms; for multi-part questions run several narrower searches instead of one long query."""
    query: str = Field(description="Keyword query, e.g. 'graph neural network molecular property prediction'")
    from_year: Optional[int] = Field(description="Earliest publication year, or null for no lower bound")
    to_year: Optional[int] = Field(description="Latest publication year, or null for no upper bound")
    min_citations: Optional[int] = Field(description="Only papers with at least this many citations, or null")
    sort: Literal["relevance", "citations", "recent"] = Field(description="Result order")
    limit: int = Field(description=f"Number of papers to return, 1-{MAX_LIMIT}")


class GetPaper(BaseModel):
    """Get full details of one paper, including its complete abstract and topics. Use it to check a promising paper before recommending it."""
    paper_id: str = Field(description="OpenAlex work ID from a previous result, e.g. 'W2741809807', or a DOI")


class SearchAuthors(BaseModel):
    """Find researchers by name. Returns their OpenAlex ID, institution, citation metrics and main topics."""
    name: str = Field(description="Author name, e.g. 'Yoshua Bengio'")
    limit: int = Field(description=f"Number of authors to return, 1-{MAX_LIMIT}")


class GetAuthorPapers(BaseModel):
    """List papers written by a specific author."""
    author_id: str = Field(description="OpenAlex author ID from search_authors, e.g. 'A5023888391'")
    sort: Literal["citations", "recent"] = Field(description="Result order")
    limit: int = Field(description=f"Number of papers to return, 1-{MAX_LIMIT}")


class ToolError(Exception):
    """An error the model can act on (bad argument, not found, upstream failure)."""


# ---------------------------------------------------------------------------
# Compact result formatting
# ---------------------------------------------------------------------------

def _short_id(openalex_id: Optional[str]) -> str:
    return (openalex_id or "").replace("https://openalex.org/", "")


def compact_paper(work: Dict, abstract_chars: Optional[int] = ABSTRACT_CHARS) -> Dict:
    """Reduce an OpenAlex work to the fields an LLM needs to judge relevance."""
    source = (work.get("primary_location") or {}).get("source") or {}
    authors = [
        (a.get("author") or {}).get("display_name")
        for a in work.get("authorships") or []
    ]
    abstract = reconstruct_abstract(work.get("abstract_inverted_index")) or ""
    if abstract_chars and len(abstract) > abstract_chars:
        abstract = abstract[:abstract_chars].rsplit(" ", 1)[0] + " ..."
    return {
        "paper_id": _short_id(work.get("id")),
        "title": work.get("title"),
        "year": work.get("publication_year"),
        "venue": source.get("display_name"),
        "type": work.get("type"),
        "citations": work.get("cited_by_count", 0),
        "authors": [a for a in authors if a][:5],
        "doi": work.get("doi"),
        "open_access": bool((work.get("open_access") or {}).get("is_oa")),
        "abstract": abstract or None,
    }


def compact_author(author: Dict) -> Dict:
    institutions = author.get("last_known_institutions") or []
    return {
        "author_id": _short_id(author.get("id")),
        "name": author.get("display_name"),
        "institution": institutions[0].get("display_name") if institutions else None,
        "works_count": author.get("works_count", 0),
        "citations": author.get("cited_by_count", 0),
        "h_index": (author.get("summary_stats") or {}).get("h_index"),
        "top_topics": [t.get("display_name") for t in (author.get("topics") or [])[:5]],
    }


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class ToolExecutor:
    """Runs tool calls against OpenAlex and tracks what was returned."""

    def __init__(self, openalex_client: OpenAlexClient):
        self.client = openalex_client
        self.seen_papers: Dict[str, Dict] = {}   # short work ID -> raw OpenAlex work
        self.seen_authors: Dict[str, Dict] = {}  # short author ID -> compact author

        self._tools: Dict[str, Tuple[Type[BaseModel], Callable[[Any], Dict]]] = {
            "search_papers": (SearchPapers, self.search_papers),
            "get_paper": (GetPaper, self.get_paper),
            "search_authors": (SearchAuthors, self.search_authors),
            "get_author_papers": (GetAuthorPapers, self.get_author_papers),
        }

    @property
    def tool_schemas(self) -> List[Dict]:
        """Strict function-calling schemas for chat.completions.create(tools=...)."""
        return [
            openai.pydantic_function_tool(model, name=name, description=model.__doc__)
            for name, (model, _) in self._tools.items()
        ]

    def execute(self, name: str, arguments: str) -> Dict:
        """
        Run one tool call. Never raises: problems come back as {"error": ...}
        so the model can see what went wrong and retry with different arguments.
        """
        if name not in self._tools:
            return {"error": f"Unknown tool '{name}'. Available tools: {', '.join(self._tools)}"}
        model, func = self._tools[name]
        try:
            params = model.model_validate_json(arguments or "{}")
        except ValidationError as e:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in err['loc']) or 'arguments'}: {err['msg']}" for err in e.errors()
            )
            return {"error": f"Invalid arguments for {name}: {problems}"}
        try:
            return func(params)
        except ToolError as e:
            return {"error": str(e)}

    # -- tools -------------------------------------------------------------

    def search_papers(self, p: SearchPapers) -> Dict:
        query = p.query.strip()
        if not query:
            raise ToolError("query must not be empty")
        if p.from_year and p.to_year and p.from_year > p.to_year:
            raise ToolError(f"from_year ({p.from_year}) is after to_year ({p.to_year})")
        if p.min_citations is not None and p.min_citations < 0:
            raise ToolError("min_citations must be >= 0")

        response = self.client.search_works(
            query=query,
            from_year=p.from_year,
            to_year=p.to_year,
            min_citations=p.min_citations,
            sort=PAPER_SORTS[p.sort],
            per_page=self._clamp(p.limit),
        )
        if response.error:
            raise ToolError(f"OpenAlex search failed: {response.error}")
        return {
            "total_matches": (response.meta or {}).get("count"),
            "papers": self._remember_papers(response.data.get("results", [])),
        }

    def get_paper(self, p: GetPaper) -> Dict:
        paper_id = p.paper_id.strip()
        if not (_WORK_ID.match(paper_id) or "10." in paper_id):
            raise ToolError("paper_id must be an OpenAlex work ID like 'W2741809807' or a DOI")
        response = self.client.get_work(paper_id)
        if response.status_code == 404:
            raise ToolError(f"No paper found with id '{paper_id}'")
        if response.error:
            raise ToolError(f"OpenAlex lookup failed: {response.error}")

        work = response.data
        self.seen_papers[_short_id(work.get("id"))] = work
        details = compact_paper(work, abstract_chars=None)
        details["topics"] = [t.get("display_name") for t in (work.get("topics") or [])[:5]]
        details["referenced_works_count"] = len(work.get("referenced_works") or [])
        return details

    def search_authors(self, p: SearchAuthors) -> Dict:
        name = p.name.strip()
        if not name:
            raise ToolError("name must not be empty")
        response = self.client.search_authors(name, per_page=self._clamp(p.limit))
        if response.error:
            raise ToolError(f"OpenAlex author search failed: {response.error}")
        authors = [compact_author(a) for a in response.data.get("results", [])]
        for author in authors:
            self.seen_authors[author["author_id"]] = author
        return {"authors": authors}

    def get_author_papers(self, p: GetAuthorPapers) -> Dict:
        author_id = _short_id(p.author_id.strip())
        if not _AUTHOR_ID.match(author_id):
            raise ToolError("author_id must be an OpenAlex author ID like 'A5023888391' (use search_authors first)")
        response = self.client.search_works(
            query="",
            filter_string=f"author.id:{author_id}",
            sort=PAPER_SORTS[p.sort],
            per_page=self._clamp(p.limit),
        )
        if response.error:
            raise ToolError(f"OpenAlex lookup failed: {response.error}")
        return {
            "author_id": author_id,
            "total_papers": (response.meta or {}).get("count"),
            "papers": self._remember_papers(response.data.get("results", [])),
        }

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _clamp(limit: int) -> int:
        return max(1, min(limit, MAX_LIMIT))

    def _remember_papers(self, works: List[Dict]) -> List[Dict]:
        papers = []
        for work in works:
            if not work:
                continue
            self.seen_papers[_short_id(work.get("id"))] = work
            papers.append(compact_paper(work))
        return papers


def tool_result_json(result: Dict) -> str:
    """Serialize a tool result for a role='tool' message."""
    return json.dumps(result, ensure_ascii=False, default=str)
