"""Combine the sample, app attribution and wallet signals into report.json."""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from . import signals
from .attribute import attribute
from .enrich import load_txs
from .http import HttpError, fetch

EXPLORER = "https://liteforge.explorer.caldera.xyz"
LABELS = (signals.LIKELY, signals.POSSIBLE, signals.NONE)


def selector_names(selectors: list[str], cache_path: Path) -> dict[str, str]:
    """Best-effort function names from the public 4byte directory."""
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    for sel in selectors:
        if sel in cache or len(sel) != 10:
            continue
        try:
            status, body = fetch(f"https://www.4byte.directory/api/v1/signatures/?hex_signature={sel}")
            results = json.loads(body).get("results", []) if status == 200 else []
            # The oldest registration is usually the real one; later ones are often collisions.
            cache[sel] = min(results, key=lambda r: r["id"])["text_signature"] if results else ""
        except (HttpError, json.JSONDecodeError, KeyError):
            continue
    cache_path.write_text(json.dumps(cache, indent=1))
    return cache


def _split(counter: Counter) -> dict[str, int]:
    return {label: counter.get(label, 0) for label in LABELS}


def run(data: Path) -> None:
    plan = json.loads((data / "windows" / "plan.json").read_text())
    txs = load_txs(data)
    apps = json.loads((data / "apps.json").read_text())
    nonces = json.loads((data / "nonces.json").read_text())
    code = json.loads((data / "code.json").read_text())
    meta = json.loads((data / "meta.json").read_text())

    wallets = signals.build_wallets(txs)
    for addr, w in wallets.items():
        w.lifetime_txs = nonces.get(addr)
    label_of = {a: w.label() for a, w in wallets.items()}

    sampled_blocks = len(plan["windows"]) * plan["blocks_per_window"]
    span_blocks = plan["head"] - plan["windows"][0]["first"]
    span_seconds = plan["head_ts"] - plan["start_ts"]
    blocks_per_day = span_blocks / span_seconds * 86400
    scale = blocks_per_day / sampled_blocks

    targets = Counter(t["t"] for t in txs if t["t"])
    contracts = {a for a in targets if code.get(a)}
    app_addresses = {a["id"]: set(a["frontend"]["addresses"]) for a in apps}
    app_names = {a["id"]: a["name"] for a in apps}
    attr = attribute(contracts, app_addresses, app_names, meta)

    by_app: dict[str, list[dict]] = defaultdict(list)
    groups: dict[str, list[dict]] = defaultdict(list)
    buckets = Counter()
    for tx in txs:
        t = tx["t"]
        if t is None:
            buckets["contract_creation"] += 1
        elif t in attr and attr[t].app:
            by_app[attr[t].app].append(tx)
        elif t in attr and attr[t].rule == "shared":
            buckets["shared_contract"] += 1
            groups["shared:" + t].append(tx)
        elif t in contracts:
            creator = (meta.get(t) or {}).get("creator")
            # Without a known deployer, a contract is its own group: never pool unrelated ones.
            groups["deployer:" + creator if creator else "contract:" + t].append(tx)
        elif code.get(t) is False:
            buckets["transfer_to_wallet"] += 1
        else:
            buckets["long_tail"] += 1

    def summarize(rows: list[dict]) -> dict:
        lt = Counter(label_of[r["f"]] for r in rows)
        senders = {r["f"] for r in rows}
        lw = Counter(label_of[s] for s in senders)
        flags = Counter(f for s in senders for f in wallets[s].flags())
        per_sender = Counter(r["f"] for r in rows)
        evidence = []
        for label in (signals.LIKELY, signals.NONE):
            picks = [s for s, _ in per_sender.most_common() if label_of[s] == label][:3]
            for s in picks:
                w = wallets[s]
                tx_hash = next(r["h"] for r in rows if r["f"] == s)
                evidence.append(
                    {
                        "wallet": s,
                        "label": label,
                        "flags": w.flags(),
                        "lifetime_txs": w.lifetime_txs,
                        "sampled_txs": per_sender[s],
                        "hours_active": len(w.hours),
                        "max_in_window": w.max_in_window,
                        "tx": tx_hash,
                    }
                )
        return {
            "sampled_txs": len(rows),
            "est_daily_txs": round(len(rows) * scale),
            "wallets": len(senders),
            "txs_by_label": _split(lt),
            "wallets_by_label": _split(lw),
            "flag_counts": dict(flags.most_common()),
            "selectors": Counter(r["sel"] for r in rows).most_common(4),
            "evidence": evidence,
        }

    app_rows = []
    for app in apps:
        rows = by_app.get(app["id"], [])
        mine = sorted((a for a, at in attr.items() if at.app == app["id"]), key=lambda a: -targets[a])
        app_rows.append(
            {
                "id": app["id"],
                "name": app["name"],
                "tag": app["tag"],
                "url": app["url"],
                "frontend_status": app["frontend"]["status"],
                "frontend_addresses": len(app["frontend"]["addresses"]),
                "contracts": [
                    {
                        "address": a,
                        "rule": attr[a].rule,
                        "name": (meta.get(a) or {}).get("name") or (meta.get(a) or {}).get("token_name"),
                        "sampled_txs": targets[a],
                    }
                    for a in mine[:8]
                ],
                **summarize(rows),
            }
        )
    app_rows.sort(key=lambda r: -r["sampled_txs"])

    group_rows = []
    for key, rows in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:25]:
        kind, _, who = key.partition(":")
        addrs = Counter(r["t"] for r in rows)
        group_rows.append(
            {
                "kind": kind,
                "key": who,
                "contracts": [
                    {
                        "address": a,
                        "name": (meta.get(a) or {}).get("name") or (meta.get(a) or {}).get("token_name"),
                        "verified": (meta.get(a) or {}).get("verified"),
                        "sampled_txs": c,
                    }
                    for a, c in addrs.most_common(5)
                ],
                **summarize(rows),
            }
        )

    chain = summarize(txs)
    chain.pop("evidence")
    # The single busiest contract, compared with everything else: its traffic and its senders.
    top_target, top_count = targets.most_common(1)[0]
    per_window: dict[int, Counter] = defaultdict(Counter)
    window_ts: dict[int, int] = {}
    windows_of: dict[str, set[int]] = defaultdict(set)
    for tx in txs:
        per_window[tx["w"]][label_of[tx["f"]]] += 1
        per_window[tx["w"]]["top_contract" if tx["t"] == top_target else "everything_else"] += 1
        window_ts[tx["w"]] = min(window_ts.get(tx["w"], tx["ts"]), tx["ts"])
        windows_of[tx["f"]].add(tx["w"])
    windows = [
        {
            "window": w,
            "ts": window_ts[w],
            **_split(per_window[w]),
            "top_contract": per_window[w]["top_contract"],
            "everything_else": per_window[w]["everything_else"],
        }
        for w in sorted(per_window)
    ]

    def median(values: list[int]) -> int:
        values = sorted(values)
        return values[len(values) // 2] if values else 0

    top_senders = {tx["f"] for tx in txs if tx["t"] == top_target}
    cohorts = []
    for name, group in (("top_contract", top_senders), ("everyone_else", set(wallets) - top_senders)):
        lw = Counter(label_of[a] for a in group)
        cohorts.append(
            {
                "cohort": name,
                "wallets": len(group),
                "median_lifetime_txs": median([wallets[a].lifetime_txs or 0 for a in group]),
                "median_sampled_txs": median([wallets[a].txs for a in group]),
                "median_windows_active": median([len(windows_of[a]) for a in group]),
                "wallets_by_label": _split(lw),
            }
        )
    top_meta = meta.get(top_target) or {}
    top_contract = {
        "address": top_target,
        "sampled_txs": top_count,
        "share_of_txs": round(top_count / len(txs), 4),
        "name": top_meta.get("name") or top_meta.get("token_name"),
        "verified": bool(top_meta.get("verified")),
        "creator": top_meta.get("creator"),
        "attributed_to": attr[top_target].app if top_target in attr else None,
        "top_call": Counter(tx["sel"] for tx in txs if tx["t"] == top_target).most_common(1)[0][0],
    }
    sels = sorted({s for r in app_rows + group_rows for s, _ in r["selectors"]} | {top_contract["top_call"]})
    names = selector_names(sels, data / "selectors.json")
    report = {
        "generated": int(time.time()),
        "sample": {
            "windows": len(plan["windows"]),
            "blocks_per_window": plan["blocks_per_window"],
            "sampled_blocks": sampled_blocks,
            "span_hours": round(span_seconds / 3600, 2),
            "start_ts": plan["start_ts"],
            "end_ts": plan["head_ts"],
            "head_block": plan["head"],
            "est_blocks_per_day": round(blocks_per_day),
            "scale": round(scale, 2),
            "transactions": len(txs),
        },
        "flags": signals.FLAGS,
        "thresholds": {
            "high_volume": signals.HIGH_VOLUME,
            "round_the_clock_hours": signals.ROUND_THE_CLOCK_HOURS,
            "burst_in_window": signals.BURST_IN_WINDOW,
            "repeat_share": signals.REPEAT_SHARE,
            "repeat_min_txs": signals.REPEAT_MIN_TXS,
        },
        "chain": chain,
        "windows": windows,
        "top_contract": top_contract,
        "cohorts": cohorts,
        "buckets": dict(buckets),
        "attributed_txs": sum(len(v) for v in by_app.values()),
        "attribution_rules": dict(Counter(a.rule for a in attr.values())),
        "apps": app_rows,
        "unattributed_groups": group_rows,
        "selector_names": {s: names.get(s, "") for s in sels},
        "explorer": EXPLORER,
    }
    (data / "report.json").write_text(json.dumps(report, indent=1))
    print(f"report: {len(txs)} txs, {report['attributed_txs']} attributed to {sum(1 for r in app_rows if r['sampled_txs'])} apps")
