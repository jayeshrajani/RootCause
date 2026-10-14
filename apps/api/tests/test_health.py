from fastapi.testclient import TestClient


def test_health_reports_ok_and_mock_mode(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["analysis_mode"] == "mock"
