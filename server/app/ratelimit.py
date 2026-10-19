"""Rate limiting for `POST /incident`.

`docs/INCIDENTS.md` lists this as blocking for public release: the route
takes unauthenticated input, and an open endpoint on the internet needs
more than capped free-text fields.

**One report is never limited, whatever the count.** A report saying
someone ate it, or that anyone is unwell, bypasses the limiter entirely.
A limiter that silently discards those would be the single worst piece of
code in this repository -- it would turn the one route that must always
work into the one that fails under exactly the conditions that produce a
flood of submissions. The cost of letting a flood of medical reports
through is a large file. The cost of the other error is not.

The counter is in memory, so it is per-process: it resets on restart and
does not hold across workers. That is sufficient for a single-process
deployment, which is what this service is, and it is deliberately not a
Redis dependency standing in for a decision nobody has made yet. If the
service is ever run with more than one worker, this becomes a limit of
`n_workers x limit` and the docstring stops being true -- move it to a
shared store at that point rather than raising the number.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

log = logging.getLogger(__name__)


class RateLimiter:
    """Fixed-window-free sliding count, per client key.

    A deque of timestamps per key rather than a token bucket, because the
    thing being limited is rare and bursty: a person filing two reports in
    a minute is ordinary, and a host filing two hundred is not. Timestamps
    older than the window are dropped on read, so an idle key costs
    nothing to keep and the structure needs no sweeper.
    """

    def __init__(self, limit: int, window_seconds: float):
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.limit = limit
        self.window = float(window_seconds)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque[float]:
        hits = self._hits[key]
        cutoff = now - self.window
        while hits and hits[0] <= cutoff:
            hits.popleft()
        return hits

    def allow(self, key: str, now: float | None = None) -> bool:
        """Record an attempt and say whether it is within the limit.

        A refused attempt is *not* recorded. Recording it would let a
        caller hold themselves out indefinitely by continuing to hammer
        the endpoint, which punishes a buggy client far harder than a
        malicious one -- the malicious one simply changes address.
        """
        now = time.monotonic() if now is None else now
        hits = self._prune(key, now)
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

    def retry_after(self, key: str, now: float | None = None) -> int:
        """Whole seconds until the oldest hit in the window expires."""
        now = time.monotonic() if now is None else now
        hits = self._prune(key, now)
        if not hits:
            return 0
        return max(1, int(self.window - (now - hits[0]) + 0.999))

    def forget(self, key: str) -> None:
        self._hits.pop(key, None)

    def reset(self) -> None:
        self._hits.clear()


def client_key(
    peer: str | None,
    forwarded_for: str | None,
    *,
    trust_forwarded_for: bool,
) -> str:
    """Which address to count against.

    `X-Forwarded-For` is set by the caller and is trivially spoofed, so
    trusting it by default would hand anyone a fresh quota per request --
    a rate limiter that any attacker can opt out of is worse than none,
    because it reads as protection. It is used only when the deployment
    declares it is behind a proxy that overwrites the header, and then the
    *first* entry is the originating client.

    A request with no peer address at all counts as one shared key rather
    than being waved through.
    """
    if trust_forwarded_for and forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    return peer or "unknown"
