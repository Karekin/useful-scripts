import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = ROOT / "models" / "apply-order-v1.txt"
EVENT_MANIFEST = ROOT / "contracts" / "event-manifest-v1.json"
MODELS = (
    "models/dwd/dwd-canonical-legacy-trade-target-readiness-event.sql",
    "models/dim/dim-canonical-legacy-trade-target-readiness-item.sql",
    "models/dws/dws-canonical-legacy-trade-target-readiness.sql",
    "models/ads/ads-canonical-legacy-trade-target-readiness.sql",
)


class CanonicalLegacyTradeTargetReadinessModelsTest(unittest.TestCase):
    def test_contract_is_registered_and_keeps_import_closed(self):
        manifest = json.loads(EVENT_MANIFEST.read_text(encoding="utf-8"))
        contract = manifest["events"]["order.migration.legacy_trade_target_readiness_assessed"]
        self.assertEqual(contract["aggregate_type"], "legacy_trade_target_readiness")
        self.assertEqual([version["schema_version"] for version in contract["versions"]], [1, 2])
        version = contract["versions"][1]
        schema = json.loads((ROOT / "contracts" / version["payload_schema"])
                            .read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["canonical_import_allowed"]["const"], False)
        self.assertEqual(schema["properties"]["policy_version"]["const"],
                         "legacy-trade-target-readiness-v2")
        item = schema["properties"]["items"]["items"]["properties"]
        self.assertEqual(item["canonical_import_allowed"]["const"], False)
        for name in ("spu_mapping_status", "sku_mapping_status", "order_item_mapping_status",
                     "money_reconciliation_status", "mapping_readiness_status", "evidence_hash",
                     "product_identity_qualification_id", "historical_product_identity_status"):
            self.assertIn(name, item)

    def test_models_are_manifested_in_dependency_order(self):
        order = [line.strip() for line in MANIFEST.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.startswith("#")]
        positions = []
        for model in MODELS:
            self.assertEqual(order.count(model), 1)
            self.assertTrue((ROOT / model).is_file())
            positions.append(order.index(model))
        self.assertEqual(positions, sorted(positions))

    def test_readiness_requires_all_four_target_dimensions_and_exact_money(self):
        dws = (ROOT / MODELS[2]).read_text(encoding="utf-8")
        ads = (ROOT / MODELS[3]).read_text(encoding="utf-8")
        for metric in ("buyer_resolved_order_count", "order_mapping_qualified_count",
                       "lifecycle_mapping_qualified_count", "spu_mapping_qualified_item_count",
                       "sku_mapping_qualified_item_count", "order_item_mapping_qualified_count",
                       "exact_money_order_count", "exact_money_item_count",
                       "historical_product_identity_qualified_item_count",
                       "historical_product_identity_unqualified_item_count",
                       "mapping_admitted_order_count", "mapping_admitted_item_count"):
            self.assertIn(metric, dws)
        self.assertIn("BLOCKED_REQUIRES_EXPLICIT_TARGET_MAPPINGS", ads)
        self.assertIn("BLOCKED_HISTORICAL_PRODUCT_IDENTITY_NOT_QUALIFIED", ads)
        self.assertIn("TARGET_MAPPING_READY_BUT_BENEFIT_GOVERNANCE_BLOCKED", ads)
        self.assertIn("FALSE AS canonical_import_available", ads)
        self.assertIn("LOCAL_YUDAO_TRADE_NOT_YSHOPPING_SOURCE", ads)


if __name__ == "__main__":
    unittest.main()
