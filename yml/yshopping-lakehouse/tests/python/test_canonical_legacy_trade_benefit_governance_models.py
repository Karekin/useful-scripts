import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = ROOT / "models" / "apply-order-v1.txt"
EVENT_MANIFEST = ROOT / "contracts" / "event-manifest-v1.json"
EVENT_TYPE = "order.migration.legacy_trade_benefit_governance_assessed"
MODELS = (
    "models/dwd/dwd-canonical-legacy-trade-benefit-governance-event.sql",
    "models/dim/dim-canonical-legacy-trade-benefit-governance-component.sql",
    "models/dim/dim-canonical-legacy-trade-benefit-governance-quarantine.sql",
    "models/dws/dws-canonical-legacy-trade-benefit-governance.sql",
    "models/ads/ads-canonical-legacy-trade-benefit-governance-readiness.sql",
)


class CanonicalLegacyTradeBenefitGovernanceModelsTest(unittest.TestCase):
    def test_contract_separates_current_observation_from_historical_qualification(self):
        manifest = json.loads(EVENT_MANIFEST.read_text(encoding="utf-8"))
        contract = manifest["events"][EVENT_TYPE]
        self.assertEqual(contract["aggregate_type"],
                         "legacy_trade_benefit_governance_readiness")
        self.assertEqual([version["schema_version"] for version in contract["versions"]], [1, 2])
        schema = json.loads((ROOT / "contracts" / contract["versions"][-1]["payload_schema"])
                            .read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["production_migration_enabled"]["const"], False)
        self.assertEqual(schema["properties"]["policy_version"]["const"],
                         "legacy-trade-benefit-governance-v1")
        component = schema["$defs"]["component"]["properties"]
        self.assertIn("CURRENT_REFERENCE_OBSERVED_NOT_HISTORICAL_VERSION",
                      component["current_reference_status"]["enum"])
        self.assertIn("historical_identity_status", component)
        self.assertIn("identity_qualification_id", component)
        self.assertIn("funding_share_count", component)
        self.assertIn("funding_amount_minor", component)
        self.assertEqual(component["canonical_import_allowed"]["const"], False)
        quarantine = schema["$defs"]["quarantine"]["properties"]
        self.assertIn("decision_id", quarantine)
        self.assertIn("source_candidate_evidence_hash", quarantine)
        self.assertEqual(quarantine["canonical_import_allowed"]["const"], False)

    def test_models_are_manifested_in_dependency_order(self):
        order = [line.strip() for line in MANIFEST.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.startswith("#")]
        positions = []
        for model in MODELS:
            self.assertEqual(order.count(model), 1)
            self.assertTrue((ROOT / model).is_file())
            positions.append(order.index(model))
        self.assertEqual(positions, sorted(positions))

    def test_rollup_requires_identity_funding_quarantine_and_separate_admission(self):
        dws = (ROOT / MODELS[3]).read_text(encoding="utf-8")
        ads = (ROOT / MODELS[4]).read_text(encoding="utf-8")
        dwd = (ROOT / MODELS[0]).read_text(encoding="utf-8")
        self.assertIn("schema_version IN (1, 2)", dwd)
        self.assertIn("governance_evaluation_id", dwd)
        for metric in ("current_reference_observed_count",
                       "historical_identity_qualified_count", "identity_blocked_count",
                       "funding_qualified_count", "funding_blocked_count",
                       "quarantine_decided_count", "quarantine_open_count",
                       "governance_admitted_component_count"):
            self.assertIn(metric, dws)
            self.assertIn(metric, ads)
        self.assertIn("BLOCKED_REQUIRES_HISTORICAL_BENEFIT_FUNDING_AND_QUARANTINE_DECISIONS", ads)
        self.assertIn("READY_FOR_SEPARATE_COMBINED_ADMISSION_DECISION", ads)
        self.assertIn("exact_target_mapping_available", ads)
        self.assertIn("FALSE AS canonical_import_available", ads)
        self.assertIn("LOCAL_YUDAO_TRADE_NOT_YSHOPPING_SOURCE", ads)


if __name__ == "__main__":
    unittest.main()
