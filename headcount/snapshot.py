"""Store each scan as a dated snapshot with a fingerprint.

A snapshot is the exported row files for one scan, kept under
snapshots/<YYYY-MM-DD>/ next to a meta.json. The digest is SHA-256 over the
row files in name order, so anyone can recompute it from the published files
and compare it with the value recorded on-chain.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROW_FILES = ("apps", "cohorts", "evidence", "flags", "groups", "summary", "windows")


def digest(folder: Path) -> str:
    h = hashlib.sha256()
    for name in ROW_FILES:
        h.update(f"{name}.json\n".encode())
        h.update((folder / f"{name}.json").read_bytes())
        h.update(b"\n")
    return "0x" + h.hexdigest()


def snapshot_date(summary: dict) -> str:
    """The UTC date the scan window ends on, which names the snapshot."""
    end = datetime.strptime(summary["window_end"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return end.strftime("%Y-%m-%d")


def write_index(root: Path) -> list[dict]:
    entries = []
    for meta_path in sorted(root.glob("*/meta.json"), reverse=True):
        meta = json.loads(meta_path.read_text())
        entries.append({k: meta[k] for k in ("date", "digest", "window_start", "window_end")})
    (root / "index.json").write_text(json.dumps(entries, indent=1) + "\n")
    return entries


def run(out: Path, root: Path) -> dict:
    summary = json.loads((out / "summary.json").read_text())[0]
    date = snapshot_date(summary)
    folder = root / date
    folder.mkdir(parents=True, exist_ok=True)
    for name in ROW_FILES:
        shutil.copyfile(out / f"{name}.json", folder / f"{name}.json")
    meta = {
        "date": date,
        "digest": digest(folder),
        "window_start": summary["window_start"],
        "window_end": summary["window_end"],
        "files": [f"{name}.json" for name in ROW_FILES],
    }
    (folder / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    write_index(root)
    print(f"snapshot {date} digest {meta['digest']}")
    return meta
