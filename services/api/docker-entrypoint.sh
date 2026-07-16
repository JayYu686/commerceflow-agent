#!/bin/sh
set -eu

python -m alembic upgrade head
python -m scripts.setup_checkpoints
python -m scripts.bootstrap_demo
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
