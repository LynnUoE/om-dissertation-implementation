import pytest
import requests

from github_tools import (BODY_CHARS, COMMENT_CHARS, MAX_COMMENTS, GetGithubIssue, GitHubClient, GitHubTools,
                          SearchGithubIssues)
from tools import MAX_LIMIT, ToolError

from conftest import FakeGitHub, make_issue


def search(**overrides) -> SearchGithubIssues:
    return SearchGithubIssues(**{"repo": None, "kind": "issue", "state": "open", "query": None,
                                 "sort": "updated", "limit": 10, **overrides})


def get(number: int, **overrides) -> GetGithubIssue:
    return GetGithubIssue(**{"number": number, "repo": None, "max_comments": 10, **overrides})


def make_tools(responses=None, default_repo="acme/widgets"):
    github = FakeGitHub(responses)
    return GitHubTools(github, default_repo), github


# -- search_github_issues ----------------------------------------------------

def test_search_builds_the_query_from_its_filters():
    tools, github = make_tools({"/search/issues": {"total_count": 0, "items": []}})
    tools.search_github_issues(search(repo="octo/repo", kind="pr", state="closed",
                                      query=" rate limit ", sort="comments", limit=5))
    assert github.calls[0]["path"] == "/search/issues"
    assert github.calls[0]["params"] == {"q": "repo:octo/repo is:pr is:closed rate limit",
                                         "sort": "comments", "order": "desc", "per_page": 5}

    tools.search_github_issues(search(state="all"))
    assert github.calls[1]["params"]["q"] == "repo:acme/widgets is:issue"


def test_search_returns_compact_results():
    merged = make_issue(9, pull=True, state="closed", pull_request={"merged_at": "2026-01-03T00:00:00Z"})
    tools, _ = make_tools({"/search/issues": {"total_count": 40, "items": [make_issue(7), merged]}})
    result = tools.search_github_issues(search())
    assert result["total_matches"] == 40
    assert result["results"][0] == {
        "number": 7, "kind": "issue", "title": "Issue 7", "state": "open", "author": "octocat",
        "labels": ["bug"], "comments": 0, "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z", "url": "https://github.com/acme/widgets/issues/7",
    }
    assert result["results"][1]["kind"] == "pr" and result["results"][1]["merged"] is True
    assert "body" not in result["results"][0]


@pytest.mark.parametrize("repo", ["widgets", "acme/widgets is:private", "acme/widgets/../other", "/widgets", ""])
def test_invalid_or_missing_repo_is_rejected_before_any_request(repo):
    tools, github = make_tools(default_repo=None)
    with pytest.raises(ToolError, match="repo"):
        tools.search_github_issues(search(repo=repo))
    with pytest.raises(ToolError, match="repo"):
        tools.get_github_issue(get(1, repo=repo))
    assert github.calls == []


def test_limits_are_validated():
    tools, github = make_tools()
    for limit in (0, MAX_LIMIT + 1):
        with pytest.raises(ToolError, match="limit"):
            tools.search_github_issues(search(limit=limit))
    with pytest.raises(ToolError, match="max_comments"):
        tools.get_github_issue(get(1, max_comments=MAX_COMMENTS + 1))
    with pytest.raises(ToolError, match="number"):
        tools.get_github_issue(get(0))
    assert github.calls == []


# -- get_github_issue --------------------------------------------------------

def test_get_issue_with_comments():
    comments = [{"user": {"login": "hubot"}, "created_at": "2026-01-02T00:00:00Z", "body": "c" * (COMMENT_CHARS + 1)}]
    tools, github = make_tools({
        "/repos/acme/widgets/issues/7": make_issue(7, comments=1, body="b" * (BODY_CHARS + 500)),
        "/repos/acme/widgets/issues/7/comments": comments,
    })
    result = tools.get_github_issue(get(7, max_comments=3))
    assert result["kind"] == "issue" and "pull_request" not in result
    assert result["body"].startswith("b" * BODY_CHARS + "... [truncated")
    assert str(BODY_CHARS + 500) in result["body"]
    assert result["comment_list"][0]["author"] == "hubot"
    assert result["comment_list"][0]["body"].startswith("c" * COMMENT_CHARS + "...")
    assert github.calls[-1] == {"path": "/repos/acme/widgets/issues/7/comments", "params": {"per_page": 3}}


def test_get_issue_skips_the_comments_request_when_there_are_none_or_none_wanted():
    tools, github = make_tools({"/repos/acme/widgets/issues/7": make_issue(7, body=None),
                                "/repos/acme/widgets/issues/8": make_issue(8, comments=4)})
    assert tools.get_github_issue(get(7))["comment_list"] == []
    result = tools.get_github_issue(get(8, max_comments=0))
    assert result["comments"] == 4 and result["comment_list"] == []
    assert [c["path"] for c in github.calls] == ["/repos/acme/widgets/issues/7", "/repos/acme/widgets/issues/8"]
    assert tools.get_github_issue(get(7))["body"] == ""


def test_get_pull_request_adds_merge_and_diff_details():
    tools, github = make_tools({
        "/repos/acme/widgets/issues/9": make_issue(9, pull=True, state="closed",
                                                   pull_request={"merged_at": "2026-01-03T00:00:00Z"}),
        "/repos/acme/widgets/pulls/9": {"draft": False, "merged": True, "merged_at": "2026-01-03T00:00:00Z",
                                        "base": {"ref": "main"}, "head": {"ref": "fix/bug"},
                                        "commits": 2, "changed_files": 3, "additions": 40, "deletions": 5},
    })
    result = tools.get_github_issue(get(9))
    assert result["kind"] == "pr" and result["merged"] is True
    assert result["pull_request"] == {"draft": False, "merged": True, "merged_at": "2026-01-03T00:00:00Z",
                                      "base": "main", "head": "fix/bug", "commits": 2, "changed_files": 3,
                                      "additions": 40, "deletions": 5}


# -- GitHubClient ------------------------------------------------------------

class StubResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code, self.payload, self.headers = status_code, payload, headers or {}

    def json(self):
        if self.payload is None:
            raise ValueError("no JSON")
        return self.payload


def make_client(response, token=None) -> GitHubClient:
    client = GitHubClient(token)

    def fake_get(url, params=None, timeout=None):
        client.requested = {"url": url, "params": params, "timeout": timeout}
        if isinstance(response, Exception):
            raise response
        return response
    client.session.get = fake_get
    return client


def test_client_sends_the_token_only_when_configured():
    assert "Authorization" not in GitHubClient().session.headers
    client = make_client(StubResponse(payload={"ok": True}), token="t0ken")
    assert client.session.headers["Authorization"] == "Bearer t0ken"
    assert client.get("/repos/a/b/issues/1", {"per_page": 1}) == {"ok": True}
    assert client.requested == {"url": "https://api.github.com/repos/a/b/issues/1",
                                "params": {"per_page": 1}, "timeout": (5, 20)}


@pytest.mark.parametrize("response, token, message", [
    (StubResponse(404, {"message": "Not Found"}), None, "Not found on GitHub"),
    (StubResponse(403, {"message": "API rate limit exceeded"}, {"X-RateLimit-Remaining": "0"}), None,
     "rate limit reached, try again later; set GITHUB_TOKEN"),
    (StubResponse(429, {}, {"Retry-After": "60"}), "t0ken", "rate limit reached, try again later$"),
    (StubResponse(403, {"message": "Resource not accessible"}), "t0ken", r"HTTP 403\): Resource not accessible"),
    (StubResponse(401, {"message": "Bad credentials"}), "t0ken", "rejected the server's GITHUB_TOKEN"),
    (StubResponse(502, None), None, r"HTTP 502\)"),
    (StubResponse(200, None), None, "invalid response"),
    (requests.exceptions.ConnectTimeout("https://api.github.com/?secret"), None, "request failed: ConnectTimeout$"),
])
def test_client_turns_failures_into_tool_errors(response, token, message):
    with pytest.raises(ToolError, match=message):
        make_client(response, token).get("/search/issues")
