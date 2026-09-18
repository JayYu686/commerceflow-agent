"""Exercise real UI-facing APIs, model, MCP, reviewer and execution confirmation."""

import json
import time
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    secrets = dotenv_values(ROOT / ".env.v2")

    def post(client, path, body):
        response = client.post(
            path,
            json=body,
            headers={
                "X-Requested-With": "CommerceFlow",
                "Idempotency-Key": str(uuid4()),
            },
        )
        response.raise_for_status()
        return response.json()

    def wait(client, case_id, terminal):
        for _ in range(240):
            result = client.get("/api/cases/" + case_id).json()
            if result["status"] in terminal:
                return result
            if result["status"] in {"stopped", "no_action", "needs_information"}:
                raise RuntimeError(json.dumps(result, ensure_ascii=False))
            time.sleep(1)
        raise RuntimeError("Timed out waiting for case")

    with (
        httpx.Client(
            base_url="http://127.0.0.1:8000", timeout=20, trust_env=False
        ) as operator,
        httpx.Client(
            base_url="http://127.0.0.1:8000", timeout=20, trust_env=False
        ) as reviewer,
    ):
        for client, role in [(operator, "operator"), (reviewer, "reviewer")]:
            post(
                client,
                "/api/session",
                {"role": role, "password": secrets[f"CF_{role.upper()}_PASSWORD"]},
            )
        case = post(
            operator,
            "/api/cases",
            {
                "content": "订单 CF000001 的蓝牙耳机左耳没有声音，收纳包没有问题，我要退耳机的钱。"
            },
        )
        print("Real model case:", case["case_id"], flush=True)
        view = wait(operator, case["case_id"], {"waiting_approval"})
        plan = view["plan"]
        assert plan["amount_fen"] == 19900
        post(
            reviewer,
            f"/api/plans/{plan['id']}/approval",
            {
                "approved": True,
                "comment": "已核实耳机左耳缺陷，收纳包正常，无人为损坏证据",
                "evidence_checked": True,
            },
        )
        execution = post(
            operator, f"/api/plans/{plan['id']}/confirmation", {"confirmed": True}
        )
        view = wait(operator, case["case_id"], {"completed"})
        result = operator.get("/api/executions/" + execution["execution_id"]).json()
        assert result["status"] == "succeeded"
        (ROOT / "data/local/smoke-result.json").write_text(
            json.dumps(
                {"case": view, "execution": result}, ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )
        print(
            "PASS: actual Qwen investigation -> reviewer -> confirmation -> item refund",
            flush=True,
        )


if __name__ == "__main__":
    main()
