import unittest

from headcount import signals

HOUR = 3600
BASE = 1_793_000_000 - (1_793_000_000 % 86400)  # midnight UTC


def tx(sender, window, ts, target="0xapp", calldata="aa", h=None):
    return {"f": sender, "w": window, "ts": ts, "t": target, "cd": calldata, "h": h or f"0x{sender}{ts}"}


class BuildWallets(unittest.TestCase):
    def test_counts_hours_bursts_and_repeats(self):
        rows = [tx("a", 0, BASE + i) for i in range(6)]
        rows += [tx("a", 5, BASE + 5 * HOUR, calldata="bb")]
        w = signals.build_wallets(rows)["a"]
        self.assertEqual(w.txs, 7)
        self.assertEqual(w.hours, {0, 5})
        self.assertEqual(w.max_in_window, 6)
        self.assertAlmostEqual(w.top_call_share, 6 / 7)
        self.assertEqual(len(w.sample_hashes), 3)

    def test_identical_calldata_to_different_targets_is_not_a_repeat(self):
        rows = [tx("a", i, BASE + i * HOUR, target=f"0x{i}") for i in range(10)]
        self.assertAlmostEqual(signals.build_wallets(rows)["a"].top_call_share, 0.1)


class Flags(unittest.TestCase):
    def test_quiet_wallet_has_no_signals(self):
        w = signals.Wallet("a", txs=3, hours={9, 10}, max_in_window=1, top_call_share=1.0, lifetime_txs=40)
        self.assertEqual(w.flags(), [])
        self.assertEqual(w.label(), signals.NONE)

    def test_each_threshold_is_inclusive_where_documented(self):
        w = signals.Wallet(
            "a",
            txs=signals.REPEAT_MIN_TXS,
            hours=set(range(signals.ROUND_THE_CLOCK_HOURS)),
            max_in_window=signals.BURST_IN_WINDOW,
            top_call_share=signals.REPEAT_SHARE,
            lifetime_txs=signals.HIGH_VOLUME + 1,
        )
        self.assertEqual(w.flags(), ["high_volume", "round_the_clock", "burst", "repeat"])

    def test_exactly_high_volume_is_not_flagged(self):
        w = signals.Wallet("a", lifetime_txs=signals.HIGH_VOLUME)
        self.assertNotIn("high_volume", w.flags())

    def test_repeat_needs_minimum_sample(self):
        w = signals.Wallet("a", txs=signals.REPEAT_MIN_TXS - 1, top_call_share=1.0)
        self.assertNotIn("repeat", w.flags())

    def test_unknown_lifetime_count_is_not_flagged(self):
        self.assertEqual(signals.Wallet("a", lifetime_txs=None).flags(), [])

    def test_labels(self):
        one = signals.Wallet("a", max_in_window=signals.BURST_IN_WINDOW)
        two = signals.Wallet("b", max_in_window=signals.BURST_IN_WINDOW, lifetime_txs=signals.HIGH_VOLUME + 1)
        self.assertEqual(one.label(), signals.POSSIBLE)
        self.assertEqual(two.label(), signals.LIKELY)


if __name__ == "__main__":
    unittest.main()
