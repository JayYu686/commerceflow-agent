"""Isolated development PostgreSQL, no root, Docker or system-service changes."""

import argparse
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runtime", type=Path)
    args = parser.parse_args()
    root = args.runtime.resolve()
    binaries, data, socket = root / "postgres/bin", root / "pgdata", root / "pgsocket"
    socket.mkdir(mode=0o700, exist_ok=True)
    credentials = json.loads((root / "credentials.json").read_text())
    if not (data / "PG_VERSION").exists():
        subprocess.run(
            [
                str(binaries / "initdb"),
                "-D",
                str(data),
                "-U",
                "cf_admin",
                "--auth-local=trust",
                "--auth-host=scram-sha-256",
                "--encoding=UTF8",
                "--locale=C",
            ],
            check=True,
        )
        with (data / "postgresql.conf").open("a") as file:
            file.write(
                f"\nlisten_addresses='127.0.0.1'\nport=55432\nunix_socket_directories='{socket}'\n"
            )
    status = subprocess.run(
        [str(binaries / "pg_ctl"), "-D", str(data), "status"], stdout=subprocess.DEVNULL
    )
    if status.returncode:
        subprocess.run(
            [
                str(binaries / "pg_ctl"),
                "-D",
                str(data),
                "-l",
                str(root / "postgres.log"),
                "start",
                "-w",
            ],
            check=True,
        )
    command = [
        str(binaries / "psql"),
        "-h",
        str(socket),
        "-p",
        "55432",
        "-U",
        "cf_admin",
        "-d",
        "postgres",
        "-v",
        "ON_ERROR_STOP=1",
    ]
    for role, secret_name in [
        ("cf_agent", "agent_password"),
        ("cf_commerce", "commerce_password"),
    ]:
        exists = subprocess.check_output(
            command + ["-tAc", f"SELECT 1 FROM pg_roles WHERE rolname='{role}'"],
            text=True,
        ).strip()
        if not exists:
            secret = credentials[secret_name]
            if not secret.isalnum():
                raise RuntimeError("Expected generated alphanumeric password")
            subprocess.run(
                command,
                input=f"CREATE ROLE {role} LOGIN PASSWORD '{secret}';",
                text=True,
                check=True,
                stdout=subprocess.DEVNULL,
            )
        for suffix in ("v2", "test"):
            name = role + "_" + suffix
            exists = subprocess.check_output(
                command + ["-tAc", f"SELECT 1 FROM pg_database WHERE datname='{name}'"],
                text=True,
            ).strip()
            if not exists:
                subprocess.run(
                    command,
                    input=f"CREATE DATABASE {name} OWNER {role}; REVOKE CONNECT ON DATABASE {name} FROM PUBLIC; GRANT CONNECT ON DATABASE {name} TO {role};",
                    text=True,
                    check=True,
                    stdout=subprocess.DEVNULL,
                )
            if role == "cf_agent":
                subprocess.run(
                    [
                        str(binaries / "psql"),
                        "-h",
                        str(socket),
                        "-p",
                        "55432",
                        "-U",
                        "cf_admin",
                        "-d",
                        name,
                        "-v",
                        "ON_ERROR_STOP=1",
                        "-c",
                        "CREATE EXTENSION IF NOT EXISTS vector;",
                    ],
                    check=True,
                )
    print("Independent demo and test databases ready on loopback:55432")


if __name__ == "__main__":
    main()
