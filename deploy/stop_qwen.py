"""Stop only the dedicated inference process group created by serve_qwen.py (Linux)."""

import argparse
import os
import signal
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime.resolve()
    pid = int((runtime / "qwen.pid").read_text())
    process = Path(f"/proc/{pid}")
    if not process.exists():
        print(
            "Recorded inference parent is already stopped. Check any driver-held children separately."
        )
        return
    command = (process / "cmdline").read_bytes()
    if (
        str(runtime / ".venv").encode() not in command
        or b"vllm.entrypoints.openai.api_server" not in command
    ):
        raise SystemExit(
            "PID identity no longer matches this runtime; refusing to stop it"
        )
    if os.getpgid(pid) != pid:
        raise SystemExit(
            "Expected an isolated process group; refusing to stop a shared group"
        )
    members = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            if int(fields[2]) == pid:
                members.append(entry)
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    os.killpg(pid, signal.SIGTERM)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and any(p.exists() for p in members):
        time.sleep(0.25)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    time.sleep(1)
    remaining = [p.name for p in members if p.exists()]
    if remaining:
        print("Processes still present:", ", ".join(remaining))
        raise SystemExit(
            "GPU release is not confirmed. Driver-held D/Z processes require server maintenance; do not reset a shared GPU here."
        )
    print(
        "Dedicated inference processes stopped. No other process groups were signalled."
    )


if __name__ == "__main__":
    main()
