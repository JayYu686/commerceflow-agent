from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_returns_service_status() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "commerceflow-api"
    assert payload["status"] == "ok"
    assert payload["environment"] == "local"
    assert "timestamp" in payload
