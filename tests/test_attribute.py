import unittest

from headcount.attribute import Attribution, attribute

NAMES = {"swap": "LiteSwap", "game": "Last Hero", "gm": "Hey"}


class Attribute(unittest.TestCase):
    def test_frontend_claim_by_one_app_wins(self):
        out = attribute({"0xr"}, {"swap": {"0xr"}}, NAMES, {"0xr": {"name": "Last Hero Pot"}})
        self.assertEqual(out["0xr"], Attribution("swap", "frontend"))

    def test_address_in_several_frontends_stays_shared(self):
        out = attribute({"0xusdc"}, {"swap": {"0xusdc"}, "game": {"0xusdc"}}, NAMES, {})
        self.assertEqual(out["0xusdc"], Attribution(None, "shared"))

    def test_same_deployer_inherits_app(self):
        meta = {"0xr": {"creator": "0xdev"}, "0xpool": {"creator": "0xdev"}}
        out = attribute({"0xr", "0xpool"}, {"swap": {"0xr"}}, NAMES, meta)
        self.assertEqual(out["0xpool"], Attribution("swap", "deployer"))

    def test_deployer_shared_by_two_apps_is_not_used(self):
        meta = {"0xa": {"creator": "0xdev"}, "0xb": {"creator": "0xdev"}, "0xc": {"creator": "0xdev"}}
        out = attribute({"0xc"}, {"swap": {"0xa"}, "game": {"0xb"}}, NAMES, meta)
        self.assertEqual(out["0xc"].rule, "unattributed")

    def test_name_match_ignores_short_app_names(self):
        meta = {"0xh": {"name": "HeyToken"}, "0xl": {"token_name": "Last Hero Ticket"}}
        out = attribute({"0xh", "0xl"}, {}, NAMES, meta)
        self.assertEqual(out["0xh"].rule, "unattributed")
        self.assertEqual(out["0xl"], Attribution("game", "name"))

    def test_unknown_contract_is_unattributed(self):
        self.assertEqual(attribute({"0xz"}, {}, NAMES, {})["0xz"], Attribution(None, "unattributed"))


if __name__ == "__main__":
    unittest.main()
