"""Run via compose exec -T api python - < deploy/compose_smoke.py; no model calls."""

from uuid import uuid4
from html.parser import HTMLParser

import httpx

from commerceflow.config import settings
from commerceflow.tools import mcp_call

cfg = settings()


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {"src", "href"} and value and value.startswith("/_next/static/"):
                self.paths.add(value)


with httpx.Client(base_url="http://web:3000", timeout=30, trust_env=False) as client:
    response = client.get("/")
    response.raise_for_status()
    assets = Assets()
    assets.feed(response.text)
    assert assets.paths, "No production browser assets found"
    for asset in assets.paths:
        client.get(asset).raise_for_status()
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
print(
    "Compose verified: production browser assets, web proxy, authenticated API, PostgreSQL, actual MCP, seeded commerce"
)
