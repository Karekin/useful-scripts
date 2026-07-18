import importlib.machinery
import importlib.util
import unittest
from pathlib import Path


USEFUL_SCRIPTS = Path(__file__).resolve().parents[4]
SCRIPT = USEFUL_SCRIPTS / "scripts" / "commerce-analyticsctl"


def load_module():
    loader = importlib.machinery.SourceFileLoader("commerce_analyticsctl_test_target", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


analyticsctl = load_module()


class CommerceAnalyticsDataProductTest(unittest.TestCase):
    def test_versioned_bundle_is_internally_consistent(self):
        summary = analyticsctl.validate()
        self.assertGreaterEqual(summary["metrics"], 60)
        self.assertEqual(8, summary["views"])
        self.assertEqual(719, summary["governed_sources"])
        self.assertEqual(258, summary["sql_models"])

    def test_role_metric_mart_is_governed_and_fail_closed(self):
        model = (
            analyticsctl.LAKEHOUSE / "models/ads/ads-ecommerce-role-metrics.sql"
        ).read_text(encoding="utf-8")
        dqc = (
            analyticsctl.LAKEHOUSE / "tests/sql/38-ecommerce-role-metrics-contract.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("CREATE OR REPLACE VIEW yshopping_ads.ads_ecommerce_role_metrics", model)
        self.assertIn("WHERE metric_value IS NOT NULL", model)
        self.assertIn("missing business semantics out of the result set", model)
        self.assertNotIn("buyer_id,", model.split("SELECT\n    tenant_id,", 1)[-1])
        self.assertIn("ecommerce_role_metric_aov_reconciliation_mismatch", dqc)
        self.assertIn("buyer.refund_cycle_hours", model)
        self.assertIn("inventory.sell_through_rate_30d", model)
        self.assertIn("service.first_response_minutes", model)

    def test_snapshot_is_aggregated_and_local_test_only(self):
        snapshot = analyticsctl.load_json(analyticsctl.SNAPSHOT)
        self.assertEqual("LOCAL_TEST", snapshot["evidence_scope"])
        self.assertEqual("Tenant 1", snapshot["tenant_label"])
        self.assertNotIn("buyer_id", analyticsctl.SNAPSHOT.read_text(encoding="utf-8").lower())
        self.assertIn("buyer.refund_cycle_hours", snapshot["metrics"])
        self.assertIn("inventory.sell_through_rate_30d", snapshot["metrics"])
        self.assertIn("service.first_response_minutes", snapshot["metrics"])
        self.assertEqual(
            "repository_verified",
            snapshot["metrics"]["governance.sql_model_count"]["status"],
        )

    def test_complete_snapshot_refresh_cannot_leave_role_marts_stale(self):
        source = SCRIPT.read_text(encoding="utf-8")
        function = source.split("def refresh_all_local_snapshot", 1)[1].split("\ndef main", 1)[0]
        expected_refreshers = (
            "refresh_local_snapshot",
            "refresh_merchant_local_snapshot",
            "refresh_operations_local_snapshot",
            "refresh_buyer_local_snapshot",
            "refresh_merchandise_local_snapshot",
            "refresh_finance_local_snapshot",
            "refresh_service_local_snapshot",
        )
        positions = [function.index(name) for name in expected_refreshers]
        self.assertEqual(sorted(positions), positions)
        self.assertIn("refresh-all-local-snapshot", source)
        self.assertIn("fixed_role_metric_ids", source)
        self.assertIn("range(0, len(fixed_role_metric_ids), 5)", source)
        self.assertIn("metric_id IN ({metric_filter})", source)

    def test_legacy_history_is_explicitly_isolated(self):
        snapshot = analyticsctl.load_json(analyticsctl.SNAPSHOT)
        legacy = snapshot["legacy_source_only"]
        self.assertEqual("LEGACY_SOURCE_ONLY", legacy["evidence_scope"])
        self.assertIn("禁止与 Canonical 指标相加", legacy["warning"])
        self.assertGreater(legacy["quality_flag_count"], 0)

    def test_report_views_only_reference_governed_kpis(self):
        catalog = analyticsctl.load_json(analyticsctl.CATALOG)
        portfolio = analyticsctl.load_json(analyticsctl.PORTFOLIO)
        known = {metric["id"] for metric in catalog["metrics"]}
        for view in portfolio["views"]:
            referenced = set(view["primary_metrics"] + view["supporting_metrics"])
            self.assertLessEqual(referenced, known)

    def test_coverage_audit_classifies_every_kpi_once(self):
        catalog = analyticsctl.load_json(analyticsctl.CATALOG)
        coverage = analyticsctl.load_json(analyticsctl.COVERAGE)
        classified = sum(coverage["computability"].values(), [])
        self.assertEqual(len(catalog["metrics"]), len(classified))
        self.assertEqual({metric["id"] for metric in catalog["metrics"]}, set(classified))
        self.assertEqual(67, coverage["summary"]["delivered_in_role_metric_mart"])
        self.assertEqual([], coverage["computability"]["missing_authoritative_semantics"])

    def test_merchant_role_metric_mart_is_lightweight_and_complete(self):
        model = (
            analyticsctl.LAKEHOUSE / "models/ads/ads-ecommerce-merchant-role-metrics.sql"
        ).read_text(encoding="utf-8")
        explicit_metrics = {
            "merchant.net_sales_yuan",
            "merchant.new_buyer_count",
            "merchant.store_conversion_rate",
            "marketing.ad_roas",
            "marketing.promotion_roi",
        }
        self.assertEqual(5, sum(model.count(f"'{metric_id}'") for metric_id in explicit_metrics))
        self.assertIn("ads_canonical_merchant_cancellation_metrics", model)
        self.assertNotIn("ads_ecommerce_role_metrics", model)

    def test_operations_role_metric_mart_is_lightweight_and_complete(self):
        model = (
            analyticsctl.LAKEHOUSE / "models/ads/ads-ecommerce-operations-role-metrics.sql"
        ).read_text(encoding="utf-8")
        for metric_id in (
            "funnel.visit_to_pay_rate",
            "funnel.cart_abandonment_rate",
            "buyer.new_paid_buyer_count",
        ):
            self.assertEqual(1, model.count(f"'{metric_id}'"))
        self.assertIn("dws_canonical_commerce_session_funnel", model)
        self.assertIn("dim_canonical_payment_current", model)
        self.assertNotIn("ads_ecommerce_role_metrics", model)

    def test_buyer_role_metric_mart_is_lightweight_and_complete(self):
        model = (
            analyticsctl.LAKEHOUSE / "models/ads/ads-ecommerce-buyer-role-metrics.sql"
        ).read_text(encoding="utf-8")
        for metric_id in (
            "buyer.time_to_first_order_hours",
            "buyer.delivery_promise_hit_rate",
            "fulfillment.on_time_delivery_rate",
        ):
            self.assertEqual(1, model.count(f"'{metric_id}'"))
        self.assertIn("dws_canonical_commerce_session_funnel", model)
        self.assertIn("ads_canonical_fulfillment_promise_metrics", model)
        self.assertIn("LOCAL_TEST_CANONICAL_CURRENT", model)
        self.assertNotIn("ads_ecommerce_role_metrics", model)

    def test_merchandise_finance_and_service_role_marts_are_lightweight(self):
        expectations = {
            "ads-ecommerce-merchandise-role-metrics.sql": (
                "inventory.turnover_days", "inventory.aged_stock_value_yuan", "procurement.otif_rate",
            ),
            "ads-ecommerce-finance-role-metrics.sql": (
                "finance.net_revenue_yuan", "finance.gross_profit_yuan",
                "finance.contribution_margin_rate", "platform.take_rate",
                "risk.flagged_order_rate", "risk.chargeback_rate", "risk.loss_amount_yuan",
            ),
            "ads-ecommerce-service-role-metrics.sql": (
                "service.first_contact_resolution_rate", "service.resolution_sla_rate",
                "service.order_defect_rate", "buyer.csat",
            ),
        }
        for filename, metric_ids in expectations.items():
            model = (analyticsctl.LAKEHOUSE / "models/ads" / filename).read_text(encoding="utf-8")
            for metric_id in metric_ids:
                self.assertIn(f"'{metric_id}'", model, f"{filename}:{metric_id}")
            self.assertIn("LOCAL_TEST_CANONICAL_CURRENT", model)
            self.assertNotIn("ads_ecommerce_role_metrics", model)

    def test_gap_backlog_has_priorities_owners_and_acceptance(self):
        backlog = analyticsctl.load_json(analyticsctl.BACKLOG)
        self.assertGreaterEqual(len(backlog["tasks"]), 7)
        self.assertTrue(any(task["priority"] == "P0" for task in backlog["tasks"]))
        for task in backlog["tasks"]:
            self.assertTrue(task["owner"])
            self.assertTrue(task["unlocks"])
            self.assertTrue(task["acceptance"])


if __name__ == "__main__":
    unittest.main()
