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


class CustomerServiceBuyerCsatModelsTest(unittest.TestCase):
    def test_buyer_feedback_contract_is_registered_and_pii_minimized(self):
        self.assertIn("customer_service.buyer_feedback.recorded", MANIFEST["events"])
        schema = json.loads(
            (ROOT / "contracts/events/customer-service-buyer-feedback-recorded-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            schema["properties"]["sentiment_code"]["enum"],
            ["SATISFIED", "NEUTRAL", "DISSATISFIED"],
        )
        self.assertEqual(
            schema["properties"]["touchpoint_code"]["enum"],
            ["TICKET_RESOLUTION", "CLAIM_COMPENSATION", "AFTER_SALE_HANDLING"],
        )
        forbidden = {"comment", "body", "message_body", "phone", "email", "reviewer_principal_id"}
        self.assertTrue(forbidden.isdisjoint(schema["properties"]))
        self.assertIn("comment_token", schema["properties"])

    def test_csat_and_service_metric_models_are_dependency_ordered(self):
        positions = {entry: index for index, entry in enumerate(ORDER)}
        self.assertLess(
            positions["models/dwd/dwd-canonical-customer-service-event.sql"],
            positions["models/dwd/dwd-canonical-customer-service-buyer-feedback-event.sql"],
        )
        self.assertLess(
            positions["models/dwd/dwd-canonical-customer-service-buyer-feedback-event.sql"],
            positions["models/dim/dim-canonical-customer-service-buyer-feedback-current.sql"],
        )
        self.assertLess(
            positions["models/dim/dim-canonical-customer-service-buyer-feedback-current.sql"],
            positions["models/dws/dws-canonical-customer-service-buyer-csat-current.sql"],
        )
        self.assertLess(
            positions["models/dws/dws-canonical-customer-service-buyer-csat-current.sql"],
            positions["models/ads/ads-canonical-buyer-csat-readiness.sql"],
        )
        self.assertLess(
            positions["models/dws/dws-canonical-customer-service-service-metrics-current.sql"],
            positions["models/ads/ads-canonical-customer-service-service-metrics-readiness.sql"],
        )

    def test_service_metrics_models_use_governed_contact_and_reopen_semantics(self):
        dwd = (ROOT / "models/dwd/dwd-canonical-customer-service-event.sql").read_text(encoding="utf-8")
        self.assertIn("sla_policy_code", dwd)
        self.assertIn("resolution_deadline_at", dwd)
        self.assertIn("fcr_window_hours", dwd)
        dws = (
            ROOT / "models/dws/dws-canonical-customer-service-service-metrics-current.sql"
        ).read_text(encoding="utf-8")
        for needle in (
            "reopen_count",
            "resolution_sla_met_flag",
            "fcr_success_flag",
            "order_defect_case_flag",
        ):
            self.assertIn(needle, dws)
        ads = (
            ROOT / "models/ads/ads-canonical-customer-service-service-metrics-readiness.sql"
        ).read_text(encoding="utf-8")
        for needle in (
            "first_contact_resolution_rate_percent",
            "resolution_sla_rate_percent",
            "order_defect_case_rate_percent",
            "PARTIAL_REQUIRES_ORDER_DENOMINATOR",
        ):
            self.assertIn(needle, ads)

    def test_dqc_covers_feedback_and_service_metric_guards(self):
        dqc = (ROOT / "tests/sql/42-canonical-customer-service-buyer-csat-contract.sql").read_text(
            encoding="utf-8"
        )
        for check in (
            "customer_service_buyer_feedback_orphan_ticket",
            "customer_service_buyer_feedback_identity_mismatch",
            "customer_service_service_metrics_fcr_invalid",
            "customer_service_service_metrics_sla_invalid",
        ):
            self.assertIn(check, dqc)


if __name__ == "__main__":
    unittest.main()
