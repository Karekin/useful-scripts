import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = json.loads((ROOT / "contracts/event-manifest-v1.json").read_text(encoding="utf-8"))
ENVELOPE = json.loads(
    (ROOT / "contracts/events/domain-event-envelope-v1.schema.json").read_text(encoding="utf-8")
)


class CommerceBehaviorModelsTest(unittest.TestCase):
    def test_commerce_behavior_contracts_are_registered(self):
        expected = {
            "commerce.session.status_changed",
            "commerce.session.identity_linked",
            "commerce.behavior.recorded",
            "commerce.session.payment_attributed",
        }
        self.assertTrue(expected.issubset(MANIFEST["events"]))
        self.assertIn("cloudmold-commerce-behavior", ENVELOPE["properties"]["source_system"]["enum"])

    def test_behavior_schema_supports_search_and_conversion_markers(self):
        behavior_schema = json.loads(
            (ROOT / "contracts/events/commerce-behavior-recorded-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            behavior_schema["properties"]["behavior_type"]["enum"],
            [
                "PDP_VIEWED",
                "SEARCH_REQUESTED",
                "SEARCH_RESULT_EXPOSED",
                "SEARCH_RESULT_CLICKED",
                "CART_ADDED",
                "CART_REMOVED",
                "CHECKOUT_STARTED",
                "CHECKOUT_ABANDONED",
                "RECOMMENDATION_EXPOSED",
                "RECOMMENDATION_CLICKED",
            ],
        )
        self.assertIn("search_token", behavior_schema["properties"])
        self.assertIn("result_set_token", behavior_schema["properties"])
        self.assertNotIn("behavior_stage", behavior_schema["properties"])
        self.assertNotIn("page_type", behavior_schema["properties"])
        self.assertNotIn("search_query", behavior_schema["properties"])
        self.assertNotIn("payment_id", behavior_schema["properties"])

    def test_models_avoid_legacy_current_state_history_inference(self):
        forbidden = {
            "product_browse_history",
            "trade_cart",
            "dwd_legacy_product_browse_history_current",
            "dwd_legacy_trade_cart_current",
        }
        for relative in (
            "models/dwd/dwd-canonical-commerce-session-event.sql",
            "models/dim/dim-canonical-commerce-session-current.sql",
            "models/dws/dws-canonical-commerce-session-funnel.sql",
            "models/dws/dws-canonical-commerce-search-request-funnel.sql",
            "models/ads/ads-canonical-commerce-acquisition-funnel.sql",
            "models/dws/dws-canonical-merchant-acquisition-daily.sql",
            "models/ads/ads-canonical-merchant-acquisition-metrics.sql",
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            for needle in forbidden:
                self.assertNotIn(needle, text, relative)

    def test_dqc_covers_session_search_and_acquisition_guards(self):
        dqc = (ROOT / "tests/sql/41-canonical-commerce-behavior-contract.sql").read_text(
            encoding="utf-8"
        )
        for check in (
            "commerce_session_current_duplicate",
            "commerce_session_funnel_invalid_timeline",
            "commerce_session_payment_attribution_duplicate",
            "commerce_search_request_invalid",
            "commerce_acquisition_funnel_invalid",
            "merchant_acquisition_dimension_missing",
            "merchant_acquisition_metric_invalid",
            "merchant_acquisition_ads_mismatch",
        ):
            self.assertIn(check, dqc)

    def test_merchant_acquisition_uses_only_governed_store_context(self):
        dws = (ROOT / "models/dws/dws-canonical-merchant-acquisition-daily.sql").read_text(
            encoding="utf-8"
        )
        for required in (
            "listing_id IS NOT NULL",
            "listing_offer_id IS NOT NULL",
            "attribution.merchant_id = touch.merchant_id",
            "attribution.shop_id = touch.shop_id",
            "PARTITION BY tenant_id, merchant_id, principal_id",
        ):
            self.assertIn(required, dws)
        self.assertNotIn("dws_legacy_user_behavior_current", dws)


if __name__ == "__main__":
    unittest.main()
