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
        self.assertEqual([entry["schema_version"] for entry in contract["versions"]], [1, 2])
        self.assertEqual(contract["aggregate_type"],
                         "legacy_trade_product_identity_qualification_request")
        schema = json.loads((ROOT / "contracts" / contract["versions"][-1]["payload_schema"])
                            .read_text(encoding="utf-8"))
        properties = schema["properties"]
        self.assertEqual(properties["canonical_import_allowed"]["const"], False)
        self.assertEqual(properties["production_migration_enabled"]["const"], False)
        self.assertEqual(properties["policy_version"]["const"],
                         "legacy-trade-product-identity-qualification-v2")
        self.assertEqual(properties["evidence_verification_status"]["enum"],
                         ["VERIFIED", "LEGACY_UNVERIFIED"])
        self.assertEqual(properties["evidence_verifier_version"]["enum"],
                         ["filesystem-content-addressed-sha256-v1", "legacy-v0"])
        self.assertEqual(properties["evidence_content_length"]["maximum"], 65536)
        qualify_rule = next(
            rule for rule in schema["allOf"]
            if rule["if"]["properties"].get("action_type", {}).get("const") == "QUALIFY"
        )
        qualify_properties = qualify_rule["then"]["properties"]
        self.assertEqual(qualify_properties["evidence_verification_status"]["const"],
                         "VERIFIED")
        self.assertEqual(qualify_properties["evidence_verifier_version"]["const"],
                         "filesystem-content-addressed-sha256-v1")
        self.assertEqual(qualify_properties["evidence_content_length"]["minimum"], 1)
        self.assertEqual(properties["approval_count"]["maximum"], 2)
        self.assertTrue(properties["approval_roles"]["uniqueItems"])
        self.assertTrue(properties["approver_system_user_ids"]["uniqueItems"])

    def test_example_validates_against_contract(self):
        manifest = json.loads(EVENT_MANIFEST.read_text(encoding="utf-8"))
        contract = manifest["events"][
            "order.migration.legacy_trade_product_identity_qualification_reviewed"]
        example = json.loads((ROOT / "contracts" / contract["versions"][-1]["example"])
                             .read_text(encoding="utf-8"))["payload"]
        self.assertEqual(example["approval_count"], 2)
        self.assertEqual(set(example["approval_roles"]), {"DATA_OWNER", "CHANGE_MANAGER"})
        self.assertEqual(len(set(example["approver_system_user_ids"])), 2)
        self.assertNotIn(example["requester_system_user_id"],
                         example["approver_system_user_ids"])
        self.assertFalse(example["canonical_import_allowed"])
        self.assertFalse(example["production_migration_enabled"])
        self.assertEqual(example["source_evidence_uri"],
                         "evidence://sha256/" + example["historical_product_snapshot_hash"])

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
        self.assertIn("evidence_verification_mismatch_count", dws)
        self.assertIn("BLOCKED_HISTORICAL_PRODUCT_EVIDENCE_NOT_CONTENT_VERIFIED", ads)
        self.assertIn("FALSE AS canonical_import_available", ads)
        self.assertIn("FALSE AS production_migration_enabled", ads)
        self.assertIn("QUALIFICATION_REVIEW_IS_EVIDENCE_NOT_IMPORT_AUTHORITY", ads)


if __name__ == "__main__":
    unittest.main()
