"""Per-visitor caps on investigations (POST /triage), the call that spends model quota.

The web app sends a random id that lives for one browser session (`X-RootCause-Session`); each
id gets `session_limit` investigations. The id is client-supplied and easy to rotate, so a
per-IP hourly cap backs it up. Counts are kept in memory per instance: enough to stop casual
over-use of a preview, not a billing-grade quota.
"""

import re
import time
from collections import OrderedDict, deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from app.core.errors import AppError

SESSION_HEADER = "X-RootCause-Session"
_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
# Bounds memory: the least recently seen sessions/IPs are forgotten first.
_MAX_TRACKED = 50_000
_HOUR_SECONDS = 3600.0


class InvestigationLimitError(AppError):
    def __init__(self, *, scope: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(
            429,
            "investigation_limit",
            "You've used all the investigations for this visit. Please come back a little later.",
        )
        self.scope = scope
        if retry_after_seconds is not None:
            self.headers["Retry-After"] = str(retry_after_seconds)


class InvestigationLimiter:
    def __init__(
        self,
        *,
        session_limit: int,
        ip_limit_per_hour: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._session_limit = session_limit
        self._ip_limit = ip_limit_per_hour
        self._clock = clock
        self._sessions: OrderedDict[str, int] = OrderedDict()
        self._ips: OrderedDict[str, deque[float]] = OrderedDict()

    def remaining(self, session_id: str | None) -> int | None:
        if self._session_limit <= 0 or not _valid(session_id):
            return None
        return max(0, self._session_limit - self._sessions.get(session_id or "", 0))

    @contextmanager
    def reserve(self, *, session_id: str | None, ip: str | None) -> Iterator[None]:
        """Counts one investigation, refunded if it fails, so a model outage costs no quota."""
        session = session_id if _valid(session_id) else None
        now = self._clock()
        if session and 0 < self._session_limit <= self._sessions.get(session, 0):
            raise InvestigationLimitError(scope="session")
        stamps = self._ip_stamps(ip, now)
        if stamps is not None and len(stamps) >= self._ip_limit:
            retry = int(stamps[0] + _HOUR_SECONDS - now) + 1
            raise InvestigationLimitError(scope="ip", retry_after_seconds=retry)

        if session and self._session_limit > 0:
            self._sessions[session] = self._sessions.get(session, 0) + 1
            self._sessions.move_to_end(session)
            _trim(self._sessions)
        if stamps is not None:
            stamps.append(now)
        try:
            yield
        except BaseException:
            if session and session in self._sessions:
                self._sessions[session] -= 1
            if stamps is not None and now in stamps:
                stamps.remove(now)
            raise

    def _ip_stamps(self, ip: str | None, now: float) -> deque[float] | None:
        if self._ip_limit <= 0 or not ip:
            return None
        stamps = self._ips.setdefault(ip, deque())
        while stamps and stamps[0] <= now - _HOUR_SECONDS:
            stamps.popleft()
        self._ips.move_to_end(ip)
        _trim(self._ips)
        return stamps


def _valid(session_id: str | None) -> bool:
    return bool(session_id and _SESSION_ID.fullmatch(session_id))


def _trim[V](entries: OrderedDict[str, V]) -> None:
    while len(entries) > _MAX_TRACKED:
        entries.popitem(last=False)
