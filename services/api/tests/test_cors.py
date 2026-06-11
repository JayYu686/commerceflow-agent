from fastapi.testclient import TestClient

from app.main import create_app


def test_cors_preflight_allows_configured_local_web_origin() -> None:
    client = TestClient(create_app())

    response = client.options(
        "/api/agent/after-sales/action-plans",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, Idempotency-Key",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "Idempotency-Key" in response.headers["access-control-allow-headers"]


def test_cors_preflight_does_not_allow_unconfigured_origin() -> None:
    client = TestClient(create_app())

    response = client.options(
        "/api/agent/after-sales/action-plans",
        headers={
            "Origin": "http://malicious.local",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, Idempotency-Key",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
