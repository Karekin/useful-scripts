import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = ROOT / "models" / "apply-order-v1.txt"
EVENT_MANIFEST = ROOT / "contracts" / "event-manifest-v1.json"
DQC = ROOT / "tests" / "sql" / "31-canonical-legacy-trade-benefit-migration-contract.sql"
MODELS = (
    "models/dwd/dwd-canonical-legacy-trade-benefit-assessment-event.sql",
    "models/dim/dim-canonical-legacy-trade-benefit-component-assessment.sql",
    "models/dim/dim-canonical-legacy-trade-benefit-item-assessment.sql",
    "models/dim/dim-canonical-legacy-trade-benefit-item-component-reconciliation.sql",
    "models/dws/dws-canonical-legacy-trade-benefit-migration-assessment.sql",
    "models/ads/ads-canonical-legacy-trade-benefit-migration-readiness.sql",
)


class CanonicalLegacyTradeBenefitMigrationModelsTest(unittest.TestCase):
    def test_event_contract_is_registered_and_fail_closed(self):
        manifest = json.loads(EVENT_MANIFEST.read_text(encoding="utf-8"))
        contract = manifest["events"]["order.migration.legacy_trade_benefit_assessed"]
        self.assertEqual(contract["aggregate_type"], "legacy_trade_benefit_migration_assessment")
        self.assertEqual([version["schema_version"] for version in contract["versions"]], [1, 2])
        schema_v2 = json.loads((ROOT / "contracts" / contract["versions"][1]["payload_schema"])
                               .read_text(encoding="utf-8"))
        self.assertEqual(schema_v2["properties"]["canonical_import_allowed"]["const"], False)
        self.assertEqual(schema_v2["properties"]["item_evidence_complete"]["const"], True)
        component = schema_v2["properties"]["components"]["items"]["properties"]
        self.assertEqual(component["funding_resolution_status"]["const"], "MISSING_NAMED_FUNDER_BREAKDOWN")
        self.assertEqual(component["canonical_import_allowed"]["const"], False)
        item = schema_v2["properties"]["items"]["items"]["properties"]
        self.assertEqual(item["canonical_import_allowed"]["const"], False)
        self.assertIn("legacy_order_item_id", item)

    def test_models_are_manifested_in_dependency_order(self):
        order = [line.strip() for line in MANIFEST.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.startswith("#")]
        positions = []
        for model in MODELS:
            self.assertEqual(order.count(model), 1)
            self.assertTrue((ROOT / model).is_file())
            positions.append(order.index(model))
        self.assertEqual(positions, sorted(positions))

    def test_backend_is_reconciled_to_independent_offline_assessment(self):
        ads = (ROOT / MODELS[5]).read_text(encoding="utf-8")
        self.assertIn("dws_canonical_legacy_trade_benefit_migration_assessment backend", ads)
        self.assertIn("dws_legacy_trade_benefit_migration_assessment offline", ads)
        for metric in ("source_order_row_count", "non_deleted_order_count", "deleted_excluded_count",
                       "no_benefit_order_count", "benefit_evidence_pending_order_count",
                       "quarantined_order_count", "source_benefit_amount_minor", "component_count",
                       "component_amount_minor", "unresolved_identity_count", "unresolved_funding_count"):
            self.assertIn(f"backend.{metric} <> offline.{metric}", ads)
        self.assertIn("MATCHED_LOCAL_SNAPSHOT_BLOCKED_REQUIRES_GOVERNED_EVIDENCE", ads)

    def test_dqc_never_confuses_local_snapshot_with_yshopping_source(self):
        text = DQC.read_text(encoding="utf-8")
        self.assertIn("canonical_legacy_trade_backend_offline_mismatch", text)
        self.assertIn("canonical_legacy_trade_false_import_readiness", text)
        self.assertIn("LOCAL_YUDAO_TRADE_NOT_YSHOPPING_SOURCE", text)

    def test_item_denominator_is_projected_without_opening_import(self):
        dwd = (ROOT / MODELS[0]).read_text(encoding="utf-8")
        dim_item = (ROOT / MODELS[2]).read_text(encoding="utf-8")
        reconciliation = (ROOT / MODELS[3]).read_text(encoding="utf-8")
        dws = (ROOT / MODELS[4]).read_text(encoding="utf-8")
        self.assertIn("schema_version IN (1, 2)", dwd)
        self.assertIn("event.schema_version = 2", dim_item)
        self.assertIn("legacy_order_item_id", dim_item)
        self.assertIn("source_item_count", dws)
        self.assertIn("item_evidence_complete", dws)
        self.assertIn("import_allowed_item_count", dws)
        self.assertIn("item_component_amount_minor", reconciliation)
        self.assertIn("source_item_component_row_count", reconciliation)
        self.assertIn("excluded_item_component_row_count", reconciliation)
        self.assertIn("reconciliation_hash", reconciliation)
        self.assertIn("MISSING_HEADER_COMPONENT", reconciliation)
        self.assertIn("item_header_component_gap_minor", dws)
        self.assertIn("import_allowed_item_component_count", dws)


if __name__ == "__main__":
    unittest.main()
