import json
import tempfile
import time
import unittest
from pathlib import Path

from headcount import sample, snapshot


def write_rows(folder: Path, end: str = "2026-11-07T13:42:20Z") -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in snapshot.ROW_FILES:
        rows = [{"window_start": "2026-11-06T13:42:20Z", "window_end": end}] if name == "summary" else [{"n": name}]
        (folder / f"{name}.json").write_text(json.dumps(rows))


class Snapshot(unittest.TestCase):
    def test_writes_dated_folder_meta_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, root = Path(tmp) / "out", Path(tmp) / "snapshots"
            write_rows(out)
            meta = snapshot.run(out, root)
            self.assertEqual(meta["date"], "2026-11-07")
            self.assertTrue((root / "2026-11-07" / "apps.json").exists())
            index = json.loads((root / "index.json").read_text())
            self.assertEqual([e["date"] for e in index], ["2026-11-07"])
            self.assertEqual(index[0]["digest"], meta["digest"])

    def test_digest_is_stable_and_changes_with_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write_rows(folder)
            first = snapshot.digest(folder)
            self.assertEqual(first, snapshot.digest(folder))
            self.assertRegex(first, r"^0x[0-9a-f]{64}$")
            (folder / "apps.json").write_text("[]")
            self.assertNotEqual(first, snapshot.digest(folder))

    def test_index_lists_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, root = Path(tmp) / "out", Path(tmp) / "snapshots"
            for end in ("2026-11-07T13:00:00Z", "2026-11-09T13:00:00Z", "2026-11-08T13:00:00Z"):
                write_rows(out, end)
                snapshot.run(out, root)
            dates = [e["date"] for e in json.loads((root / "index.json").read_text())]
            self.assertEqual(dates, ["2026-11-09", "2026-11-08", "2026-11-07"])


class FreshScan(unittest.TestCase):
    def test_old_plan_and_nonce_cache_are_cleared(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            windows = data / "windows"
            windows.mkdir()
            (windows / "plan.json").write_text(json.dumps({"created": 1000}))
            (data / "nonces.json").write_text("{}")
            (data / "meta.json").write_text("{}")
            self.assertTrue(sample.start_fresh_if_stale(windows, 1000 + 13 * 3600))
            self.assertFalse(windows.exists())
            self.assertFalse((data / "nonces.json").exists())
            self.assertTrue((data / "meta.json").exists())

    def test_recent_plan_resumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            windows = Path(tmp) / "windows"
            windows.mkdir()
            now = time.time()
            (windows / "plan.json").write_text(json.dumps({"created": now - 3600}))
            self.assertFalse(sample.start_fresh_if_stale(windows, now))
            self.assertTrue(windows.exists())


if __name__ == "__main__":
    unittest.main()
