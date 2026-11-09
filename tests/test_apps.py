import unittest

from headcount.apps import ADDRESS, merge_scans

A = "0x" + "a" * 40
B = "0x" + "b" * 40


class MergeScans(unittest.TestCase):
    def test_first_scan_is_kept_as_is(self):
        new = {"id": "x", "status": "ok", "scripts": 3, "addresses": [A]}
        self.assertEqual(merge_scans(None, new), new)

    def test_timeout_keeps_earlier_addresses_and_ok_status(self):
        prev = {"id": "x", "status": "ok", "scripts": 9, "addresses": [A]}
        new = {"id": "x", "status": "unreachable (curl exit 28)", "scripts": 0, "addresses": []}
        merged = merge_scans(prev, new)
        self.assertEqual(merged["addresses"], [A])
        self.assertEqual(merged["status"], "ok")
        self.assertEqual(merged["scripts"], 9)

    def test_addresses_are_unioned(self):
        prev = {"id": "x", "status": "ok", "scripts": 1, "addresses": [A]}
        new = {"id": "x", "status": "ok", "scripts": 2, "addresses": [B, A]}
        self.assertEqual(merge_scans(prev, new)["addresses"], [A, B])


class AddressPattern(unittest.TestCase):
    def test_matches_exact_40_hex_only(self):
        text = f'x="{A}" y="{A}ff" z="0x{"c" * 39}"'
        self.assertEqual(ADDRESS.findall(text), [A])


if __name__ == "__main__":
    unittest.main()
