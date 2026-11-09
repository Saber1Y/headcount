"""Per-wallet behaviour signals and the scripted-traffic classification.

Every flag is a plain rule with a stated threshold, so a report reader can check
why a wallet was labelled. The labels describe behaviour ("looks scripted"), not
intent: a developer's test script is scripted too.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Lifetime transactions above this mean ~49 a day, every day, since LiteForge
# opened on 2026-04-15: sustained manual signing at that rate is implausible.
HIGH_VOLUME = 10_000
# Seen in at least this many of the 24 UTC hours of the sample: no sleep pattern.
ROUND_THE_CLOCK_HOURS = 20
# Transactions sent inside one ~30 second window: one every 5 seconds or faster.
BURST_IN_WINDOW = 6
# Share of a wallet's sampled transactions that are the exact same call.
REPEAT_SHARE = 0.9
REPEAT_MIN_TXS = 10

FLAGS = {
    "high_volume": f"Over {HIGH_VOLUME:,} lifetime transactions",
    "round_the_clock": f"Active in {ROUND_THE_CLOCK_HOURS}+ of 24 hours",
    "burst": f"{BURST_IN_WINDOW}+ transactions inside one 30-second window",
    "repeat": f"{int(REPEAT_SHARE * 100)}%+ of transactions are one identical call",
}

LIKELY = "likely_scripted"
POSSIBLE = "possibly_scripted"
NONE = "no_signals"


@dataclass
class Wallet:
    address: str
    txs: int = 0
    hours: set[int] = field(default_factory=set)
    max_in_window: int = 0
    top_call_share: float = 0.0
    lifetime_txs: int | None = None
    sample_hashes: list[str] = field(default_factory=list)

    def flags(self) -> list[str]:
        out = []
        if self.lifetime_txs is not None and self.lifetime_txs > HIGH_VOLUME:
            out.append("high_volume")
        if len(self.hours) >= ROUND_THE_CLOCK_HOURS:
            out.append("round_the_clock")
        if self.max_in_window >= BURST_IN_WINDOW:
            out.append("burst")
        if self.txs >= REPEAT_MIN_TXS and self.top_call_share >= REPEAT_SHARE:
            out.append("repeat")
        return out

    def label(self) -> str:
        n = len(self.flags())
        return LIKELY if n >= 2 else POSSIBLE if n == 1 else NONE


def utc_hour(ts: int) -> int:
    return datetime.fromtimestamp(ts, tz=timezone.utc).hour


def build_wallets(txs: list[dict]) -> dict[str, Wallet]:
    """Aggregate compact sample rows (see sample.compact) into wallets."""
    per_window: dict[str, Counter] = defaultdict(Counter)
    calls: dict[str, Counter] = defaultdict(Counter)
    wallets: dict[str, Wallet] = {}
    for tx in txs:
        w = wallets.setdefault(tx["f"], Wallet(tx["f"]))
        w.txs += 1
        w.hours.add(utc_hour(tx["ts"]))
        per_window[tx["f"]][tx["w"]] += 1
        calls[tx["f"]][(tx["t"], tx["cd"])] += 1
        if len(w.sample_hashes) < 3:
            w.sample_hashes.append(tx["h"])
    for addr, w in wallets.items():
        w.max_in_window = max(per_window[addr].values())
        w.top_call_share = calls[addr].most_common(1)[0][1] / w.txs
    return wallets
