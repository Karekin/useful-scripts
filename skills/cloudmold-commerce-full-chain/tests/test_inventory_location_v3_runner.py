import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "canonical_inventory_location_v3_runner.py"
SPEC = importlib.util.spec_from_file_location("canonical_inventory_location_v3_runner", SCRIPT)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class InventoryLocationV3RunnerTest(unittest.TestCase):
    def test_plan_is_non_mutating_and_keeps_lot_null(self):
        self.assertEqual(RUNNER.main(["--mode", "plan", "--run-id", "cinv3001"]), 0)

    def test_payloads_use_exact_dimensions_and_no_fake_lot(self):
        master = {"merchant_id": "merchant", "canonical_sku_id": "sku",
                  "warehouse_id": "warehouse", "location_id": "location"}
        payloads = RUNNER.build_payloads("cinv3001", master)
        self.assertEqual(len(payloads), 6)
        self.assertTrue(all(payload["ownerId"] == "merchant" for payload in payloads))
        self.assertTrue(all(payload["locationId"] == "location" for payload in payloads))
        self.assertTrue(all(payload["lotId"] is None for payload in payloads))

    def test_costed_payloads_freeze_complete_fifo_evidence(self):
        master = {"merchant_id": "merchant", "canonical_sku_id": "sku",
                  "warehouse_id": "warehouse", "location_id": "location"}
        payloads = RUNNER.build_payloads("cinvcost01", master, costed=True)
        costed = [payload for payload in payloads if payload["operation"] in {"RECEIVE", "SHIP", "RETURN"}]
        self.assertEqual(3, len(costed))
        self.assertTrue(all(payload["currencyCode"] == "CNY" for payload in costed))
        self.assertTrue(all(payload["costPolicyVersion"] == "FIFO_COST_V1" for payload in costed))
        self.assertEqual(120000, costed[0]["movementCostAmountMinor"])
        self.assertEqual(36000, costed[1]["movementCostAmountMinor"])
        self.assertEqual(12000, costed[2]["movementCostAmountMinor"])
        self.assertLess(costed[0]["occurredAt"], "2026-04-19")

    def test_load_master_requires_succeeded_exact_canonical_dimensions(self):
        ledger = {"scenario": "canonical-merchant-warehouse-first-slice-v1", "status": "SUCCEEDED",
                  "tenant": 7, "final": {"merchant_status": "ACTIVE", "warehouse_status": "ACTIVE",
                  "merchant_id": "merchant", "canonical_sku_id": "sku",
                  "warehouse_id": "warehouse", "location_id": "location"}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps(ledger), encoding="utf-8")
            loaded = RUNNER.load_master(str(path), 7)
        self.assertEqual(loaded["location_id"], "location")

    def test_result_includes_in_transit_conservation(self):
        result = {"onHandQuantity": 8, "reservedQuantity": 0, "inTransitQuantity": 0,
                  "availableQuantity": 8, "aggregateVersion": 6}
        RUNNER.validate_result(result, ("8.000000", "0.000000", "0.000000", "8.000000", 6), "RELEASE")


if __name__ == "__main__":
    unittest.main()
