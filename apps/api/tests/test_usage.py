import pytest
from fastapi.testclient import TestClient

from app.services.usage import SESSION_HEADER, InvestigationLimiter, InvestigationLimitError
from tests.conftest import jpeg

SESSION = "visit-1234abcd"


def triage(client: TestClient, session: str | None = SESSION, **data: str) -> int:
    headers = {SESSION_HEADER: session} if session else {}
    response = client.post("/api/v1/triage", headers=headers, data=data, files=[jpeg()])
    return int(response.status_code)


def test_five_investigations_per_session_then_a_friendly_429(client: TestClient) -> None:
    assert [triage(client) for _ in range(5)] == [200] * 5

    response = client.post("/api/v1/triage", headers={SESSION_HEADER: SESSION}, files=[jpeg()])

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "investigation_limit"
    assert triage(client, session="another-visit-99") == 200


def test_rejected_reports_do_not_use_up_the_allowance(client: TestClient) -> None:
    for _ in range(6):
        assert triage(client, latitude="18.5") == 422

    assert [triage(client) for _ in range(5)] == [200] * 5


def test_ip_backstop_catches_rotating_session_ids() -> None:
    now = [0.0]
    limiter = InvestigationLimiter(session_limit=5, ip_limit_per_hour=3, clock=lambda: now[0])
    for i in range(3):
        with limiter.reserve(session_id=f"rotating-{i:04d}", ip="203.0.113.7"):
            pass

    with (
        pytest.raises(InvestigationLimitError) as caught,
        limiter.reserve(session_id="rotating-9999", ip="203.0.113.7"),
    ):
        pass
    assert caught.value.headers["Retry-After"] == "3601"

    now[0] = 3601
    with limiter.reserve(session_id="rotating-9999", ip="203.0.113.7"):
        pass


def test_failed_analysis_is_refunded() -> None:
    limiter = InvestigationLimiter(session_limit=1, ip_limit_per_hour=1)

    with pytest.raises(RuntimeError), limiter.reserve(session_id=SESSION, ip="203.0.113.7"):
        raise RuntimeError("model unavailable")

    assert limiter.remaining(SESSION) == 1
    with limiter.reserve(session_id=SESSION, ip="203.0.113.7"):
        pass
    assert limiter.remaining(SESSION) == 0


def test_invalid_or_missing_session_ids_fall_back_to_the_ip_cap() -> None:
    limiter = InvestigationLimiter(session_limit=1, ip_limit_per_hour=2)
    for session in (None, "bad id!"):
        with limiter.reserve(session_id=session, ip="203.0.113.7"):
            pass

    with (
        pytest.raises(InvestigationLimitError),
        limiter.reserve(session_id=None, ip="203.0.113.7"),
    ):
        pass


def test_zero_disables_limits() -> None:
    limiter = InvestigationLimiter(session_limit=0, ip_limit_per_hour=0)
    for _ in range(20):
        with limiter.reserve(session_id=SESSION, ip="203.0.113.7"):
            pass
