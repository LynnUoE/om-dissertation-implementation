import pytest

import api_server
from usage_limits import DAY, HOUR, Limit, UsageLimiter


class Clock:
    def __init__(self, now: float = 10 * DAY + 1000):
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_limit_parse():
    default = Limit(1, 2)
    assert Limit.parse("20,300", default) == Limit(20, 300)
    assert Limit.parse(" ", default) == default
    assert Limit.parse(None, default) == default
    with pytest.raises(ValueError):
        Limit.parse("20", default)
    with pytest.raises(ValueError):
        Limit.parse("-1,5", default)


def test_per_client_limit_slides_over_the_hour():
    clock = Clock()
    limiter = UsageLimiter({"agent": Limit(2, 0)}, labels={"agent": "agent searches"}, clock=clock)
    assert limiter.check("agent", "1.1.1.1") is None
    clock.now += 600
    assert limiter.check("agent", "1.1.1.1") is None
    blocked = limiter.check("agent", "1.1.1.1")
    assert blocked is not None and "2 agent searches per hour" in blocked.message
    assert blocked.retry_after == HOUR - 600  # When the first request leaves the window
    assert limiter.check("agent", "2.2.2.2") is None  # Other clients are unaffected
    clock.now += HOUR - 600
    assert limiter.check("agent", "1.1.1.1") is None


def test_daily_limit_is_site_wide_and_resets_at_utc_midnight():
    clock = Clock()
    limiter = UsageLimiter({"search": Limit(0, 2)}, clock=clock)
    assert limiter.check("search", "a") is None
    assert limiter.check("search", "b") is None
    blocked = limiter.check("search", "c")
    assert blocked is not None and "today's 2 requests" in blocked.message
    assert blocked.retry_after == DAY - 1000
    assert limiter.usage() == {"search": {"today": 2, "per_day": 2}}
    clock.now += DAY - 1000
    assert limiter.check("search", "c") is None


def test_blocked_requests_are_not_counted():
    limiter = UsageLimiter({"search": Limit(1, 2)}, clock=Clock())
    assert limiter.check("search", "a") is None
    assert limiter.check("search", "a") is not None  # Per-client limit, not counted for the day
    assert limiter.check("search", "b") is None
    assert limiter.usage()["search"]["today"] == 2


def test_unknown_buckets_are_unlimited():
    assert UsageLimiter({}).check("anything", "a") is None


def test_api_returns_429_with_retry_after(monkeypatch):
    limiter = UsageLimiter({"agent": Limit(1, 0)}, labels={"agent": "agent searches"}, clock=Clock())
    monkeypatch.setattr(api_server, "usage_limiter", limiter)
    limiter.check("agent", "127.0.0.1")  # Use up this client's hour

    response = api_server.app.test_client().post(
        "/api/agent-search", json={"query": "gnn"}, environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert response.status_code == 429
    assert response.headers["Retry-After"] == str(HOUR)
    assert "1 agent searches per hour" in response.get_json()["message"]

    # Free endpoints are never limited
    assert api_server.app.test_client().get("/api/health_check").status_code == 200
