import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = ROOT / "models" / "apply-order-v1.txt"
EVENT_MANIFEST = ROOT / "contracts" / "event-manifest-v1.json"
MODELS = (
    "models/dwd/dwd-canonical-legacy-trade-product-identity-qualification-review-event.sql",
    "models/dim/dim-canonical-legacy-trade-product-identity-qualification-request-current.sql",
    "models/dws/dws-canonical-legacy-trade-product-identity-qualification-workflow.sql",
    "models/ads/ads-canonical-legacy-trade-product-identity-qualification-readiness.sql",
)


class CanonicalLegacyTradeProductIdentityQualificationModelsTest(unittest.TestCase):
    def test_contract_requires_two_independent_approvals_and_keeps_import_closed(self):
        manifest = json.loads(EVENT_MANIFEST.read_text(encoding="utf-8"))
        contract = manifest["events"][
            "order.migration.legacy_trade_product_identity_qualification_reviewed"]
        self.assertEqual(contract["schema_version"], 1)
        self.assertEqual(contract["aggregate_type"],
                         "legacy_trade_product_identity_qualification_request")
        schema = json.loads((ROOT / "contracts" / contract["payload_schema"])
                            .read_text(encoding="utf-8"))
        properties = schema["properties"]
        self.assertEqual(properties["canonical_import_allowed"]["const"], False)
        self.assertEqual(properties["production_migration_enabled"]["const"], False)
        self.assertEqual(properties["policy_version"]["const"],
                         "legacy-trade-product-identity-qualification-v1")
        self.assertEqual(properties["approval_count"]["maximum"], 2)
        self.assertTrue(properties["approval_roles"]["uniqueItems"])
        self.assertTrue(properties["approver_system_user_ids"]["uniqueItems"])

    def test_example_validates_against_contract(self):
        manifest = json.loads(EVENT_MANIFEST.read_text(encoding="utf-8"))
        contract = manifest["events"][
            "order.migration.legacy_trade_product_identity_qualification_reviewed"]
        example = json.loads((ROOT / "contracts" / contract["example"])
                             .read_text(encoding="utf-8"))["payload"]
        self.assertEqual(example["approval_count"], 2)
        self.assertEqual(set(example["approval_roles"]), {"DATA_OWNER", "CHANGE_MANAGER"})
        self.assertEqual(len(set(example["approver_system_user_ids"])), 2)
        self.assertNotIn(example["requester_system_user_id"],
                         example["approver_system_user_ids"])
        self.assertFalse(example["canonical_import_allowed"])
        self.assertFalse(example["production_migration_enabled"])

    def test_models_are_manifested_in_dependency_order(self):
        order = [line.strip() for line in MANIFEST.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.startswith("#")]
        positions = []
        for model in MODELS:
            self.assertEqual(order.count(model), 1)
            self.assertTrue((ROOT / model).is_file())
            positions.append(order.index(model))
        self.assertEqual(positions, sorted(positions))

    def test_readiness_is_evidence_only(self):
        dws = (ROOT / MODELS[2]).read_text(encoding="utf-8")
        ads = (ROOT / MODELS[3]).read_text(encoding="utf-8")
        self.assertIn("actor_separation_mismatch_count", dws)
        self.assertIn("approval_set_hash", dws)
        self.assertIn("FALSE AS canonical_import_available", ads)
        self.assertIn("FALSE AS production_migration_enabled", ads)
        self.assertIn("QUALIFICATION_REVIEW_IS_EVIDENCE_NOT_IMPORT_AUTHORITY", ads)


if __name__ == "__main__":
    unittest.main()
