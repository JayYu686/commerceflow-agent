import os
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import text

from commerceflow.config import settings
from commerceflow.db import digest, engine, transaction, utcnow
from commerceflow.models import Base, CommerceBase, Order, OrderItem, Policy
from commerceflow.policy import embed, policy_sources

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def integration_environment():
    values = dotenv_values(ROOT / ".env.v2")
    for name, value in values.items():
        if name.startswith("CF_") and value is not None:
            os.environ[name] = value
    os.environ["CF_DATABASE_URL"] = os.environ.get("CF_DATABASE_URL", "").replace(
        "/cf_agent_v2", "/cf_agent_test"
    )
    os.environ["CF_COMMERCE_DATABASE_URL"] = os.environ.get("CF_COMMERCE_DATABASE_URL", "").replace(
        "/cf_commerce_v2", "/cf_commerce_test"
    )
    os.environ["CF_COMMERCE_URL"] = "http://127.0.0.1:18001"
    settings.cache_clear()
    engine.cache_clear()
    if not settings().database_url.endswith(
        "/cf_agent_test"
    ) or not settings().commerce_database_url.endswith("/cf_commerce_test"):
        pytest.fail("Integration tests require explicitly isolated *_test databases")
    for arguments in [[], ["-x", "database=commerce"]]:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                "alembic-v2.ini",
                *arguments,
                "upgrade",
                "head",
            ],
            check=True,
            cwd=ROOT / "services/api",
        )
    from langgraph.checkpoint.postgres import PostgresSaver

    from commerceflow.agent import checkpoint_url

    with PostgresSaver.from_conn_string(checkpoint_url()) as saver:
        saver.setup()
    logfile = ROOT / "data/local/test-commerce.log"
    logfile.parent.mkdir(parents=True, exist_ok=True)
    with logfile.open("w") as output:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "commerceflow.commerce:app", "--port", "18001"],
            cwd=ROOT / "services/api",
            stdout=output,
            stderr=output,
        )
        try:
            for _ in range(100):
                try:
                    if (
                        httpx.get(
                            "http://127.0.0.1:18001/health", timeout=1, trust_env=False
                        ).status_code
                        == 200
                    ):
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.2)
            else:
                pytest.fail("Test commerce service did not start")
            yield
        finally:
            process.terminate()
            process.wait(timeout=15)


@pytest.fixture
def db(integration_environment):
    for commerce, metadata in [(False, Base.metadata), (True, CommerceBase.metadata)]:
        with transaction(commerce) as session:
            names = ", ".join('"' + table.name + '"' for table in metadata.sorted_tables)
            session.execute(text("TRUNCATE " + names + " RESTART IDENTITY CASCADE"))
    now = utcnow()
    with transaction(True) as session:
        for number, delivered in [("TEST-REFUND", now - timedelta(days=2)), ("TEST-DELAY", None)]:
            session.add(
                Order(
                    order_no=number,
                    customer_id="CUSTOMER",
                    status="delivered" if delivered else "in_transit",
                    paid_fen=24900,
                    paid_at=now - timedelta(days=10),
                    delivered_at=delivered,
                    promised_at=now - timedelta(days=3),
                    tracking_no="TRACK",
                    carrier_events=[
                        {"kind": "movement", "at": (now - timedelta(days=5)).isoformat()}
                    ],
                )
            )
            session.flush()
            session.add_all(
                [
                    OrderItem(
                        id=number + "-1",
                        order_no=number,
                        name="耳机",
                        category="electronics",
                        paid_fen=19900,
                    ),
                    OrderItem(
                        id=number + "-2",
                        order_no=number,
                        name="收纳包",
                        category="accessories",
                        paid_fen=5000,
                    ),
                ]
            )
    sources = policy_sources()
    vectors = embed([p["content"] for p in sources])
    with transaction() as session:
        for source, vector in zip(sources, vectors, strict=True):
            session.add(
                Policy(
                    **{k: v for k, v in source.items() if k != "effective_from"},
                    effective_from=now - timedelta(days=300),
                    checksum=digest({k: source[k] for k in ("content", "rules", "version")}),
                    embedding=vector,
                    embedding_model="BAAI/bge-small-zh-v1.5",
                )
            )
    yield


@pytest.fixture
def clients(db):
    from commerceflow.api import app

    headers = {"X-Requested-With": "CommerceFlow", "Idempotency-Key": "login"}
    with TestClient(app) as operator, TestClient(app) as reviewer:
        for client, role, password in [
            (operator, "operator", settings().operator_password),
            (reviewer, "reviewer", settings().reviewer_password),
        ]:
            response = client.post(
                "/api/session",
                json={"role": role, "password": password.get_secret_value()},
                headers=headers,
            )
            assert response.status_code == 200, response.text
        yield operator, reviewer
