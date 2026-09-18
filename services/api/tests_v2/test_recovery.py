import json
import os
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
from sqlalchemy import func, select

from commerceflow.db import transaction
from commerceflow.models import BusinessResult, Execution, Job, Ticket
from tests_v2.test_integration import approved_execution


def test_worker_process_death_after_remote_commit_recovers_once(clients, tmp_path):
    """Real HTTP/MCP/PostgreSQL. Kill an owned process after remote commit, not a mock exception."""
    _, _, execution_id = approved_execution(clients)
    committed = threading.Event()
    release = threading.Event()

    class Proxy(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def forward(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else None
            headers = {
                k: v
                for k, v in self.headers.items()
                if k.lower() not in {"host", "content-length", "connection"}
            }
            with httpx.Client(timeout=20, trust_env=False) as client:
                response = client.request(
                    self.command,
                    "http://127.0.0.1:18001" + self.path,
                    headers=headers,
                    content=body,
                )
            if (
                self.command == "POST"
                and self.path == "/executions"
                and response.status_code == 200
            ):
                committed.set()
                release.wait(30)
                return  # Deliberately lose the reply after committing in the real commerce service.
            self.send_response(response.status_code)
            self.send_header(
                "Content-Type", response.headers.get("content-type", "application/json")
            )
            self.send_header("Content-Length", str(len(response.content)))
            self.end_headers()
            self.wfile.write(response.content)

        do_GET = forward
        do_POST = forward
        do_DELETE = forward

    proxy = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    processes = []

    def start_worker(name, commerce_url):
        pidfile = tmp_path / (name + ".pid")
        code = (
            "import os; from pathlib import Path; "
            "Path(os.environ['TEST_PID_FILE']).write_text(str(os.getpid())); "
            "from commerceflow.worker import main; main()"
        )
        env = {
            **os.environ,
            "CF_COMMERCE_URL": commerce_url,
            "CF_JOB_LEASE_SECONDS": "2",
            "TEST_PID_FILE": str(pidfile),
        }
        output = (tmp_path / (name + ".log")).open("w")
        process = subprocess.Popen(
            [sys.executable, "-c", code], env=env, stdout=output, stderr=output
        )
        processes.append((process, pidfile, output))
        return process, pidfile

    try:
        first, pidfile = start_worker("first", f"http://127.0.0.1:{proxy.server_port}")
        assert committed.wait(45), "Worker never committed the remote business operation"
        os.kill(int(pidfile.read_text()), signal.SIGTERM)
        first.wait(timeout=15)
        release.set()
        with transaction() as session:
            assert session.get(Execution, execution_id).status == "queued"
        with transaction(True) as session:
            assert session.scalar(select(func.count()).select_from(BusinessResult)) == 1
        start_worker("replacement", "http://127.0.0.1:18001")
        for _ in range(100):
            with transaction() as session:
                execution = session.get(Execution, execution_id)
                job = session.scalar(select(Job).where(Job.reference_id == execution_id))
                if execution.status == "succeeded" and job.status == "completed":
                    break
            time.sleep(0.2)
        else:
            raise AssertionError("Replacement worker failed to recover")
        with transaction(True) as session:
            assert session.scalar(select(func.count()).select_from(BusinessResult)) == 1
            assert session.scalar(select(func.count()).select_from(Ticket)) == 1
        artifact = Path(__file__).resolve().parents[3] / "data/local/recovery-proof.json"
        artifact.write_text(
            json.dumps(
                {
                    "test": "kill_after_remote_commit",
                    "execution_id": execution_id,
                    "worker_attempts": job.attempts,
                    "business_results": 1,
                    "tickets": 1,
                    "status": execution.status,
                },
                indent=2,
            )
        )
    finally:
        release.set()
        proxy.shutdown()
        proxy.server_close()
        for process, pidfile, output in processes:
            if process.poll() is None:
                if pidfile.exists():
                    os.kill(int(pidfile.read_text()), signal.SIGTERM)
                process.wait(timeout=15)
            output.close()
