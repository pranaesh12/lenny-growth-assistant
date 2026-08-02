"""
Smoke test for the application skeleton.

Confirms the app boots and the health endpoint responds correctly.
This is the only test in Phase 1 — no domain logic exists yet to test.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_200() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert "service" in body
    assert "version" in body
    assert "timestamp" in body


def test_health_check_includes_request_id_header() -> None:
    response = client.get("/api/v1/health")

    assert "X-Request-ID" in response.headers