"""Attribute contract addresses to hub apps, strongest evidence first.

1. frontend: the address appears in exactly one app's frontend code.
2. deployer: the address was deployed by the same wallet as a contract that
   rule 1 attributed to exactly one app.
3. name: the explorer's contract or token name contains the app's name.

Addresses embedded by several frontends (shared tokens, routers) stay shared
rather than being credited to one app.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class Attribution:
    app: str | None
    rule: str  # frontend | deployer | name | shared | unattributed


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def attribute(
    targets: set[str],
    app_addresses: dict[str, set[str]],
    app_names: dict[str, str],
    meta: dict[str, dict],
) -> dict[str, Attribution]:
    claims: dict[str, set[str]] = defaultdict(set)
    for app, addrs in app_addresses.items():
        for a in addrs:
            claims[a].add(app)

    out: dict[str, Attribution] = {}
    deployer_app: dict[str, set[str]] = defaultdict(set)
    for addr, apps in claims.items():
        if len(apps) == 1:
            creator = (meta.get(addr) or {}).get("creator")
            if creator:
                deployer_app[creator].update(apps)

    names = {app: _norm(name) for app, name in app_names.items() if len(_norm(name)) >= 4}
    for t in targets:
        apps = claims.get(t, set())
        if len(apps) == 1:
            out[t] = Attribution(next(iter(apps)), "frontend")
            continue
        if len(apps) > 1:
            out[t] = Attribution(None, "shared")
            continue
        info = meta.get(t) or {}
        via_deployer = deployer_app.get(info.get("creator") or "", set())
        if len(via_deployer) == 1:
            out[t] = Attribution(next(iter(via_deployer)), "deployer")
            continue
        label = _norm(" ".join(filter(None, [info.get("name"), info.get("token_name")])))
        hits = [app for app, n in names.items() if label and n in label]
        if len(hits) == 1:
            out[t] = Attribution(hits[0], "name")
        else:
            out[t] = Attribution(None, "unattributed")
    return out
