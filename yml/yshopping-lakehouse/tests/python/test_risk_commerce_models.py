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


class RiskCommerceModelsTest(unittest.TestCase):
    def test_risk_commerce_events_are_manifested(self):
        for event_name in (
            "risk.order_review.linked",
            "risk.payment_dispute.status_changed",
            "risk.loss_entry.posted",
        ):
            self.assertIn(event_name, MANIFEST["events"])

    def test_risk_commerce_models_have_dependency_order(self):
        positions = {entry: index for index, entry in enumerate(ORDER)}
        self.assertLess(
            positions["models/dwd/dwd-canonical-risk-event.sql"],
            positions["models/dwd/dwd-canonical-risk-commerce-event.sql"],
        )
        self.assertLess(
            positions["models/dwd/dwd-canonical-risk-commerce-event.sql"],
            positions["models/dim/dim-canonical-risk-commerce-current.sql"],
        )
        self.assertLess(
            positions["models/dim/dim-canonical-risk-commerce-current.sql"],
            positions["models/dws/dws-canonical-risk-commerce-current.sql"],
        )
        self.assertLess(
            positions["models/dws/dws-canonical-risk-commerce-current.sql"],
            positions["models/ads/ads-canonical-risk-commerce-metrics.sql"],
        )

    def test_metrics_are_wired_into_role_surface(self):
        risk_sql = (ROOT / "models/ads/ads-canonical-risk-commerce-metrics.sql").read_text(encoding="utf-8")
        role_sql = (ROOT / "models/ads/ads-ecommerce-role-metrics.sql").read_text(encoding="utf-8")
        for metric_id in (
            "risk.flagged_order_rate",
            "risk.chargeback_rate",
            "risk.loss_amount_yuan",
            "service.order_defect_rate",
        ):
            self.assertIn(metric_id, risk_sql)
        self.assertIn("ads_canonical_risk_commerce_metrics", role_sql)


if __name__ == "__main__":
    unittest.main()
