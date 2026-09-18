"""Run via compose exec -T api python - < deploy/compose_smoke.py; no model calls."""

from uuid import uuid4

import httpx

from commerceflow.config import settings
from commerceflow.tools import mcp_call

cfg = settings()
with httpx.Client(base_url="http://web:3000", timeout=30, trust_env=False) as client:
    assert client.get("/").status_code == 200
    response = client.post(
        "/api/session",
        json={"role": "operator", "password": cfg.operator_password.get_secret_value()},
        headers={"X-Requested-With": "CommerceFlow", "Idempotency-Key": str(uuid4())},
    )
    response.raise_for_status()
    assert client.get("/api/session").json()["role"] == "operator"
    response = client.get("/api/cases")
    response.raise_for_status()
    assert response.json() == []
assert mcp_call("get_order", {"order_no": "CF000001"})["paid_fen"] == 24900
print("Compose verified: web proxy, authenticated API, PostgreSQL, actual MCP, seeded commerce")
