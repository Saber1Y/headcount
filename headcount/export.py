"""Flatten report.json into row files the report page reads (data/out/*.json)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import signals

LABELS = (signals.LIKELY, signals.POSSIBLE, signals.NONE)
LABEL_NAMES = {signals.LIKELY: "Likely scripted", signals.POSSIBLE: "Possibly scripted", signals.NONE: "No signals"}
SIGNAL_NAMES = {
    "high_volume": "Very high volume",
    "round_the_clock": "Round the clock",
    "burst": "Bursts",
    "repeat": "One repeated call",
}


def _shares(counts: dict[str, int]) -> dict[str, float]:
    total = sum(counts.values())
    return {f"share_{k}": round(counts[k] / total, 4) if total else 0.0 for k in LABELS}


ACRONYMS = {"DEX", "NFT", "AI", "RPC", "RWA", "LP", "RWAS"}


def category(tag: str | None) -> str:
    """Sentence-case a hub tag ("DEX AGGREGATOR" -> "DEX aggregator"), keeping acronyms."""
    words = []
    for i, word in enumerate((tag or "").split()):
        if word in ACRONYMS:
            words.append(word)
        elif word == "DEFI":
            words.append("DeFi")
        else:
            words.append(word.capitalize() if i == 0 else word.lower())
    return " ".join(words)


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(data: Path) -> Path:
    r = json.loads((data / "report.json").read_text())
    out = data / "out"
    out.mkdir(exist_ok=True)
    s, chain, names = r["sample"], r["chain"], r["selector_names"]
    app_names = {a["id"]: a["name"] for a in r["apps"]}

    def fn_name(sel_counts: list) -> str:
        if not sel_counts:
            return ""
        sel = sel_counts[0][0]
        return (names.get(sel) or sel).split("(")[0]

    summary = [
        {
            "window_start": _iso(s["start_ts"]),
            "window_end": _iso(s["end_ts"]),
            "span_hours": s["span_hours"],
            "windows": s["windows"],
            "blocks_per_window": s["blocks_per_window"],
            "sampled_blocks": s["sampled_blocks"],
            "est_blocks_per_day": s["est_blocks_per_day"],
            "sample_share_of_day": round(s["sampled_blocks"] / s["est_blocks_per_day"], 4),
            "sampled_txs": chain["sampled_txs"],
            "est_daily_txs": chain["est_daily_txs"],
            "wallets": chain["wallets"],
            "wallets_likely": chain["wallets_by_label"][signals.LIKELY],
            "wallets_possible": chain["wallets_by_label"][signals.POSSIBLE],
            "wallets_none": chain["wallets_by_label"][signals.NONE],
            **_shares(chain["txs_by_label"]),
            "attributed_txs": r["attributed_txs"],
            "share_attributed": round(r["attributed_txs"] / chain["sampled_txs"], 4),
            "apps_listed": len(r["apps"]),
            "apps_seen": sum(1 for a in r["apps"] if a["sampled_txs"]),
            "apps_frontend_scanned": sum(1 for a in r["apps"] if a["frontend_addresses"]),
            "head_block": s["head_block"],
            "top_contract": r["top_contract"]["address"],
            "top_contract_share": r["top_contract"]["share_of_txs"],
            "top_contract_sampled_txs": r["top_contract"]["sampled_txs"],
            "top_contract_call": (names.get(r["top_contract"]["top_call"]) or r["top_contract"]["top_call"]).split("(")[0],
            "top_contract_source": "Verified" if r["top_contract"]["verified"] else "Unverified",
            "top_contract_app": app_names.get(r["top_contract"]["attributed_to"], "no hub app"),
        }
    ]

    cohort_names = {"top_contract": "Senders to the busiest contract", "everyone_else": "Every other wallet"}
    cohorts = [
        {
            "cohort": c["cohort"],
            "group": cohort_names[c["cohort"]],
            "wallets": c["wallets"],
            "median_lifetime_txs": c["median_lifetime_txs"],
            "median_sampled_txs": c["median_sampled_txs"],
            "median_windows_active": c["median_windows_active"],
            **{f"wallets_{k}": c["wallets_by_label"][k] for k in LABELS},
        }
        for c in r["cohorts"]
    ]

    apps = []
    for a in r["apps"]:
        rules = sorted({c["rule"] for c in a["contracts"]})
        apps.append(
            {
                "app": a["name"],
                "app_id": a["id"],
                "category": category(a["tag"]),
                "url": a["url"],
                "sampled_txs": a["sampled_txs"],
                "est_daily_txs": a["est_daily_txs"],
                "wallets": a["wallets"],
                **_shares(a["txs_by_label"]),
                "wallets_none": a["wallets_by_label"][signals.NONE],
                "contracts": len(a["contracts"]),
                "contract_list": [
                    {"address": c["address"], "rule": c["rule"], "name": c["name"] or "", "sampled_txs": c["sampled_txs"]}
                    for c in a["contracts"]
                ],
                "matched_by": ", ".join(rules) if rules else "not matched",
                "frontend": a["frontend_status"],
                "top_call": fn_name(a["selectors"]),
            }
        )

    groups = []
    for g in r["unattributed_groups"]:
        top = g["contracts"][0] if g["contracts"] else {}
        groups.append(
            {
                "group": g["key"],
                "kind": {"shared": "Shared contract", "deployer": "Same deployer"}.get(g["kind"], "Deployer unknown"),
                "top_contract": top.get("address", ""),
                "top_name": top.get("name") or "",
                "source_code": "Verified" if top.get("verified") else "Unverified",
                "contracts": len(g["contracts"]),
                "sampled_txs": g["sampled_txs"],
                "est_daily_txs": g["est_daily_txs"],
                "wallets": g["wallets"],
                **_shares(g["txs_by_label"]),
                "top_call": fn_name(g["selectors"]),
            }
        )

    evidence = []
    for a in r["apps"]:
        for e in a["evidence"]:
            evidence.append(
                {
                    "key": f"{a['id']}:{e['wallet']}",
                    "app_id": a["id"],
                    "app": a["name"],
                    "wallet": e["wallet"],
                    "label": e["label"],
                    "label_name": LABEL_NAMES[e["label"]],
                    "flags": ", ".join(signals.FLAGS[f] for f in e["flags"]) or "None",
                    "lifetime_txs": e["lifetime_txs"],
                    "sampled_txs": e["sampled_txs"],
                    "hours_active": e["hours_active"],
                    "max_in_window": e["max_in_window"],
                    "tx": e["tx"],
                }
            )

    flag_rows = [
        {"flag": k, "signal": SIGNAL_NAMES[k], "rule": text, "wallets": chain["flag_counts"].get(k, 0)}
        for k, text in signals.FLAGS.items()
    ]

    hourly = [
        {
            "window": w["window"],
            "start": _iso(w["ts"]),
            **{k: w[k] for k in LABELS},
            "top_contract": w["top_contract"],
            "everything_else": w["everything_else"],
        }
        for w in r["windows"]
    ]

    files = {
        "summary": summary,
        "apps": apps,
        "groups": groups,
        "evidence": evidence,
        "flags": flag_rows,
        "windows": hourly,
        "cohorts": cohorts,
    }
    for name, rows in files.items():
        (out / f"{name}.json").write_text(json.dumps(rows, indent=1))
        print(f"{name}: {len(rows)} rows")
    return out
