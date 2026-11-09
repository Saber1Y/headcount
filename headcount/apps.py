"""Read the LitVM testnet hub's app directory and find each app's contract addresses.

The hub ships its directory as JSON inside its JavaScript bundle. For each app,
the scan fetches the public frontend and the scripts it loads, then collects every
EVM address literal. An address a frontend embeds is evidence the app calls it.
Sites that answer with a bot challenge are recorded as blocked, not worked around.
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .http import HttpError, fetch

HUB = "https://testnet.litvm.com/"
ADDRESS = re.compile(r"0x[a-fA-F0-9]{40}(?![a-fA-F0-9])")
SCRIPT_SRC = re.compile(r"""<script[^>]+src=["']([^"']+)["']""", re.I)
# Chunk paths inside bundles: Next.js build paths, Vite asset paths, and relative imports.
CHUNK_PATH = re.compile(
    r"""["'](/?_next/static/[^"']+?\.js|/?assets/[^"']+?\.js|static/chunks/[^"']+?\.js|\./[\w.-]+?\.js)["']"""
)
# Analytics and widget hosts carry no app contracts; skip them to save the budget.
SKIP_HOSTS = ("googletagmanager.com", "google-analytics.com", "cloudflareinsights.com", "vercel-insights.com")
CHALLENGE = re.compile(rb"Vercel Security Checkpoint|cf-chl|challenge-platform|Just a moment", re.I)
# Same-site links on the homepage; route-specific code (a staking page) often loads only there.
PAGE_LINK = re.compile(r"""href=["'](/[A-Za-z0-9_\-/]*)["']""")
MAX_SUBPAGES = 8
MAX_SCRIPTS = 80
MAX_BYTES = 25_000_000
ZERO = "0x" + "0" * 40


def _fetch_ok(url: str, attempts: int = 4) -> bytes:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            status, body = fetch(url, timeout=60)
            if status == 200:
                return body
            last = HttpError(f"HTTP {status} for {url}")
        except HttpError as exc:
            last = exc
        time.sleep(3 * (attempt + 1))
    raise HttpError(str(last))


def hub_apps() -> list[dict]:
    html = _fetch_ok(HUB)
    apps: dict[str, dict] = {}
    for src in SCRIPT_SRC.findall(html.decode(errors="replace")):
        js = _fetch_ok(urljoin(HUB, src))
        text = js.decode(errors="replace")
        for m in re.finditer(r'\{"id":"[^"]+","name":"[^{}]*?"comingSoon":(?:true|false)\}', text):
            app = json.loads(m.group(0))
            if not app.get("comingSoon") and app.get("url"):
                apps[app["id"]] = {k: app.get(k) for k in ("id", "name", "url", "tag", "description")}
    return list(apps.values())


def scan_frontend(app: dict) -> dict:
    """Collect address literals from an app's page and the scripts it loads.

    Scripts from any host are followed, since many apps serve bundles from a CDN.
    Stray addresses (other chains, libraries) are harmless: only addresses that
    match contracts seen on LiteForge are used.
    """
    url = app["url"]
    origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    result = {"id": app["id"], "status": "ok", "scripts": 0, "addresses": []}
    try:
        status, html = fetch(url, timeout=30)
    except HttpError as exc:
        return {**result, "status": f"unreachable ({exc})"}
    if CHALLENGE.search(html):
        return {**result, "status": "bot challenge (not bypassed)"}
    if status >= 400:
        return {**result, "status": f"HTTP {status}"}
    page = html.decode(errors="replace")
    found = set(ADDRESS.findall(page))
    queue = [urljoin(url, s) for s in SCRIPT_SRC.findall(page)]
    total = len(html)
    subpages = sorted({p for p in PAGE_LINK.findall(page) if p.strip("/")})[:MAX_SUBPAGES]
    for path in subpages:
        try:
            status, sub = fetch(origin + path, timeout=30)
        except HttpError:
            continue
        if status != 200 or CHALLENGE.search(sub):
            continue
        total += len(sub)
        text = sub.decode(errors="replace")
        found |= set(ADDRESS.findall(text))
        queue += [urljoin(origin + path, s) for s in SCRIPT_SRC.findall(text)]
    seen: set[str] = set()
    while queue and len(seen) < MAX_SCRIPTS and total < MAX_BYTES:
        src = queue.pop(0)
        if src in seen or any(h in urlparse(src).netloc for h in SKIP_HOSTS):
            continue
        seen.add(src)
        try:
            status, body = fetch(src, timeout=30)
        except HttpError:
            continue
        if status != 200:
            continue
        total += len(body)
        text = body.decode(errors="replace")
        found |= set(ADDRESS.findall(text))
        for path in CHUNK_PATH.findall(text):
            if path.startswith("./"):
                queue.append(urljoin(src, path))
            else:
                # Build paths are relative to the site root, where the bundle came from.
                base = f"{urlparse(src).scheme}://{urlparse(src).netloc}/"
                queue.append(urljoin(base, path))
    found = {a.lower() for a in found} - {ZERO}
    return {**result, "scripts": len(seen), "addresses": sorted(found)}


def merge_scans(prev: dict | None, new: dict) -> dict:
    """Union two scans of one frontend, so a slow site on one run keeps earlier evidence."""
    if not prev:
        return new
    addresses = sorted(set(prev["addresses"]) | set(new["addresses"]))
    status = new["status"] if new["status"] == "ok" or prev["status"] != "ok" else prev["status"]
    return {**new, "status": status, "scripts": max(prev["scripts"], new["scripts"]), "addresses": addresses}


def run(data: Path) -> None:
    path = data / "apps.json"
    previous = {a["id"]: a["frontend"] for a in json.loads(path.read_text())} if path.exists() else {}
    apps = hub_apps()
    with ThreadPoolExecutor(12) as pool:
        scans = list(pool.map(scan_frontend, apps))
    by_id = {s["id"]: s for s in scans}
    for app in apps:
        app["frontend"] = merge_scans(previous.get(app["id"]), by_id[app["id"]])
    path.write_text(json.dumps(apps, indent=1))
    ok = sum(1 for a in apps if a["frontend"]["addresses"])
    print(f"{len(apps)} live apps, {ok} with addresses in their frontend")
    for a in apps:
        f = a["frontend"]
        print(f"  {a['name']:<22} {f['status']:<28} scripts={f['scripts']:<3} addresses={len(f['addresses'])}")
