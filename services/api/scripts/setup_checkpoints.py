from app.agent.checkpoint import setup_postgres_checkpoints


def main() -> None:
    setup_postgres_checkpoints()


if __name__ == "__main__":
    main()
