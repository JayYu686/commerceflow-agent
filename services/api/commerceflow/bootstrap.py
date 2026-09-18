import argparse
from datetime import timedelta

from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import select

from commerceflow.agent import checkpoint_url
from commerceflow.db import digest, transaction, utcnow
from commerceflow.models import Order, OrderItem, Policy
from commerceflow.policy import embed, policy_sources


def seed_commerce():
    now = utcnow()
    with transaction(True) as session:
        if session.scalar(select(Order.order_no).limit(1)):
            return
        for index in range(300):
            number = f"CF{index + 1:06d}"
            delivered = (
                None if index % 3 == 1 else now - timedelta(days=2 if index % 3 == 0 else 10)
            )
            paid = now - timedelta(days=15)
            session.add(
                Order(
                    order_no=number,
                    customer_id=f"CUSTOMER-{index % 50:03d}",
                    status="delivered" if delivered else "in_transit",
                    paid_fen=24900,
                    paid_at=paid,
                    delivered_at=delivered,
                    promised_at=now - timedelta(days=3),
                    tracking_no=f"TRACK-{index:06d}",
                    carrier_events=[
                        {"kind": "picked_up", "at": (paid + timedelta(days=1)).isoformat()},
                        {
                            "kind": "movement",
                            "at": (now - timedelta(days=5 if not delivered else 12)).isoformat(),
                        },
                    ],
                )
            )
            session.flush()
            session.add_all(
                [
                    OrderItem(
                        id=number + "-1",
                        order_no=number,
                        name="蓝牙耳机",
                        category="electronics",
                        paid_fen=19900,
                    ),
                    OrderItem(
                        id=number + "-2",
                        order_no=number,
                        name="耳机收纳包",
                        category="accessories",
                        paid_fen=5000,
                    ),
                ]
            )


def seed_policies():
    sources = policy_sources()
    vectors = embed([s["content"] for s in sources])
    with transaction() as session:
        for source, vector in zip(sources, vectors, strict=True):
            checksum = digest({k: source[k] for k in ("content", "rules", "version")})
            prior = session.get(Policy, source["id"])
            if prior:
                if prior.checksum != checksum:
                    raise RuntimeError("Existing policy differs: publish a new version instead")
                continue
            from datetime import datetime

            session.add(
                Policy(
                    **{k: v for k, v in source.items() if k != "effective_from"},
                    effective_from=datetime.fromisoformat(source["effective_from"]),
                    checksum=checksum,
                    embedding=vector,
                    embedding_model="BAAI/bge-small-zh-v1.5",
                )
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=["commerce", "agent"])
    args = parser.parse_args()
    if args.target == "commerce":
        seed_commerce()
    else:
        seed_policies()
        with PostgresSaver.from_conn_string(checkpoint_url()) as saver:
            saver.setup()


if __name__ == "__main__":
    main()
