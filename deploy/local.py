"""Local development launcher. Secrets stay in ignored .env.v2 and child environments."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services/api"
LOCAL = ROOT / "data/local"


def main():
    load_dotenv(ROOT / ".env.v2", override=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["exec", "start", "status"])
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == "exec":
        command = args.arguments
        if command[0] == "python":
            command[0] = sys.executable
        raise SystemExit(subprocess.call(command, cwd=API))
    if args.action == "status":
        print(
            (LOCAL / "processes.json").read_text()
            if (LOCAL / "processes.json").exists()
            else "not started"
        )
        return
    LOCAL.mkdir(parents=True, exist_ok=True)
    processes = {}
    commands = {
        "commerce": (
            [
                sys.executable,
                "-m",
                "uvicorn",
                "commerceflow.commerce:app",
                "--port",
                "8001",
            ],
            API,
        ),
        "api": (
            [sys.executable, "-m", "uvicorn", "commerceflow.api:app", "--port", "8000"],
            API,
        ),
        "worker": ([sys.executable, "-m", "commerceflow.worker"], API),
        "web": (
            [shutil.which("npm.cmd" if os.name == "nt" else "npm"), "run", "dev"],
            ROOT / "apps/web",
        ),
    }
    for name, (command, cwd) in commands.items():
        with (LOCAL / f"{name}.log").open("ab") as output:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=output,
                stderr=output,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                start_new_session=os.name != "nt",
            )
        processes[name] = process.pid
    (LOCAL / "processes.json").write_text(json.dumps(processes, indent=2))
    print("Started local processes:", processes)


if __name__ == "__main__":
    main()
