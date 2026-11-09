import unittest

from headcount.export import category


class Category(unittest.TestCase):
    def test_keeps_acronyms_and_sentence_cases_the_rest(self):
        self.assertEqual(category("DEX"), "DEX")
        self.assertEqual(category("DEX AGGREGATOR"), "DEX aggregator")
        self.assertEqual(category("RWA & AI"), "RWA & AI")
        self.assertEqual(category("DEFI SUITE"), "DeFi suite")
        self.assertEqual(category("PREDICTION MARKET"), "Prediction market")

    def test_missing_tag_is_empty(self):
        self.assertEqual(category(None), "")


if __name__ == "__main__":
    unittest.main()
