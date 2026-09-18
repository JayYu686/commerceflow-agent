"""Start one user-owned inference process after checking the selected GPU is idle."""

import argparse
import json
import os
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--gpu", type=int, required=True)
    args = parser.parse_args()
    runtime = args.runtime.resolve()
    pidfile = runtime / "qwen.pid"
    if pidfile.exists():
        try:
            os.kill(int(pidfile.read_text()), 0)
        except ProcessLookupError:
            pass
        else:
            raise SystemExit("The recorded model process is still running")
    used = int(
        subprocess.check_output(
            [
                "nvidia-smi",
                f"--id={args.gpu}",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            text=True,
        ).strip()
    )
    processes = subprocess.check_output(
        [
            "nvidia-smi",
            f"--id={args.gpu}",
            "--query-compute-apps=pid",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    ).strip()
    if used > 100 or processes:
        raise SystemExit("Selected GPU is occupied; no processes have been modified")
    secret = json.loads((runtime / "credentials.json").read_text())["model_key"]
    env = {
        **os.environ,
        "CUDA_VISIBLE_DEVICES": str(args.gpu),
        "OMP_NUM_THREADS": "2",
        "VLLM_API_KEY": secret,
        "TOKENIZERS_PARALLELISM": "false",
    }
    command = [
        str(runtime / ".venv/bin/python"),
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        str(args.model),
        "--served-model-name",
        "Qwen3-8B",
        "--host",
        "127.0.0.1",
        "--port",
        "18080",
        "--dtype",
        "bfloat16",
        "--max-model-len",
        "8192",
        "--max-num-seqs",
        "2",
        "--gpu-memory-utilization",
        "0.90",
        "--enable-auto-tool-choice",
        "--tool-call-parser",
        "hermes",
        "--disable-log-requests",
    ]
    with (runtime / "qwen.log").open("ab") as output:
        process = subprocess.Popen(
            command, env=env, stdout=output, stderr=output, start_new_session=True
        )
    pidfile.write_text(str(process.pid))
    print(
        f"Started own Qwen process {process.pid} on GPU {args.gpu}; endpoint 127.0.0.1:18080"
    )


if __name__ == "__main__":
    main()
