import argparse
from pathlib import Path

from app.db.session import SessionLocal
from app.services.policy_ingestion import DEFAULT_POLICY_DIR, ingest_policies


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest deterministic local policy RAG data.")
    parser.add_argument(
        "--policy-dir",
        type=Path,
        default=DEFAULT_POLICY_DIR,
        help="Directory containing policy JSON files.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear and rebuild local policy RAG data. This deletes Phase 2A policy rows.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with SessionLocal() as session:
        summary = ingest_policies(session, policy_dir=args.policy_dir, reset=args.reset)
    print(  # noqa: T201
        f"Policy ingestion complete: documents={summary.documents}, chunks={summary.chunks}"
    )


if __name__ == "__main__":
    main()
