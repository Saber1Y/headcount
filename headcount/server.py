"""Scan runner for a free Render web service.

A free Render service sleeps after 15 minutes without inbound traffic and has no
cron, so an outside scheduler POSTs /run once a day. The runner then:

1. clones or updates the repository in a work folder,
2. runs `python3 -m headcount all` there,
3. commits the new snapshot and pushes it to GitHub,

and pings its own public URL every few minutes while the scan runs, so Render
does not put it to sleep halfway. Between runs it sleeps and uses no free hours.

Environment:
  RUN_TOKEN           bearer token the scheduler must send to start a run
  GITHUB_TOKEN        fine-grained token with Contents read/write on the repository
  GITHUB_REPOSITORY   owner/name, default Saber1Y/headcount
  RENDER_EXTERNAL_URL set by Render; the URL the keep-alive pings
  HEADCOUNT_WORKDIR   where the repository is cloned, default /tmp/headcount-work
"""

from __future__ import annotations

import base64
import hmac
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .http import HttpError, fetch

SCAN_TIMEOUT_SECONDS = 4 * 3600
KEEPALIVE_SECONDS = 300


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_env(token: str) -> dict[str, str]:
    """Environment that authenticates git over HTTPS without putting the token in argv or a URL."""
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
        "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {basic}",
        "GIT_AUTHOR_NAME": "headcount-bot",
        "GIT_AUTHOR_EMAIL": "headcount-bot@users.noreply.github.com",
        "GIT_COMMITTER_NAME": "headcount-bot",
        "GIT_COMMITTER_EMAIL": "headcount-bot@users.noreply.github.com",
    }


def redact(text: str, *secrets: str) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


class Runner:
    """Runs one scan at a time in a background thread and remembers how the last one went."""

    def __init__(
        self,
        *,
        repo: str,
        github_token: str,
        workdir: Path,
        keepalive_url: str = "",
        steps: Callable[[], str] | None = None,
        remote_url: str | None = None,
        scan_cmd: list[str] | None = None,
    ) -> None:
        self.repo = repo
        self.github_token = github_token
        self.workdir = workdir
        self.keepalive_url = keepalive_url.rstrip("/")
        self.remote_url = remote_url or f"https://github.com/{repo}.git"
        self.scan_cmd = scan_cmd or [sys.executable, "-m", "headcount", "all"]
        self.steps = steps or self._scan_and_publish
        self._lock = threading.Lock()
        self.state: dict[str, str | None] = {
            "status": "idle",
            "started_at": None,
            "finished_at": None,
            "message": None,
        }

    @property
    def running(self) -> bool:
        return self.state["status"] == "running"

    def start(self) -> bool:
        """Start a scan unless one is already running. Returns whether it started."""
        with self._lock:
            if self.running:
                return False
            self.state = {"status": "running", "started_at": now_iso(), "finished_at": None, "message": None}
        threading.Thread(target=self._run, daemon=True).start()
        if self.keepalive_url:
            threading.Thread(target=self._keep_awake, daemon=True).start()
        return True

    def _run(self) -> None:
        try:
            message = self.steps()
            status = "succeeded"
        except Exception as exc:  # noqa: BLE001 - any failure ends the run; the message is reported on /health
            message = redact(str(exc), self.github_token)[:800]
            status = "failed"
        print(f"scan {status}: {message}", flush=True)
        with self._lock:
            self.state = {**self.state, "status": status, "finished_at": now_iso(), "message": message}

    def _keep_awake(self) -> None:
        while self.running:
            try:
                fetch(f"{self.keepalive_url}/health", timeout=30)
            except HttpError:
                pass
            for _ in range(KEEPALIVE_SECONDS):
                if not self.running:
                    return
                time.sleep(1)

    def _git(self, *args: str, cwd: Path | None = None) -> str:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd or self.repo_dir,
            env=git_env(self.github_token),
            capture_output=True,
            text=True,
            timeout=600,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git {args[0]} failed: {redact(proc.stderr.strip(), self.github_token)}")
        return proc.stdout.strip()

    @property
    def repo_dir(self) -> Path:
        return self.workdir / "repo"

    def _scan_and_publish(self) -> str:
        if not self.github_token:
            raise RuntimeError("GITHUB_TOKEN is not set")
        self.workdir.mkdir(parents=True, exist_ok=True)
        if (self.repo_dir / ".git").exists():
            self._git("fetch", "--depth", "50", "origin", "main")
            self._git("reset", "--hard", "origin/main")
        else:
            self._git("clone", "--depth", "50", "--branch", "main", self.remote_url, str(self.repo_dir), cwd=self.workdir)

        subprocess.run(self.scan_cmd, cwd=self.repo_dir, check=True, timeout=SCAN_TIMEOUT_SECONDS)

        self._git("add", "snapshots")
        if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=self.repo_dir).returncode == 0:
            return "scan finished; snapshot unchanged"
        date = json.loads((self.repo_dir / "snapshots" / "index.json").read_text())[0]["date"]
        self._git("commit", "-m", f"Add snapshot {date}")
        try:
            self._git("push", "origin", "HEAD:main")
        except RuntimeError:
            # Someone pushed meanwhile: replay the snapshot commit on top and try once more.
            self._git("pull", "--rebase", "--depth", "50", "origin", "main")
            self._git("push", "origin", "HEAD:main")
        return f"pushed snapshot {date}"


def make_handler(runner: Runner, run_token: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802 - http.server naming
            if self.path in ("/", "/health"):
                self._send(200, {"service": "headcount-runner", **runner.state})
            else:
                self._send(404, {"error": "not found"})

        def do_HEAD(self) -> None:  # noqa: N802
            self.send_response(200 if self.path in ("/", "/health") else 404)
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/run":
                self._send(404, {"error": "not found"})
                return
            if not run_token:
                self._send(503, {"error": "RUN_TOKEN is not set on the server"})
                return
            given = self.headers.get("authorization", "").removeprefix("Bearer ").strip()
            if not hmac.compare_digest(given.encode(), run_token.encode()):
                self._send(401, {"error": "missing or wrong token"})
                return
            if runner.start():
                self._send(202, {"started": True, **runner.state})
            else:
                self._send(409, {"started": False, "error": "a scan is already running", **runner.state})

        def log_message(self, fmt: str, *args: object) -> None:
            # One line per request without headers, so tokens never reach the logs.
            print(f"{self.command} {self.path} -> {args[1] if len(args) > 1 else ''}", flush=True)

    return Handler


def main() -> None:
    runner = Runner(
        repo=os.environ.get("GITHUB_REPOSITORY", "Saber1Y/headcount"),
        github_token=os.environ.get("GITHUB_TOKEN", ""),
        workdir=Path(os.environ.get("HEADCOUNT_WORKDIR", "/tmp/headcount-work")),
        keepalive_url=os.environ.get("RENDER_EXTERNAL_URL", ""),
    )
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), make_handler(runner, os.environ.get("RUN_TOKEN", "")))
    print(f"headcount-runner listening on {port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
