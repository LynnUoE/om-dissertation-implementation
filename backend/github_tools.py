"""
Read-only GitHub tools for the MCP server: search a repository's issues and
pull requests, and read one with its discussion.

Same layout as tools.py: a Pydantic parameter model per tool (its docstring is
the tool description) and a method on GitHubTools that runs it against the
GitHub REST API. Results are compact dicts sized for an LLM context window.

Public repositories work without a token (60 requests/hour, 10 searches/minute).
GITHUB_TOKEN raises the limits and gives access to whatever the token can read,
so use a fine-grained token with read-only "Issues" and "Pull requests" access.
"""
import re
from typing import Any, Dict, List, Literal, Optional

import requests
from pydantic import BaseModel, Field

from tools import MAX_LIMIT, ToolError

BODY_CHARS = 4000     # Issue / PR description
COMMENT_CHARS = 1500  # Each comment
MAX_COMMENTS = 30

_REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+$")


# ---------------------------------------------------------------------------
# Tool parameter schemas (docstrings become the tool descriptions)
# ---------------------------------------------------------------------------

class SearchGithubIssues(BaseModel):
    """List or search the issues or pull requests of a GitHub repository. Returns titles, state, labels and numbers; use get_github_issue to read one in full."""
    repo: Optional[str] = Field(description="Repository as 'owner/name'. Null for the server's default repository")
    kind: Literal["issue", "pr"] = Field(description="'issue' for issues, 'pr' for pull requests")
    state: Literal["open", "closed", "all"] = Field(description="Filter by state; merged pull requests count as closed")
    query: Optional[str] = Field(description="Keywords to match in the title, body and comments. Null to list everything")
    sort: Literal["updated", "created", "comments"] = Field(description="Result order, highest or newest first")
    limit: int = Field(description=f"Number of results to return, 1-{MAX_LIMIT}")


class GetGithubIssue(BaseModel):
    """Read one GitHub issue or pull request by number: its description, labels, state and comments. Pull requests also include their branches, merge status and diff size."""
    number: int = Field(description="Issue or pull request number, e.g. 16")
    repo: Optional[str] = Field(description="Repository as 'owner/name'. Null for the server's default repository")
    max_comments: int = Field(description=f"Number of comments to include, oldest first, 0-{MAX_COMMENTS}")


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

class GitHubClient:
    """Minimal GitHub REST client; raises ToolError with a message the model can act on."""

    def __init__(self, token: Optional[str] = None, timeout: tuple = (5, 20)):
        self.base_url = "https://api.github.com"
        self.authenticated = bool(token)
        self.timeout = timeout  # (connect, read) seconds
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "litfinder-mcp",
        })
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def get(self, path: str, params: Optional[Dict] = None) -> Any:
        try:
            response = self.session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            raise ToolError(f"GitHub request failed: {type(e).__name__}") from e

        if response.status_code == 200:
            try:
                return response.json()
            except ValueError as e:
                raise ToolError("GitHub returned an invalid response") from e

        # GitHub reports an exhausted rate limit as 403 or 429
        if response.status_code in (403, 429) and (
                response.headers.get("X-RateLimit-Remaining") == "0" or "Retry-After" in response.headers):
            hint = "" if self.authenticated else "; set GITHUB_TOKEN on the server for higher limits"
            raise ToolError(f"GitHub rate limit reached, try again later{hint}")
        if response.status_code == 404:
            raise ToolError("Not found on GitHub: the repository or number does not exist, or it is private "
                            "and the server's token cannot read it")
        if response.status_code == 401:
            raise ToolError("GitHub rejected the server's GITHUB_TOKEN")
        try:
            message = response.json().get("message", "")
        except (ValueError, AttributeError):
            message = ""
        raise ToolError(f"GitHub error (HTTP {response.status_code}): {message[:200]}")


# ---------------------------------------------------------------------------
# Compact result formatting
# ---------------------------------------------------------------------------

def _truncate(text: Optional[str], limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + f"... [truncated, {len(text)} characters in total]"


def _login(item: Dict) -> Optional[str]:
    return (item.get("user") or {}).get("login")


def _summary(item: Dict) -> Dict:
    """Fields shared by search results and full issues. The issues API also returns pull requests."""
    pull = item.get("pull_request")
    result = {
        "number": item.get("number"),
        "kind": "pr" if pull is not None else "issue",
        "title": item.get("title") or "",
        "state": item.get("state"),
        "author": _login(item),
        "labels": [label["name"] for label in item.get("labels") or [] if isinstance(label, dict)],
        "comments": item.get("comments", 0),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "url": item.get("html_url"),
    }
    if pull is not None:
        result["merged"] = bool(pull.get("merged_at"))
    return result


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class GitHubTools:
    def __init__(self, client: GitHubClient, default_repo: Optional[str] = None):
        self.client = client
        self.default_repo = default_repo or None

    def _repo(self, repo: Optional[str]) -> str:
        repo = (repo or self.default_repo or "").strip()
        if not repo:
            raise ToolError("No repository given and the server has no default (GITHUB_REPO); pass repo as 'owner/name'")
        # Also keeps the value from changing the meaning of the search query or the URL path
        if not _REPO.match(repo):
            raise ToolError(f"Invalid repo '{repo}': expected 'owner/name', e.g. 'modelcontextprotocol/python-sdk'")
        return repo

    def search_github_issues(self, params: SearchGithubIssues) -> Dict:
        repo = self._repo(params.repo)
        if not 1 <= params.limit <= MAX_LIMIT:
            raise ToolError(f"limit must be between 1 and {MAX_LIMIT}")

        # The search API covers listing and keyword search, and unlike /issues keeps the two kinds apart
        terms = [f"repo:{repo}", f"is:{params.kind}"]
        if params.state != "all":
            terms.append(f"is:{params.state}")
        if params.query and params.query.strip():
            terms.append(params.query.strip())
        data = self.client.get("/search/issues", {"q": " ".join(terms), "sort": params.sort,
                                                  "order": "desc", "per_page": params.limit})
        return {
            "repo": repo,
            "total_matches": data.get("total_count", 0),
            "results": [_summary(item) for item in data.get("items") or []],
        }

    def get_github_issue(self, params: GetGithubIssue) -> Dict:
        repo = self._repo(params.repo)
        if params.number < 1:
            raise ToolError("number must be a positive integer")
        if not 0 <= params.max_comments <= MAX_COMMENTS:
            raise ToolError(f"max_comments must be between 0 and {MAX_COMMENTS}")

        item = self.client.get(f"/repos/{repo}/issues/{params.number}")
        result = {"repo": repo, **_summary(item)}
        result["closed_at"] = item.get("closed_at")
        result["body"] = _truncate(item.get("body"), BODY_CHARS)

        if result["kind"] == "pr":
            pull = self.client.get(f"/repos/{repo}/pulls/{params.number}")
            result["pull_request"] = {
                "draft": pull.get("draft", False),
                "merged": pull.get("merged", False),
                "merged_at": pull.get("merged_at"),
                "base": (pull.get("base") or {}).get("ref"),
                "head": (pull.get("head") or {}).get("ref"),
                "commits": pull.get("commits"),
                "changed_files": pull.get("changed_files"),
                "additions": pull.get("additions"),
                "deletions": pull.get("deletions"),
            }

        comments: List[Dict] = []
        if params.max_comments and result["comments"]:
            raw = self.client.get(f"/repos/{repo}/issues/{params.number}/comments",
                                  {"per_page": params.max_comments})
            comments = [{"author": _login(c), "created_at": c.get("created_at"),
                         "body": _truncate(c.get("body"), COMMENT_CHARS)} for c in raw]
        result["comment_list"] = comments
        return result
