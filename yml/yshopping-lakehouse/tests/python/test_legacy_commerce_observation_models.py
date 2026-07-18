import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = ROOT / "models" / "apply-order-v1.txt"

DWD_MODELS = (
    "pay-order",
    "pay-refund",
    "member-user",
    "product-browse-history",
    "trade-cart",
)
DWS_MODELS = (
    "payment",
    "user-behavior",
)


class LegacyCommerceObservationModelsTest(unittest.TestCase):
    def test_manifest_orders_new_legacy_observability_models_after_existing_legacy_current_state(self):
        entries = [
            line.strip()
            for line in MANIFEST.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        positions = {entry: index for index, entry in enumerate(entries)}

        legacy_collect = "models/dwd/dwd-legacy-collect-current.sql"
        legacy_pay_order = "models/dwd/dwd-legacy-pay-order-current.sql"
        payment_dws = "models/dws/dws-legacy-payment-current.sql"
        behavior_dws = "models/dws/dws-legacy-user-behavior-current.sql"
        legacy_ads = "models/ads/ads-legacy-commerce-source-metrics.sql"

        self.assertLess(positions[legacy_collect], positions[legacy_pay_order])
        for slug in DWD_MODELS:
            entry = f"models/dwd/dwd-legacy-{slug}-current.sql"
            self.assertEqual(1, entries.count(entry))
            self.assertTrue((ROOT / entry).is_file())
            self.assertLess(positions[entry], positions[payment_dws])
        self.assertLess(positions[payment_dws], positions[behavior_dws])
        self.assertLess(positions[behavior_dws], positions[legacy_ads])

    def test_dwd_models_are_current_state_only_and_pii_safe(self):
        expectations = {
            "dwd-legacy-pay-order-current.sql": ("pay_order", ("notify_url", "user_ip", "channel_user_id")),
            "dwd-legacy-pay-refund-current.sql": ("pay_refund", ("notify_url", "user_ip", "channel_notify_data", "channel_error_msg")),
            "dwd-legacy-member-user-current.sql": ("member_user", ("password", "mobile", "email", "nickname", "avatar", "mark", "tag_ids", "login_date", "point", "experience")),
            "dwd-legacy-product-browse-history-current.sql": ("product_browse_history", tuple()),
            "dwd-legacy-trade-cart-current.sql": ("trade_cart", tuple()),
        }
        for filename, (source_table, forbidden) in expectations.items():
            text = (ROOT / "models" / "dwd" / filename).read_text(encoding="utf-8")
            self.assertIn("LEGACY_CURRENT_STATE_ROW", text)
            self.assertIn(f"'{source_table}' AS source_table", text)
            for field in forbidden:
                self.assertNotIn(field, text, filename)

    def test_dws_payment_and_behavior_rollups_expose_join_coverage_not_funnel_truth(self):
        payment = (ROOT / "models/dws/dws-legacy-payment-current.sql").read_text(encoding="utf-8")
        behavior = (ROOT / "models/dws/dws-legacy-user-behavior-current.sql").read_text(encoding="utf-8")

        for required in (
            "trade_order_linked_pay_order_count",
            "pay_order_unlinked_refund_count",
            "average_refund_cycle_hours",
            "observable_refund_cycle_count",
        ):
            self.assertIn(required, payment)
        self.assertNotIn("visit_to_pay_rate", payment)
        self.assertIn("LEGACY_CURRENT_STATE_OBSERVABILITY", payment)

        for required in (
            "member_unresolved_browse_count",
            "member_unresolved_cart_count",
            "selected_cart_quantity",
            "source_user_deleted_browse_count",
        ):
            self.assertIn(required, behavior)
        self.assertNotIn("session_id", behavior.lower())
        self.assertIn("LEGACY_CURRENT_STATE_OBSERVABILITY", behavior)

    def test_ads_rollup_keeps_legacy_source_isolation_and_new_join_quality_flags(self):
        text = (ROOT / "models/ads/ads-legacy-commerce-source-metrics.sql").read_text(encoding="utf-8")
        for required in (
            "trade_order_linked_pay_order_count",
            "refund_order_join_rate",
            "browse_unresolved_member_rate",
            "cart_unresolved_member_rate",
            "LEGACY_SOURCE_ONLY",
            "LOCAL_YUDAO_TRADE_CURRENT_STATE_NOT_YSHOPPING_PRODUCTION",
        ):
            self.assertIn(required, text)
        self.assertIn("pay_trade_user_mismatch_count", text)
        self.assertIn("quality_flag_count", text)
        self.assertNotIn("'LOCAL_TEST_CANONICAL_CURRENT'", text)


if __name__ == "__main__":
    unittest.main()
