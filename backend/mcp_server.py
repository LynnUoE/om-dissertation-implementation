"""
MCP server exposing LitFinder's OpenAlex literature tools.

The tools are the same ones the agent uses via function calling (tools.py);
this module only adapts them to the Model Context Protocol, so any MCP host
(Claude Code, Claude Desktop, ...) can search papers and researchers.

Run:
    python backend/mcp_server.py                     # stdio, launched by an MCP host
    python backend/mcp_server.py --transport http    # Streamable HTTP at http://127.0.0.1:8000/mcp

Configuration comes from backend/.env: OPENALEX_API_KEY (recommended) and
RESEARCHER_EMAIL. No LLM key is needed; the host's model does the reasoning.
"""
import argparse
import os
from typing import Annotated, Callable, Dict, Literal, Optional

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError as MCPToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from openalex_client import OpenAlexClient, create_client
from tools import GetAuthorPapers, GetPaper, SearchAuthors, SearchPapers, ToolError, ToolExecutor

INSTRUCTIONS = """Search academic literature and researchers in OpenAlex.
Use several focused search_papers queries (2-6 key terms) rather than one long query.
paper_id and author_id values from results can be passed to get_paper and get_author_papers.
Abstracts in search results are truncated; get_paper returns the full abstract."""

# Every tool only reads from OpenAlex, an external (open-world) service
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False,
                            idempotent_hint=True, open_world_hint=True)


def _describe(model, field: str) -> str:
    """Reuse the parameter descriptions from the function-calling schemas."""
    return model.model_fields[field].description


def create_server(openalex_client: OpenAlexClient) -> MCPServer:
    server = MCPServer(name="litfinder", instructions=INSTRUCTIONS)

    def run(tool: Callable[[ToolExecutor], Dict]) -> Dict:
        # Fresh executor per call: MCP needs no grounding state across calls
        try:
            return tool(ToolExecutor(openalex_client))
        except ToolError as e:
            raise MCPToolError(str(e)) from e  # is_error=True result the model can read

    @server.tool(name="search_papers", description=SearchPapers.__doc__, annotations=READ_ONLY)
    def search_papers(
        query: Annotated[str, Field(description=_describe(SearchPapers, "query"))],
        from_year: Annotated[Optional[int], Field(description=_describe(SearchPapers, "from_year"))] = None,
        to_year: Annotated[Optional[int], Field(description=_describe(SearchPapers, "to_year"))] = None,
        min_citations: Annotated[Optional[int], Field(description=_describe(SearchPapers, "min_citations"))] = None,
        sort: Annotated[Literal["relevance", "citations", "recent"],
                        Field(description=_describe(SearchPapers, "sort"))] = "relevance",
        limit: Annotated[int, Field(description=_describe(SearchPapers, "limit"))] = 10,
    ) -> Dict:
        params = SearchPapers(query=query, from_year=from_year, to_year=to_year,
                              min_citations=min_citations, sort=sort, limit=limit)
        return run(lambda ex: ex.search_papers(params))

    @server.tool(name="get_paper", description=GetPaper.__doc__, annotations=READ_ONLY)
    def get_paper(
        paper_id: Annotated[str, Field(description=_describe(GetPaper, "paper_id"))],
    ) -> Dict:
        return run(lambda ex: ex.get_paper(GetPaper(paper_id=paper_id)))

    @server.tool(name="search_authors", description=SearchAuthors.__doc__, annotations=READ_ONLY)
    def search_authors(
        name: Annotated[str, Field(description=_describe(SearchAuthors, "name"))],
        limit: Annotated[int, Field(description=_describe(SearchAuthors, "limit"))] = 5,
    ) -> Dict:
        return run(lambda ex: ex.search_authors(SearchAuthors(name=name, limit=limit)))

    @server.tool(name="get_author_papers", description=GetAuthorPapers.__doc__, annotations=READ_ONLY)
    def get_author_papers(
        author_id: Annotated[str, Field(description=_describe(GetAuthorPapers, "author_id"))],
        sort: Annotated[Literal["citations", "recent"],
                        Field(description=_describe(GetAuthorPapers, "sort"))] = "citations",
        limit: Annotated[int, Field(description=_describe(GetAuthorPapers, "limit"))] = 10,
    ) -> Dict:
        params = GetAuthorPapers(author_id=author_id, sort=sort, limit=limit)
        return run(lambda ex: ex.get_author_papers(params))

    @server.prompt(name="literature_review",
                   description="Find and summarize the key papers on a research topic")
    def literature_review(topic: str) -> str:
        return (
            f"Find the most important academic papers on: {topic}\n\n"
            "1. Run 2-4 focused search_papers queries covering the topic's main aspects.\n"
            "2. Use get_paper on promising papers whose abstracts are truncated.\n"
            "3. Recommend 5-10 papers, best first. For each give the title, year, paper_id "
            "and one sentence on what it contributes, based on its abstract.\n"
            "Only cite papers returned by the tools."
        )

    return server


def main():
    parser = argparse.ArgumentParser(description="LitFinder MCP server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    # MCP hosts launch servers from their own working directory, so locate .env explicitly
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    openalex_client = create_client(
        os.getenv("RESEARCHER_EMAIL", "research@example.com"),
        os.getenv("OPENALEX_API_KEY") or None,
    )
    server = create_server(openalex_client)

    if args.transport == "http":
        server.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        server.run()  # stdio: JSON-RPC on stdout, so all logging goes to stderr


if __name__ == "__main__":
    main()
