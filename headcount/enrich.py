"""Add chain context the sample alone lacks.

- Lifetime transaction counts for every sampled sender (RPC nonce).
- Which sampled targets are contracts (RPC code), and for those the explorer's
  contract name, token name, verification status and deployer.

Results are cached in data/ so a rerun only fetches what is missing.
"""

from __future__ import annotations

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .http import HttpError, explorer_json, rpc_batch

# Contract metadata is fetched for targets with at least this many sampled txs;
# rarer targets are reported together as the long tail.
META_MIN_TXS = 3


def load_txs(data: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted((data / "windows").glob("w*.jsonl")):
        rows += [json.loads(line) for line in path.open()]
    return rows


def _cache(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _batched(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def nonces(addresses: list[str], cache: dict) -> dict:
    todo = [a for a in addresses if a not in cache]

    def job(part: list[str]) -> dict:
        res = rpc_batch([("eth_getTransactionCount", [a, "latest"]) for a in part])
        return {a: int(r, 16) for a, r in zip(part, res)}

    with ThreadPoolExecutor(3) as pool:
        for got in pool.map(job, _batched(todo, 100)):
            cache.update(got)
    return cache


def code_presence(addresses: list[str], cache: dict) -> dict:
    todo = [a for a in addresses if a not in cache]

    def job(part: list[str]) -> dict:
        res = rpc_batch([("eth_getCode", [a, "latest"]) for a in part])
        return {a: r not in (None, "0x") for a, r in zip(part, res)}

    with ThreadPoolExecutor(3) as pool:
        for got in pool.map(job, _batched(todo, 100)):
            cache.update(got)
    return cache


def contract_meta(address: str) -> dict:
    try:
        d = explorer_json(f"/addresses/{address}") or {}
    except HttpError as exc:
        return {"error": str(exc)}
    token = d.get("token") or {}
    return {
        "name": d.get("name"),
        "verified": bool(d.get("is_verified")),
        "creator": (d.get("creator_address_hash") or "").lower() or None,
        "token_name": token.get("name"),
        "token_symbol": token.get("symbol"),
    }


def run(data: Path) -> None:
    txs = load_txs(data)
    senders = sorted({t["f"] for t in txs})
    targets = Counter(t["t"] for t in txs if t["t"])
    busy = sorted(a for a, c in targets.items() if c >= META_MIN_TXS)
    print(f"{len(txs)} txs, {len(senders)} senders, {len(targets)} targets, {len(busy)} busy targets")

    n_path, c_path, m_path = data / "nonces.json", data / "code.json", data / "meta.json"
    n = nonces(senders, _cache(n_path))
    n_path.write_text(json.dumps(n))
    print(f"nonces: {len(n)}")
    c = code_presence(busy, _cache(c_path))
    c_path.write_text(json.dumps(c))
    contracts = [a for a in busy if c.get(a)]
    print(f"contracts among busy targets: {len(contracts)}")

    meta = _cache(m_path)
    todo = [a for a in contracts if a not in meta or "error" in meta[a]]
    with ThreadPoolExecutor(4) as pool:
        for addr, info in zip(todo, pool.map(contract_meta, todo)):
            meta[addr] = info
    m_path.write_text(json.dumps(meta, indent=1))
    failed = sum(1 for v in meta.values() if "error" in v)
    print(f"explorer metadata: {len(meta)} contracts, {failed} lookups failed")
