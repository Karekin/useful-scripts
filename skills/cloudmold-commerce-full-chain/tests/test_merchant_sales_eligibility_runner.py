import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "canonical_merchant_sales_eligibility_runner.py"
SPEC = importlib.util.spec_from_file_location("canonical_merchant_sales_eligibility_runner", SCRIPT)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class MerchantSalesEligibilityRunnerTest(unittest.TestCase):
    def test_plan_is_read_only(self):
        self.assertEqual(RUNNER.main(["--mode", "plan", "--run-id", "cmse001"]), 0)

    def test_context_is_deterministic(self):
        self.assertEqual(RUNNER.scenario_context("cmse001"), RUNNER.scenario_context("cmse001"))

    def test_execute_requires_succeeded_master_ledger(self):
        with self.assertRaisesRegex(RUNNER.ScenarioError, "requires --master-ledger"):
            RUNNER.load_master_ledger(None, 1)

    def test_loads_exact_offer_from_succeeded_master_ledger(self):
        ledger = {
            "scenario": "canonical-merchant-warehouse-first-slice-v1", "status": "SUCCEEDED", "tenant": 7,
            "final": {"principal_id": "principal", "merchant_id": "merchant", "merchant_status": "ACTIVE",
                      "shop_id": "shop", "shop_status": "ACTIVE", "listing_id": "listing",
                      "listing_status": "PUBLISHED", "canonical_sku_id": "sku"},
            "steps": [{"domain": "listing", "operation": "CREATE_DRAFT",
                       "result": {"offers": [{"listingOfferId": "offer", "enabled": True,
                                               "priceMinor": 19900, "currencyCode": "CNY"}]}}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps(ledger), encoding="utf-8")
            result = RUNNER.load_master_ledger(str(path), 7)
        self.assertEqual(result["listing_offer_id"], "offer")
        self.assertEqual(result["price_minor"], 19900)
        self.assertEqual(result["principal_id"], "principal")

    def test_rejects_non_succeeded_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps({"scenario": "canonical-merchant-warehouse-first-slice-v1",
                                        "status": "STARTED", "tenant": 1}), encoding="utf-8")
            with self.assertRaisesRegex(RUNNER.ScenarioError, "not SUCCEEDED"):
                RUNNER.load_master_ledger(str(path), 1)


if __name__ == "__main__":
    unittest.main()
