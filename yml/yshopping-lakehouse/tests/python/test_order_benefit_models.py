import importlib.machinery
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
CONTRACT_LOADER = importlib.machinery.SourceFileLoader("order_benefit_contractctl", str(ROOT / "scripts/contractctl"))
CONTRACT_SPEC = importlib.util.spec_from_loader(CONTRACT_LOADER.name, CONTRACT_LOADER)
CONTRACT = importlib.util.module_from_spec(CONTRACT_SPEC)
CONTRACT_LOADER.exec_module(CONTRACT)
MANIFEST = json.loads((ROOT / "contracts/event-manifest-v1.json").read_text(encoding="utf-8"))
ORDER = [
    line.strip()
    for line in (ROOT / "models/apply-order-v1.txt").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.startswith("#")
]


class OrderBenefitModelsTest(unittest.TestCase):
    EVENT_TYPE = "order.benefit_application.recorded"

    def schema(self):
        config = MANIFEST["events"][self.EVENT_TYPE]
        return json.loads((ROOT / "contracts" / config["payload_schema"]).read_text(encoding="utf-8"))

    def test_event_is_exactly_manifested_on_the_order_aggregate(self):
        config = MANIFEST["events"][self.EVENT_TYPE]
        self.assertEqual(1, config["schema_version"])
        self.assertEqual("order", config["aggregate_type"])
        self.assertEqual(
            "events/order-benefit-application-recorded-v1.schema.json",
            config["payload_schema"],
        )
        schema = self.schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(schema["properties"]))

    def test_nested_application_allocation_and_funding_payload_is_strict(self):
        schema = self.schema()
        expected_application = {
            "run_id", "order_id", "order_no", "benefit_application_id", "application_key",
            "benefit_type", "benefit_source_type", "benefit_source_id", "benefit_source_version",
            "entitlement_id", "amount_minor", "currency_code", "calculation_digest", "allocations",
        }
        self.assertEqual(expected_application, set(schema["properties"]))
        allocation = schema["properties"]["allocations"]["items"]
        expected_allocation = {
            "benefit_allocation_id", "allocation_key", "order_item_id", "line_key",
            "amount_minor", "currency_code", "funding",
        }
        self.assertFalse(allocation["additionalProperties"])
        self.assertEqual(expected_allocation, set(allocation["required"]))
        self.assertEqual(expected_allocation, set(allocation["properties"]))
        funding = allocation["properties"]["funding"]["items"]
        expected_funding = {
            "benefit_funding_id", "funding_key", "funder_type", "funder_id",
            "amount_minor", "currency_code",
        }
        self.assertFalse(funding["additionalProperties"])
        self.assertEqual(expected_funding, set(funding["required"]))
        self.assertEqual(expected_funding, set(funding["properties"]))

    def test_backend_length_and_nullable_identity_boundaries_are_locked(self):
        properties = self.schema()["properties"]
        allocation = properties["allocations"]["items"]["properties"]
        funding = allocation["funding"]["items"]["properties"]
        self.assertEqual(128, properties["application_key"]["maxLength"])
        self.assertEqual(32, properties["benefit_source_type"]["maxLength"])
        self.assertEqual("^[A-Z][A-Z0-9_]*$", properties["benefit_source_type"]["pattern"])
        self.assertEqual(["string", "null"], properties["entitlement_id"]["type"])
        self.assertNotIn("format", properties["entitlement_id"])
        self.assertEqual(128, properties["entitlement_id"]["maxLength"])
        self.assertEqual(128, allocation["allocation_key"]["maxLength"])
        self.assertEqual(128, allocation["line_key"]["maxLength"])
        self.assertEqual(128, funding["funding_key"]["maxLength"])
        self.assertEqual(["COUPON", "PROMOTION", "ALLOWANCE", "CAMPAIGN"],
                         properties["benefit_type"]["enum"])
        self.assertEqual(["PLATFORM", "MERCHANT", "PARTNER"], funding["funder_type"]["enum"])
        self.assertEqual("^[0-9a-f]{64}$", properties["calculation_digest"]["pattern"])
        self.assertEqual(100, properties["allocations"]["maxItems"])
        self.assertEqual(10, allocation["funding"]["maxItems"])

    def test_example_proves_all_three_money_conservation_levels(self):
        config = MANIFEST["events"][self.EVENT_TYPE]
        example = json.loads((ROOT / "contracts" / config["example"]).read_text(encoding="utf-8"))
        self.assertEqual("order", example["aggregate_type"])
        self.assertEqual(example["aggregate_id"], example["payload"]["order_id"])
        self.assertEqual(1, example["aggregate_version"])
        self.assertEqual(2, example["event_sequence"])
        payload = example["payload"]
        self.assertEqual(payload["amount_minor"], sum(row["amount_minor"] for row in payload["allocations"]))
        for allocation in payload["allocations"]:
            self.assertEqual(allocation["amount_minor"],
                             sum(row["amount_minor"] for row in allocation["funding"]))

    def test_local_contract_gate_enforces_backend_array_caps(self):
        schema = self.schema()
        allocation_schema = schema["properties"]["allocations"]
        funding_schema = allocation_schema["items"]["properties"]["funding"]
        self.assertTrue(any("at most 100" in error for error in
                            CONTRACT.validate_instance([{}] * 101, allocation_schema, "$.allocations")))
        self.assertTrue(any("at most 10" in error for error in
                            CONTRACT.validate_instance([{}] * 11, funding_schema, "$.funding")))

    def test_models_follow_nested_and_layer_dependencies(self):
        positions = {entry: index for index, entry in enumerate(ORDER)}
        application = "models/dwd/dwd-canonical-order-benefit-application-event.sql"
        allocation = "models/dwd/dwd-canonical-order-benefit-allocation-event.sql"
        funding = "models/dwd/dwd-canonical-order-benefit-funding-event.sql"
        dimension = "models/dim/dim-canonical-order-benefit-application-current.sql"
        item = "models/dws/dws-canonical-order-item-benefit-current.sql"
        readiness = "models/ads/ads-canonical-order-benefit-readiness.sql"
        self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[application])
        self.assertLess(positions[application], positions[allocation])
        self.assertLess(positions[allocation], positions[funding])
        self.assertLess(positions[application], positions[dimension])
        self.assertLess(positions[dimension], positions[item])
        self.assertLess(positions["models/dws/dws-canonical-order-item-current.sql"], positions[item])
        self.assertLess(positions[item], positions[readiness])

    def test_item_and_readiness_models_fail_closed_on_money_or_empty_evidence(self):
        item = (ROOT / "models/dws/dws-canonical-order-item-benefit-current.sql").read_text(encoding="utf-8")
        readiness = (ROOT / "models/ads/ads-canonical-order-benefit-readiness.sql").read_text(encoding="utf-8")
        self.assertIn("gross_amount_minor", item)
        self.assertIn("discount_amount_minor", item)
        self.assertIn("net_amount_minor", item)
        self.assertIn("funding_mismatch_count", item)
        self.assertIn("item.line_amount_minor - COALESCE(benefit.discount_amount_minor, 0)", item)
        for token in (
            "header_discount_amount_minor", "application_amount_minor", "allocation_amount_minor",
            "funding_amount_minor", "item_discount_amount_minor", "NONEMPTY_IMMUTABLE_ORDER_BENEFIT_V1",
            "EVIDENCE_MISSING", "INCONSISTENT", "RECONCILED",
        ):
            self.assertIn(token, readiness)
        self.assertIn("FROM benefit_by_order benefit", readiness)
        self.assertNotIn("FROM (SELECT 1", readiness)

    def test_dqc_locks_conservation_identity_sequence_and_nonempty_readiness(self):
        dqc = (ROOT / "tests/sql/27-canonical-order-benefit-contract.sql").read_text(encoding="utf-8")
        for check in (
            "order_benefit_envelope_identity_invalid",
            "order_benefit_status_sequence_anchor_missing",
            "order_benefit_event_sequence_not_contiguous",
            "order_benefit_application_not_immutable",
            "order_benefit_application_allocation_not_conserved",
            "order_benefit_allocation_funding_not_conserved",
            "order_benefit_order_header_not_conserved",
            "order_benefit_order_item_orphan",
            "order_benefit_item_money_not_conserved",
            "order_benefit_readiness_unproven",
        ):
            self.assertIn(check, dqc)
        self.assertNotIn("order_benefit_runtime_evidence_absent", dqc)
        self.assertIn("source_system <> 'cloudmold-order'", dqc)
        self.assertIn("CHAR_LENGTH(application_key) NOT BETWEEN 1 AND 128", dqc)
        self.assertIn("CHAR_LENGTH(benefit_source_type) NOT BETWEEN 1 AND 32", dqc)
        self.assertIn("benefit_source_type REGEXP '^[A-Z][A-Z0-9_]*$'", dqc)
        self.assertIn("allocation.allocation_count, 0) NOT BETWEEN 1 AND 100", dqc)
        self.assertIn("funding.funding_count, 0) NOT BETWEEN 1 AND 10", dqc)
        self.assertIn("order_current.discount_amount_minor <> benefit.application_amount_minor", dqc)
        self.assertIn("gross_amount_minor <> discount_amount_minor + net_amount_minor", dqc)


if __name__ == "__main__":
    unittest.main()
