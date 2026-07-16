import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = ROOT / "models" / "apply-order-v1.txt"
DQC = ROOT / "tests" / "sql" / "30-legacy-trade-benefit-migration-assessment-contract.sql"
MODELS = (
    "models/dwd/dwd-legacy-trade-benefit-assessment.sql",
    "models/dim/dim-legacy-trade-benefit-component-assessment.sql",
    "models/dws/dws-legacy-trade-benefit-migration-assessment.sql",
    "models/ads/ads-legacy-trade-benefit-migration-readiness.sql",
)


class LegacyTradeBenefitMigrationModelsTest(unittest.TestCase):
    def test_models_are_manifested_once_in_dependency_order(self):
        entries = [line.strip() for line in MANIFEST.read_text(encoding="utf-8").splitlines()
                   if line.strip() and not line.startswith("#")]
        positions = []
        for entry in MODELS:
            self.assertEqual(entries.count(entry), 1)
            self.assertTrue((ROOT / entry).is_file())
            positions.append(entries.index(entry))
        self.assertEqual(positions, sorted(positions))

    def test_assessment_uses_all_four_legacy_money_components(self):
        dwd = (ROOT / MODELS[0]).read_text(encoding="utf-8")
        dim = (ROOT / MODELS[1]).read_text(encoding="utf-8")
        for component in ("discount_price", "coupon_price", "point_price", "vip_price"):
            self.assertIn(component, dwd)
        for component_type in ("GENERIC_DISCOUNT", "COUPON", "POINT", "VIP"):
            self.assertIn(f"'{component_type}' AS legacy_component_type", dim)

    def test_unknown_identity_and_funding_fail_closed(self):
        combined = "\n".join((ROOT / entry).read_text(encoding="utf-8") for entry in MODELS)
        self.assertIn("MISSING_NAMED_FUNDER_BREAKDOWN", combined)
        self.assertIn("FALSE AS canonical_import_allowed", combined)
        self.assertIn("FALSE AS production_migration_enabled", combined)
        self.assertIn("BLOCKED_REQUIRES_GOVERNED_EVIDENCE", combined)
        self.assertNotIn("FROM yshopping_ods.ods_trade_trade_discount_di", combined)

    def test_source_scope_is_not_mislabeled_as_yshopping(self):
        ads = (ROOT / MODELS[3]).read_text(encoding="utf-8")
        self.assertIn("LOCAL_YUDAO_TRADE_NOT_YSHOPPING_SOURCE", ads)
        self.assertIn("exact_order_item_mapping_available", ads)
        self.assertIn("versioned_benefit_identity_available", ads)
        self.assertIn("named_funding_breakdown_available", ads)

    def test_dqc_preserves_denominator_and_rejects_false_readiness(self):
        text = DQC.read_text(encoding="utf-8")
        self.assertIn("legacy_trade_source_to_assessment_count_mismatch", text)
        self.assertIn("legacy_trade_component_amount_mismatch", text)
        self.assertIn("legacy_trade_false_migration_readiness", text)
        self.assertIn("source_benefit_amount_minor <> component_amount_minor", text)


if __name__ == "__main__":
    unittest.main()
