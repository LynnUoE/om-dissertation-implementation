"""
Usage limits for a public deployment. Every search spends OpenAI and OpenAlex
credit, so each costly endpoint gets two limits:

  - per client (IP address), over a sliding hour, so one visitor can't use up the demo;
  - site-wide per UTC day, which caps the daily spend whatever the traffic.

Counters live in memory. That fits the Docker image, which runs one gunicorn
process with threads (not several worker processes); they reset on restart.
"""
import math
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, Optional, Tuple

HOUR = 3600
DAY = 86400


@dataclass(frozen=True)
class Limit:
    per_client_hour: int  # Requests per client per sliding hour; 0 = unlimited
    per_day: int          # Requests per UTC day across all clients; 0 = unlimited

    @classmethod
    def parse(cls, value: Optional[str], default: "Limit") -> "Limit":
        """'20,300' -> 20 per client per hour, 300 per day; empty -> default."""
        if not value or not value.strip():
            return default
        try:
            per_hour, per_day = (int(part) for part in value.split(","))
        except ValueError:
            raise ValueError(f"Expected '<per client per hour>,<per day>', e.g. '20,300', got {value!r}")
        if per_hour < 0 or per_day < 0:
            raise ValueError(f"Limits can't be negative: {value!r}")
        return cls(per_hour, per_day)


@dataclass(frozen=True)
class Blocked:
    message: str
    retry_after: int  # Seconds


class UsageLimiter:
    def __init__(self, limits: Dict[str, Limit], labels: Optional[Dict[str, str]] = None,
                 clock: Callable[[], float] = time.time):
        """
        Args:
            limits: Limit per bucket name, e.g. {"search": Limit(20, 300)}
            labels: Plural noun per bucket for messages, e.g. {"search": "searches"}
            clock: Seconds since the epoch (injectable for tests)
        """
        self.limits = limits
        self.labels = labels or {}
        self.clock = clock
        self._lock = threading.Lock()
        self._recent: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)
        self._day = -1
        self._today: Dict[str, int] = defaultdict(int)

    def check(self, bucket: str, client: str) -> Optional[Blocked]:
        """Count one request from `client`; return None if allowed, else why it was blocked."""
        limit = self.limits.get(bucket)
        if limit is None:
            return None
        now = self.clock()
        label = self.labels.get(bucket, "requests")
        with self._lock:
            self._roll_day(now)
            if limit.per_day and self._today[bucket] >= limit.per_day:
                return Blocked(
                    f"The public demo has used today's {limit.per_day} {label}. "
                    "It resets at 00:00 UTC; please try again then.",
                    math.ceil((self._day + 1) * DAY - now))
            if limit.per_client_hour:
                recent = self._recent[(bucket, client)]
                while recent and recent[0] <= now - HOUR:
                    recent.popleft()
                if len(recent) >= limit.per_client_hour:
                    wait = math.ceil(recent[0] + HOUR - now)
                    return Blocked(
                        f"You've reached the demo limit of {limit.per_client_hour} {label} per hour. "
                        f"Please try again in {math.ceil(wait / 60)} minutes.",
                        wait)
                recent.append(now)
            self._today[bucket] += 1
            return None

    def usage(self) -> Dict[str, Dict[str, int]]:
        """Today's count and daily limit per bucket (for the health check)."""
        with self._lock:
            self._roll_day(self.clock())
            return {bucket: {"today": self._today[bucket], "per_day": limit.per_day}
                    for bucket, limit in self.limits.items()}

    def _roll_day(self, now: float) -> None:
        day = int(now // DAY)
        if day != self._day:
            self._day, self._today = day, defaultdict(int)
            # Forget clients with nothing in the last hour, so memory doesn't grow without bound
            self._recent = defaultdict(deque, {key: times for key, times in self._recent.items()
                                               if times and times[-1] > now - HOUR})
