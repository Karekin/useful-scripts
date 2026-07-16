import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = json.loads((ROOT / "contracts/event-manifest-v1.json").read_text(encoding="utf-8"))
ORDER = [
    line.strip()
    for line in (ROOT / "models/apply-order-v1.txt").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.startswith("#")
]


class GamificationModelsTest(unittest.TestCase):
    EVENTS = {
        "gamification.game.created", "gamification.game.definition_published",
        "gamification.virtual_currency.account_opened", "gamification.virtual_currency.ledger_posted",
        "gamification.reward.definition_published", "gamification.reward.granted",
        "gamification.draw_pool.version_published", "gamification.draw.completed",
        "gamification.session.status_changed", "gamification.round.status_changed",
        "gamification.assist.recorded", "gamification.task.definition_published",
        "gamification.task.progress_changed", "gamification.fragment.ledger_posted",
        "gamification.gift.transferred", "gamification.season_series.version_published",
        "gamification.season.version_published", "gamification.collectible.version_published",
        "gamification.collectible.ownership_changed", "gamification.redemption.status_changed",
        "gamification.reward_claim.status_changed",
    }

    def schema(self, name):
        return json.loads((ROOT / f"contracts/events/{name}").read_text(encoding="utf-8"))

    def test_all_backend_events_are_manifested_with_strict_payloads(self):
        self.assertTrue(self.EVENTS.issubset(MANIFEST["events"]))
        for event_type in self.EVENTS:
            config = MANIFEST["events"][event_type]
            schema = json.loads((ROOT / "contracts" / config["payload_schema"]).read_text(encoding="utf-8"))
            self.assertFalse(schema["additionalProperties"], event_type)
            self.assertEqual(set(schema["required"]), set(schema["properties"]), event_type)

    def test_asset_and_external_value_boundaries_are_locked(self):
        game = self.schema("gamification-game-definition-published-v1.schema.json")["properties"]
        self.assertIn("session_ttl_seconds", game)
        self.assertIn("(?!.*(?:TOKEN|COUPON|POINT|CNY|RMB|USD|MONEY))", game["virtual_currency_code"]["pattern"])
        redemption = self.schema("gamification-redemption-status-changed-v1.schema.json")
        self.assertEqual(False, redemption["properties"]["contains_external_balance"]["const"])
        self.assertTrue({"source_asset_class", "collectible_definition_id", "collectible_version", "quantity",
                         "currency_code", "amount_microunits", "source_ledger_transaction_id"}.issubset(redemption["required"]))
        self.assertEqual({"GAME_COLLECTIBLE", "GAME_VIRTUAL_CURRENCY"},
                         set(redemption["properties"]["source_asset_class"]["enum"]))
        ledger = self.schema("gamification-virtual-currency-ledger-posted-v1.schema.json")
        self.assertIn("REDEMPTION", ledger["properties"]["business_type"]["enum"])
        forbidden = {"amount_minor", "money_amount", "coupon_id", "point_amount", "token_amount", "external_balance"}
        for path in (ROOT / "contracts/events").glob("gamification-*.schema.json"):
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(forbidden.isdisjoint(schema["properties"]), path.name)

    def test_versioned_definition_and_claim_fields_are_complete(self):
        expected = {
            "gamification-season-series-version-published-v1.schema.json": {"series_name"},
            "gamification-season-version-published-v1.schema.json": {"season_code", "season_name", "definition_sha256"},
            "gamification-collectible-version-published-v1.schema.json": {"collectible_name"},
            "gamification-reward-claim-status-changed-v1.schema.json": {"source_type", "source_id", "claimed_at"},
        }
        for name, fields in expected.items():
            self.assertTrue(fields.issubset(self.schema(name)["required"]), name)

    def test_redemption_contract_has_mutually_exclusive_asset_and_status_branches(self):
        schema = self.schema("gamification-redemption-status-changed-v1.schema.json")
        def branch(**conditions):
            return next(
                rule["then"]["properties"]
                for rule in schema["allOf"]
                if {key: value["const"] for key, value in rule["if"]["properties"].items()} == conditions
            )

        collectible = branch(source_asset_class="GAME_COLLECTIBLE")
        self.assertEqual("string", collectible["collectible_definition_id"]["type"])
        self.assertEqual("null", collectible["currency_code"]["type"])
        self.assertEqual("null", collectible["amount_microunits"]["type"])

        currency = branch(source_asset_class="GAME_VIRTUAL_CURRENCY")
        self.assertEqual("null", currency["collectible_definition_id"]["type"])
        self.assertEqual("string", currency["currency_code"]["type"])
        self.assertEqual("integer", currency["amount_microunits"]["type"])

        pending = branch(current_status="PENDING")
        rejected = branch(current_status="REJECTED")
        self.assertEqual("null", pending["source_ledger_transaction_id"]["type"])
        self.assertEqual("null", rejected["source_ledger_transaction_id"]["type"])

        currency_success = branch(current_status="SUCCEEDED", source_asset_class="GAME_VIRTUAL_CURRENCY")
        collectible_success = branch(current_status="SUCCEEDED", source_asset_class="GAME_COLLECTIBLE")
        self.assertEqual("string", currency_success["source_ledger_transaction_id"]["type"])
        self.assertEqual("null", collectible_success["source_ledger_transaction_id"]["type"])

    def test_model_dependency_order_and_history_policy(self):
        positions = {entry: index for index, entry in enumerate(ORDER)}
        dwd = "models/dwd/dwd-canonical-gamification-event.sql"
        dim = "models/dim/dim-canonical-gamification-current.sql"
        dws = "models/dws/dws-canonical-gamification-current.sql"
        ads = "models/ads/ads-canonical-gamification-readiness.sql"
        self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[dwd])
        self.assertLess(positions[dwd], positions[dim])
        self.assertLess(positions[dim], positions[dws])
        self.assertLess(positions[dws], positions[ads])
        dim_sql = (ROOT / dim).read_text(encoding="utf-8")
        for history in ("game_version_history", "reward_definition_history", "draw_pool_version_history",
                        "task_definition_history", "season_series_version_history", "season_version_history",
                        "collectible_version_history"):
            self.assertIn(history, dim_sql)

    def test_dws_are_governed_read_models_not_new_write_authorities(self):
        dws = (ROOT / "models/dws/dws-canonical-gamification-current.sql").read_text(encoding="utf-8")
        for view in ("player_game_1d", "currency_balance_current", "gamification_economy_current",
                     "collectible_balance_current", "reward_delivery_current", "season_leaderboard_current",
                     "redemption_current", "currency_leaderboard_input_current", "gift_leaderboard_1d"):
            self.assertIn(view, dws)
        self.assertNotIn("gamification.leaderboard", MANIFEST["events"])
        self.assertIn("lakehouse-derived read model", dws)

        ads = (ROOT / "models/ads/ads-canonical-gamification-readiness.sql").read_text(encoding="utf-8")
        for view in ("currency_leaderboard_current", "gift_leaderboard_1d"):
            self.assertIn(view, ads)
        self.assertIn("DENSE_RANK()", ads)
        self.assertIn("principal_id ASC", ads)

    def test_dqc_covers_economic_and_cross_domain_invariants(self):
        dqc = (ROOT / "tests/sql/25-canonical-gamification-contract.sql").read_text(encoding="utf-8")
        for check in (
            "gamification_currency_ledger_not_double_entry",
            "gamification_currency_balance_not_ledger_derived",
            "gamification_draw_charge_reward_lineage_invalid",
            "gamification_fragment_reward_lineage_invalid",
            "gamification_collectible_balance_not_ledger_derived",
            "gamification_redemption_external_boundary_invalid",
            "gamification_redemption_deduction_cardinality_invalid",
            "gamification_reward_claim_lineage_invalid",
            "gamification_leaderboard_write_event_forbidden",
            "gamification_currency_leaderboard_input_invalid",
            "gamification_currency_leaderboard_key_duplicate",
            "gamification_currency_leaderboard_position_invalid",
            "gamification_gift_leaderboard_input_invalid",
            "gamification_gift_leaderboard_position_invalid",
            "gamification_unproven_completion_flag",
        ):
            self.assertIn(check, dqc)
        self.assertIn("c.delta_quantity <> -r.quantity", dqc)
        self.assertIn("l.business_type <> 'REDEMPTION'", dqc)
        self.assertIn("r.source_ledger_transaction_id", dqc)

    def test_alignment_remains_honestly_partial(self):
        alignment = json.loads((ROOT / "contracts/yshopping-model-alignment-v1.json").read_text(encoding="utf-8"))
        game = next(unit for unit in alignment["alignment_units"] if unit["id"] == "game")
        self.assertEqual("partial", game["backend"]["status"])
        self.assertEqual("partial", game["lakehouse"]["status"])
        self.assertTrue(game["backend"]["gaps"])
        self.assertTrue(game["lakehouse"]["gaps"])


if __name__ == "__main__":
    unittest.main()
