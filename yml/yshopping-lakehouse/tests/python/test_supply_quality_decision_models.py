import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


class SupplyQualityDecisionModelsTest(unittest.TestCase):
    def test_models_are_dependency_ordered(self):
        order = [
            line.strip()
            for line in (ROOT / "models/apply-order-v1.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        positions = {entry: index for index, entry in enumerate(order)}
        for domain in ("supply-planning", "quality"):
            dwd = f"models/dwd/dwd-canonical-{domain}-event.sql"
            dws = f"models/dws/dws-canonical-{domain}-current.sql"
            ads = f"models/ads/ads-canonical-{domain}-readiness.sql"
            self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[dwd])
            self.assertLess(positions[dwd], positions[dws])
            self.assertLess(positions[dws], positions[ads])

    def test_supply_metrics_preserve_denominators_and_evidence(self):
        dwd = (ROOT / "models/dwd/dwd-canonical-supply-planning-event.sql").read_text(
            encoding="utf-8"
        )
        ads = (ROOT / "models/ads/ads-canonical-supply-planning-readiness.sql").read_text(
            encoding="utf-8"
        )
        for field in (
            "actuals_sha256",
            "wape_basis_points",
            "bias_basis_points",
            "mae",
            "parameters_sha256",
            "policy_sha256",
        ):
            self.assertIn(field, dwd)
        self.assertIn("forecast_evaluation_count", ads)
        self.assertIn("inventory_health_scan_count", ads)
        self.assertIn("scenario_recommendation_count", ads)
        self.assertIn("average_worst_case_service_level_basis_points", ads)
        self.assertIn("supply_planning.plan_scenario.recommended", dwd)
        self.assertIn("execution_authorized", dwd)

    def test_quality_metrics_use_final_ground_truth(self):
        ads = (ROOT / "models/ads/ads-canonical-quality-readiness.sql").read_text(
            encoding="utf-8"
        )
        self.assertIn("COALESCE(ground_truth_decision,decision)", ads)
        self.assertIn("independent_review_agreement_rate", ads)
        self.assertIn("authentication_accuracy_rate", ads)
        self.assertIn("authentication_recall_rate", ads)
        self.assertIn("authentication_precision_rate", ads)
        self.assertIn("NULLIF(task.ground_truth_failed_task_count, 0)", ads)
        self.assertIn("active_recall_action_count", ads)


if __name__ == "__main__":
    unittest.main()
