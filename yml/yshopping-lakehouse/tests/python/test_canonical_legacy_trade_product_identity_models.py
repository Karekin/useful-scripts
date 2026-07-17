import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = ROOT / "models" / "apply-order-v1.txt"
EVENT_MANIFEST = ROOT / "contracts" / "event-manifest-v1.json"
MODELS = (
    "models/dwd/dwd-canonical-legacy-trade-product-identity-event.sql",
    "models/dim/dim-canonical-legacy-trade-product-identity-item.sql",
    "models/dws/dws-canonical-legacy-trade-product-identity.sql",
    "models/ads/ads-canonical-legacy-trade-product-identity-readiness.sql",
)


class CanonicalLegacyTradeProductIdentityModelsTest(unittest.TestCase):
    def test_contract_requires_historical_qualification_and_keeps_import_closed(self):
        manifest = json.loads(EVENT_MANIFEST.read_text(encoding="utf-8"))
        contract = manifest["events"]["order.migration.legacy_trade_product_identity_assessed"]
        self.assertEqual(contract["schema_version"], 1)
        self.assertEqual(contract["aggregate_type"], "legacy_trade_product_identity")
        schema = json.loads((ROOT / "contracts" / contract["payload_schema"])
                            .read_text(encoding="utf-8"))
        properties = schema["properties"]
        self.assertEqual(properties["policy_version"]["const"],
                         "legacy-trade-product-identity-v1")
        for name in ("source_item_evidence_hash", "source_parent_cardinality",
                     "source_pair_status", "current_reference_status",
                     "current_product_snapshot_hash", "qualification_id",
                     "historical_identity_status", "identity_admission_allowed",
                     "target_mapping_allowed", "governance_evidence_hash"):
            self.assertIn(name, properties)

    def test_models_are_manifested_in_dependency_order(self):
        order = [line.strip() for line in MANIFEST.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.startswith("#")]
        positions = []
        for model in MODELS:
            self.assertEqual(order.count(model), 1)
            self.assertTrue((ROOT / model).is_file())
            positions.append(order.index(model))
        self.assertEqual(positions, sorted(positions))

    def test_current_catalog_is_only_observation_and_target_mapping_fails_closed(self):
        dwd = (ROOT / MODELS[0]).read_text(encoding="utf-8")
        dws = (ROOT / MODELS[2]).read_text(encoding="utf-8")
        ads = (ROOT / MODELS[3]).read_text(encoding="utf-8")
        self.assertIn("CURRENT_RELATION_OBSERVED_NOT_HISTORICAL_VERSION", dws)
        self.assertIn("historical_identity_qualified_count", dws)
        self.assertIn("CURRENT_CATALOG_RELATION_IS_OBSERVATION_ONLY", ads)
        self.assertIn("BLOCKED_REQUIRES_HISTORICAL_PRODUCT_IDENTITY", ads)
        self.assertIn("FALSE AS canonical_import_available", ads)
        self.assertIn("legacy_trade_product_identity", dwd)


if __name__ == "__main__":
    unittest.main()
