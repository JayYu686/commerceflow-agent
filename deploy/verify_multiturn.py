"""Exercise missing-order clarification and SSE cursor recovery against the real app."""

import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--order", default="CF000010")
    args = parser.parse_args()
    values = dotenv_values(ROOT / ".env.v2")
    with httpx.Client(
        base_url="http://127.0.0.1:8000", timeout=20, trust_env=False
    ) as client:

        def post(path, body):
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

        def wait(case_id, expected):
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                response = client.get("/api/cases/" + case_id)
                response.raise_for_status()
                view = response.json()
                if view["status"] == expected:
                    return view
                if view["status"] not in {"investigating", "needs_information"}:
                    raise RuntimeError("Unexpected terminal status: " + view["status"])
                time.sleep(1)
            raise RuntimeError("Model did not reach expected status: " + expected)

        post(
            "/api/session",
            {"role": "operator", "password": values["CF_OPERATOR_PASSWORD"]},
        )
        case_id = post(
            "/api/cases",
            {"content": "蓝牙耳机左耳没有声音，收纳包正常，我想退耳机的钱。"},
        )["case_id"]
        first = wait(case_id, "needs_information")
        assert first["plan"] is None and first["executions"] == []
        post(f"/api/cases/{case_id}/messages", {"content": f"订单号是 {args.order}。"})
        second = wait(case_id, "waiting_approval")
        assert second["plan"]["amount_fen"] == 19900
        assert second["plan"]["order_no"] == args.order
        assert second["plan"]["item_id"] == args.order + "-1"
        assert second["executions"] == []

        def first_event(cursor=0):
            with client.stream(
                "GET",
                f"/api/cases/{case_id}/events",
                headers={"Last-Event-ID": str(cursor)},
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        return json.loads(line[6:])
            raise AssertionError("No SSE event")

        event = first_event()
        resumed = first_event(event["id"])
        assert resumed["id"] > event["id"]
        proof = {
            "case_id": case_id,
            "order_no": args.order,
            "first_status": first["status"],
            "second_status": second["status"],
            "amount_fen": second["plan"]["amount_fen"],
            "sse_first_id": event["id"],
            "sse_resumed_id": resumed["id"],
            "executions_without_approval": len(second["executions"]),
        }
        (ROOT / "data/local/multiturn-proof.json").write_text(
            json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            "PASS: real multi-turn clarification, item selection, approval boundary and SSE reconnect"
        )


if __name__ == "__main__":
    main()
