import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = json.loads((ROOT / "contracts/event-manifest-v1.json").read_text(encoding="utf-8"))
ENVELOPE = json.loads(
    (ROOT / "contracts/events/domain-event-envelope-v1.schema.json").read_text(encoding="utf-8")
)


class AppRecommendationCartModelsTest(unittest.TestCase):
    def test_app_contracts_are_registered_and_source_system_is_allowlisted(self):
        expected = {
            "app.recommendation.generated",
            "app.recommendation.served",
            "app.cart.changed",
            "app.product_review.created",
            "engagement.community.reaction_status_changed",
        }
        self.assertTrue(expected.issubset(MANIFEST["events"]))
        self.assertIn("cloudmold-app-commerce", ENVELOPE["properties"]["source_system"]["enum"])

    def test_recommendation_and_cart_schemas_are_fail_closed_and_pii_safe(self):
        for relative in (
            "contracts/events/app-recommendation-generated-v1.schema.json",
            "contracts/events/app-recommendation-served-v1.schema.json",
            "contracts/events/app-cart-changed-v1.schema.json",
        ):
            schema = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            self.assertFalse(schema.get("additionalProperties", True), relative)
            text = json.dumps(schema, ensure_ascii=False)
            for forbidden in (
                "receiver_name",
                "receiver_phone",
                "address_detail",
                "mobile",
            ):
                self.assertNotIn(forbidden, text, relative)

    def test_recommendation_models_use_exact_token_and_rank_join(self):
        dws = (ROOT / "models/dws/dws-app-recommendation-effectiveness.sql").read_text(encoding="utf-8")
        self.assertIn("behavior.result_set_token = item.decision_token", dws)
        self.assertIn("behavior.listing_id = item.listing_id", dws)
        self.assertIn("behavior.result_position = item.rank_no", dws)
        self.assertIn("RECOMMENDATION_EXPOSED", dws)
        self.assertIn("RECOMMENDATION_CLICKED", dws)

    def test_cart_models_remain_current_state_only_without_fake_order_linkage(self):
        dws = (ROOT / "models/dws/dws-app-cart-current.sql").read_text(encoding="utf-8")
        self.assertIn("APP_CART_CURRENT_STATE_ONLY_NO_EXACT_CHECKOUT_ORDER_LINK", dws)
        for forbidden in ("order_id", "checkout_token", "payment_id"):
            self.assertNotIn(forbidden, dws)

    def test_dqc_covers_recommendation_exact_join_and_cart_materialization(self):
        dqc = (ROOT / "tests/sql/53-app-recommendation-cart-contract.sql").read_text(encoding="utf-8")
        for check in (
            "app_recommendation_current_duplicate",
            "app_recommendation_item_count_mismatch",
            "app_recommendation_behavior_exact_join_missing",
            "app_cart_current_duplicate",
            "app_cart_line_materialization_mismatch",
        ):
            self.assertIn(check, dqc)


if __name__ == "__main__":
    unittest.main()
