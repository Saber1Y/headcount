import base64
import json
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError

from headcount.server import Runner, git_env, make_handler, redact

TOKEN = "run-secret"


class FakeScan:
    """Stands in for the real scan: blocks until released, then succeeds or fails."""

    def __init__(self, fail: bool = False) -> None:
        self.release = threading.Event()
        self.calls = 0
        self.fail = fail

    def __call__(self) -> str:
        self.calls += 1
        self.release.wait(5)
        if self.fail:
            raise RuntimeError("push failed for ghp_secret")
        return "pushed snapshot 2026-11-09"


class Server:
    def __init__(self, runner: Runner) -> None:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(runner, TOKEN))
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def request(self, method: str, path: str, token: str | None = None) -> tuple[int, dict]:
        req = urllib.request.Request(self.url + path, method=method)
        if token is not None:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def wait_for(predicate, seconds: float = 5) -> None:
    deadline = time.time() + seconds
    while not predicate():
        if time.time() > deadline:
            raise AssertionError("timed out")
        time.sleep(0.01)


class RunEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.scan = FakeScan()
        self.runner = Runner(repo="o/r", github_token="ghp_secret", workdir=Path(tempfile.mkdtemp()), steps=self.scan)
        self.server = Server(self.runner)

    def tearDown(self) -> None:
        self.scan.release.set()
        self.server.close()

    def test_rejects_missing_and_wrong_tokens(self):
        self.assertEqual(self.server.request("POST", "/run")[0], 401)
        self.assertEqual(self.server.request("POST", "/run", "nope")[0], 401)
        self.assertEqual(self.scan.calls, 0)

    def test_starts_once_and_refuses_a_second_run_while_busy(self):
        code, body = self.server.request("POST", "/run", TOKEN)
        self.assertEqual((code, body["status"]), (202, "running"))
        wait_for(lambda: self.scan.calls == 1)
        self.assertEqual(self.server.request("POST", "/run", TOKEN)[0], 409)
        self.scan.release.set()
        wait_for(lambda: self.runner.state["status"] == "succeeded")
        code, body = self.server.request("GET", "/health")
        self.assertEqual(code, 200)
        self.assertEqual(body["message"], "pushed snapshot 2026-11-09")
        self.assertIsNotNone(body["finished_at"])

    def test_unknown_paths_are_404(self):
        self.assertEqual(self.server.request("GET", "/run")[0], 404)
        self.assertEqual(self.server.request("POST", "/health", TOKEN)[0], 404)


class Failures(unittest.TestCase):
    def test_failed_scan_reports_without_the_github_token(self):
        scan = FakeScan(fail=True)
        scan.release.set()
        runner = Runner(repo="o/r", github_token="ghp_secret", workdir=Path(tempfile.mkdtemp()), steps=scan)
        self.assertTrue(runner.start())
        wait_for(lambda: runner.state["status"] == "failed")
        self.assertIn("[redacted]", runner.state["message"])
        self.assertNotIn("ghp_secret", runner.state["message"])

    def test_server_without_run_token_refuses_runs(self):
        runner = Runner(repo="o/r", github_token="", workdir=Path(tempfile.mkdtemp()), steps=FakeScan())
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(runner, ""))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{httpd.server_address[1]}/run", method="POST")
            req.add_header("Authorization", "Bearer ")
            with self.assertRaises(HTTPError) as ctx:
                urllib.request.urlopen(req, timeout=5)
            self.assertEqual(ctx.exception.code, 503)
        finally:
            httpd.shutdown()
            httpd.server_close()


def git(*args: str, cwd: Path) -> str:
    import subprocess

    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


# Stands in for `python3 -m headcount all`: writes a new dated snapshot and index.
FAKE_SCAN = (
    "import json, pathlib; p = pathlib.Path('snapshots/2026-11-10'); p.mkdir(parents=True, exist_ok=True); "
    "(p / 'meta.json').write_text('{}'); "
    "pathlib.Path('snapshots/index.json').write_text(json.dumps([{'date': '2026-11-10'}]))"
)


class PublishFlow(unittest.TestCase):
    """The real clone, scan, commit and push path, against a local bare repository."""

    def setUp(self) -> None:
        import sys

        self.tmp = Path(tempfile.mkdtemp())
        self.origin = self.tmp / "origin.git"
        seed = self.tmp / "seed"
        git("init", "-q", "--bare", "-b", "main", str(self.origin), cwd=self.tmp)
        git("init", "-q", "-b", "main", str(seed), cwd=self.tmp)
        (seed / "snapshots").mkdir()
        (seed / "snapshots" / "index.json").write_text("[]")
        git("add", ".", cwd=seed)
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "seed", cwd=seed)
        git("push", "-q", str(self.origin), "main", cwd=seed)
        self.runner = Runner(
            repo="o/r",
            github_token="ghp_secret",
            workdir=self.tmp / "work",
            remote_url=str(self.origin),
            scan_cmd=[sys.executable, "-c", FAKE_SCAN],
        )

    def test_clones_scans_commits_and_pushes_the_snapshot(self):
        self.assertEqual(self.runner._scan_and_publish(), "pushed snapshot 2026-11-10")
        log = git("log", "--format=%s|%an", "main", cwd=self.origin)
        self.assertEqual(log.splitlines()[0], "Add snapshot 2026-11-10|headcount-bot")

    def test_second_run_reuses_the_clone_and_reports_no_change(self):
        self.runner._scan_and_publish()
        self.assertEqual(self.runner._scan_and_publish(), "scan finished; snapshot unchanged")
        self.assertEqual(len(git("log", "--format=%s", "main", cwd=self.origin).splitlines()), 2)

    def test_refuses_to_run_without_a_github_token(self):
        self.runner.github_token = ""
        with self.assertRaisesRegex(RuntimeError, "GITHUB_TOKEN is not set"):
            self.runner._scan_and_publish()


class GitAuth(unittest.TestCase):
    def test_token_travels_in_an_encoded_header_not_in_plain_text(self):
        env = git_env("ghp_secret")
        self.assertEqual(env["GIT_CONFIG_KEY_0"], "http.https://github.com/.extraheader")
        encoded = env["GIT_CONFIG_VALUE_0"].removeprefix("AUTHORIZATION: basic ")
        self.assertEqual(base64.b64decode(encoded).decode(), "x-access-token:ghp_secret")
        self.assertNotIn("ghp_secret", env["GIT_CONFIG_VALUE_0"])
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")

    def test_redact_removes_every_secret(self):
        self.assertEqual(redact("a ghp_x b ghp_x", "ghp_x", ""), "a [redacted] b [redacted]")


if __name__ == "__main__":
    unittest.main()
