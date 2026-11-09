"""Sample LiteForge transactions in evenly spaced windows across a time span.

Reading every block of a day (~345k blocks) through the public RPC takes most
of a day, so the scan reads a fixed number of consecutive blocks at regular
intervals instead. Each window is stored as its own file so an interrupted run
resumes where it stopped.
"""

from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from .http import rpc, rpc_batch

# Arbitrum system transactions (deposits, retryables, internal) are not user activity.
USER_TX_TYPES = {"0x0", "0x1", "0x2", "0x4"}


@dataclass(frozen=True)
class Plan:
    windows: int = 48
    blocks_per_window: int = 120
    span_hours: float = 24.0
    chunk: int = 40
    workers: int = 4


def block_time(number: int) -> int:
    return int(rpc("eth_getBlockByNumber", [hex(number), False])["timestamp"], 16)


def block_at(ts: int, lo: int, lo_ts: int, hi: int, hi_ts: int, tolerance: int = 20) -> int:
    """Return a block whose timestamp is within `tolerance` seconds of ts.

    Interpolation search: block production is close to uniform on LiteForge, so
    a few secant steps land near the target with far fewer calls than bisection.
    """
    for _ in range(12):
        if hi - lo <= 1 or hi_ts == lo_ts:
            return lo
        guess = lo + int((ts - lo_ts) * (hi - lo) / (hi_ts - lo_ts))
        guess = min(max(guess, lo + 1), hi - 1)
        g_ts = block_time(guess)
        if abs(g_ts - ts) <= tolerance:
            return guess
        if g_ts < ts:
            lo, lo_ts = guess, g_ts
        else:
            hi, hi_ts = guess, g_ts
    return lo


def compact(tx: dict, window: int, ts: int) -> dict:
    data = tx.get("input") or "0x"
    return {
        "w": window,
        "b": int(tx["blockNumber"], 16),
        "ts": ts,
        "h": tx["hash"],
        "f": tx["from"].lower(),
        "t": (tx.get("to") or "").lower() or None,
        "n": int(tx["nonce"], 16),
        "sel": data[:10],
        "cd": hashlib.sha1(data.encode()).hexdigest()[:12],
        "v": int(tx.get("value") or "0x0", 16) > 0,
        "gp": tx.get("gasPrice"),
    }


def fetch_window(window: int, first: int, plan: Plan, out: Path) -> int:
    path = out / f"w{window:03d}.jsonl"
    if path.exists():
        return sum(1 for _ in path.open())
    rows: list[dict] = []
    numbers = list(range(first, first + plan.blocks_per_window))
    for i in range(0, len(numbers), plan.chunk):
        part = numbers[i : i + plan.chunk]
        blocks = rpc_batch([("eth_getBlockByNumber", [hex(n), True]) for n in part])
        for blk in blocks:
            ts = int(blk["timestamp"], 16)
            rows += [compact(t, window, ts) for t in blk["transactions"] if t.get("type") in USER_TX_TYPES]
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r) + "\n" for r in rows))
    tmp.rename(path)
    return len(rows)


def run(out: Path, plan: Plan = Plan()) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    meta_path = out / "plan.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
    else:
        head = int(rpc("eth_blockNumber", []), 16)
        head_ts = block_time(head)
        start_ts = head_ts - int(plan.span_hours * 3600)
        step = int(plan.span_hours * 3600 / plan.windows)
        targets = [start_ts + k * step for k in range(plan.windows)]
        lo = max(0, head - int(plan.span_hours * 3600 * 6))
        lo_ts = block_time(lo)
        if lo_ts > start_ts:
            lo, lo_ts = 0, block_time(0)
        firsts = [block_at(t, lo, lo_ts, head, head_ts) for t in targets]
        meta = {
            "head": head,
            "head_ts": head_ts,
            "start_ts": start_ts,
            "windows": [{"w": k, "first": f, "target_ts": t} for k, (f, t) in enumerate(zip(firsts, targets))],
            "blocks_per_window": plan.blocks_per_window,
            "created": int(time.time()),
        }
        meta_path.write_text(json.dumps(meta, indent=1))
    with ThreadPoolExecutor(plan.workers) as pool:
        counts = list(
            pool.map(lambda w: fetch_window(w["w"], w["first"], plan, out), meta["windows"])
        )
    for w, c in zip(meta["windows"], counts):
        print(f"window {w['w']:02d} block {w['first']} txs {c}", flush=True)
    return meta
