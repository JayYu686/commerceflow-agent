"""Create a new local v2 configuration without printing any generated credential."""

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / ".env.v2"
if target.exists():
    raise SystemExit(
        ".env.v2 already exists; edit it explicitly rather than overwriting credentials"
    )
values = {
    name: secrets.token_hex(18)
    for name in (
        "POSTGRES_PASSWORD",
        "AGENT_DB_PASSWORD",
        "COMMERCE_DB_PASSWORD",
        "CF_COMMERCE_READ_TOKEN",
        "CF_COMMERCE_WRITE_TOKEN",
        "CF_OPERATOR_PASSWORD",
        "CF_REVIEWER_PASSWORD",
        "CF_MODEL_KEY",
    )
}
values.update(
    {
        "CF_MODEL_PROVIDER": "qwen",
        "CF_MODEL_NAME": "Qwen3-8B",
        "CF_MODEL_URL": "http://127.0.0.1:18080/v1",
        "CF_DEEPSEEK_KEY": "",
        "CF_COMMERCE_URL": "http://127.0.0.1:8001",
        "CF_EMBEDDING_PATH": str(ROOT / "data/local/models/bge-small-zh-v1.5").replace(
            "\\", "/"
        ),
    }
)
values["CF_EMBEDDING_MODEL"] = values["CF_EMBEDDING_PATH"]
values["CF_DATABASE_URL"] = (
    "postgresql+psycopg://cf_agent:"
    + values["AGENT_DB_PASSWORD"]
    + "@127.0.0.1:55432/cf_agent_v2"
)
values["CF_COMMERCE_DATABASE_URL"] = (
    "postgresql+psycopg://cf_commerce:"
    + values["COMMERCE_DB_PASSWORD"]
    + "@127.0.0.1:55432/cf_commerce_v2"
)
target.write_text(
    "".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8"
)
print(
    "Created ignored .env.v2. Configure inference URL/key and read demo passwords locally."
)
