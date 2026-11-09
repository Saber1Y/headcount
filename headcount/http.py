"""HTTP and JSON-RPC access through the system curl binary.

The LiteForge RPC sits behind a proxy that rejects Python's default client,
so every request goes through curl, which the RPC accepts as-is.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from typing import Any

RPC_URL = os.environ.get("LITEFORGE_RPC", "https://liteforge.rpc.caldera.xyz/http")
EXPLORER_API = os.environ.get(
    "LITEFORGE_EXPLORER_API", "https://liteforge.explorer.caldera.xyz/api/v2"
)
# The public RPC answers 429 when pushed; space requests out across all threads.
RPC_MIN_INTERVAL = float(os.environ.get("LITEFORGE_RPC_INTERVAL", "0.35"))


class HttpError(RuntimeError):
    pass


class RateLimited(HttpError):
    pass


class _Pacer:
    def __init__(self, interval: float) -> None:
        self.interval = interval
        self.lock = threading.Lock()
        self.next_at = 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            delay = max(0.0, self.next_at - now)
            self.next_at = max(now, self.next_at) + self.interval
        if delay:
            time.sleep(delay)

    def back_off(self, seconds: float) -> None:
        with self.lock:
            self.next_at = max(self.next_at, time.monotonic() + seconds)


_rpc_pacer = _Pacer(RPC_MIN_INTERVAL)
_explorer_pacer = _Pacer(0.25)


def fetch(url: str, *, body: bytes | None = None, timeout: int = 60) -> tuple[int, bytes]:
    """Return (status, body) for a GET, or a JSON POST when body is given."""
    cmd = ["curl", "-s", "-m", str(timeout), "-w", "\n%{http_code}", url]
    if body is not None:
        cmd += ["-H", "content-type: application/json", "--data-binary", "@-"]
    proc = subprocess.run(cmd, input=body, capture_output=True, check=False)
    if proc.returncode != 0:
        raise HttpError(f"curl exit {proc.returncode} for {url}")
    payload, _, status = proc.stdout.rpartition(b"\n")
    return int(status or 0), payload


def explorer_json(path: str, *, retries: int = 4, timeout: int = 30) -> Any:
    """GET a LiteForge explorer API path, paced and retried."""
    url = EXPLORER_API + path
    last: Exception | None = None
    for attempt in range(retries):
        _explorer_pacer.wait()
        try:
            status, payload = fetch(url, timeout=timeout)
            if status == 200:
                return json.loads(payload)
            if status == 404:
                return None
            if status == 429:
                _explorer_pacer.back_off(10 * (attempt + 1))
            last = HttpError(f"HTTP {status} for {url}")
        except (HttpError, json.JSONDecodeError) as exc:
            last = exc
        time.sleep(1.5 * (attempt + 1))
    raise HttpError(str(last))


def rpc_batch(calls: list[tuple[str, list[Any]]], *, retries: int = 8, timeout: int = 120) -> list[Any]:
    """Run a JSON-RPC batch and return results in call order.

    Raises if any call in the batch still errors after retries, so callers never
    mistake a missing block for an empty one.
    """
    body = json.dumps(
        [{"jsonrpc": "2.0", "id": i, "method": m, "params": p} for i, (m, p) in enumerate(calls)]
    ).encode()
    last: Exception | None = None
    for attempt in range(retries):
        _rpc_pacer.wait()
        try:
            status, payload = fetch(RPC_URL, body=body, timeout=timeout)
            if status == 429:
                _rpc_pacer.back_off(10 * (attempt + 1))
                raise RateLimited("RPC HTTP 429")
            if status != 200:
                raise HttpError(f"RPC HTTP {status}")
            replies = json.loads(payload)
            if isinstance(replies, dict):
                raise HttpError(f"RPC error {replies.get('error')}")
            by_id = {r["id"]: r for r in replies}
            errors = [r["error"] for r in replies if "error" in r]
            if errors or len(by_id) != len(calls):
                raise HttpError(f"RPC batch incomplete: {errors[:1]}")
            return [by_id[i]["result"] for i in range(len(calls))]
        except (HttpError, json.JSONDecodeError, KeyError) as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise HttpError(str(last))


def rpc(method: str, params: list[Any]) -> Any:
    return rpc_batch([(method, params)])[0]
