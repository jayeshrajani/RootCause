import logging

import pytest
from fastapi.testclient import TestClient

from app.schemas.triage import TriageResponse
from tests.conftest import PNG_BYTES, VALID_FORM, jpeg


def test_valid_report_returns_labelled_mock_assessment(client: TestClient) -> None:
    response = client.post(
        "/api/v1/triage",
        data=VALID_FORM,
        files=[jpeg(), ("images", ("b.png", PNG_BYTES, "image/png"))],
    )

    assert response.status_code == 200, response.text
    result = TriageResponse.model_validate(response.json())
    assert result.analysis_mode == "mock"
    assert result.report_id.startswith("mock_")
    assert result.crop == "tomato"
    assert result.requires_expert_review is True
    assert "MOCK" in result.disclaimer
    assert result.possible_causes and all(c.confidence == "low" for c in result.possible_causes)


def test_mock_never_claims_external_evidence(client: TestClient) -> None:
    response = client.post("/api/v1/triage", data=VALID_FORM, files=[jpeg()])

    evidence = {e["source"]: e for e in response.json()["evidence"]}
    for source in ("weather", "satellite", "knowledge_base"):
        assert evidence[source]["availability"] == "not_integrated"
        assert evidence[source]["observed_at"] is None


def test_photo_alone_is_a_valid_report(client: TestClient) -> None:
    response = client.post("/api/v1/triage", files=[jpeg()])

    assert response.status_code == 200, response.text
    assert response.json()["crop"] is None


@pytest.mark.parametrize("present", ["latitude", "longitude"])
def test_coordinates_must_be_given_together(client: TestClient, present: str) -> None:
    response = client.post("/api/v1/triage", data={present: "18.5"}, files=[jpeg()])

    assert response.status_code == 422
    missing = "longitude" if present == "latitude" else "latitude"
    assert response.json()["error"]["details"][0]["field"] == missing


def test_missing_images_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/triage", data=VALID_FORM)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "images_required"


def test_more_than_three_images_is_rejected(client: TestClient) -> None:
    files = [jpeg(f"{i}.jpg") for i in range(4)]

    response = client.post("/api/v1/triage", data=VALID_FORM, files=files)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "too_many_images"


def test_non_image_file_is_rejected_even_with_image_content_type(client: TestClient) -> None:
    files = [("images", ("fake.png", b"not really an image", "image/png"))]

    response = client.post("/api/v1/triage", data=VALID_FORM, files=files)

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_image_type"


def test_oversized_image_is_rejected(client: TestClient) -> None:
    files = [("images", ("big.jpg", b"\xff\xd8\xff" + b"\x00" * 2048, "image/jpeg"))]

    response = client.post("/api/v1/triage", data=VALID_FORM, files=files)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "image_too_large"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("latitude", "91"),
        ("longitude", "-181"),
        ("latitude", "nan"),
        ("crop", "banana-tree"),
        ("description", "x" * 2001),
        ("symptom_duration", "forever"),
    ],
)
def test_invalid_fields_return_field_level_errors(
    client: TestClient, field: str, value: str
) -> None:
    response = client.post("/api/v1/triage", data={**VALID_FORM, field: value}, files=[jpeg()])

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert field in {d["field"] for d in error["details"]}
    assert value not in response.text


def test_request_over_total_size_limit_is_rejected_early(client: TestClient) -> None:
    files = [("images", ("huge.jpg", b"\xff\xd8\xff" + b"\x00" * (2 * 1024 * 1024), "image/jpeg"))]

    response = client.post("/api/v1/triage", data=VALID_FORM, files=files)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"


def test_sensitive_report_data_is_not_logged(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        response = client.post("/api/v1/triage", data=VALID_FORM, files=[jpeg()])

    assert response.status_code == 200
    assert "Triage completed" in caplog.text
    for sensitive in ("18.52", "73.86", "Near Pune", "Yellow spots"):
        assert sensitive not in caplog.text
