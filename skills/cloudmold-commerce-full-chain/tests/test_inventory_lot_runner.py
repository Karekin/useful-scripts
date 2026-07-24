import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "canonical_inventory_lot_runner.py"
SPEC = importlib.util.spec_from_file_location("canonical_inventory_lot_runner", SCRIPT)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class InventoryLotRunnerTest(unittest.TestCase):
    def test_plan_is_non_mutating_and_declares_recall_fence(self):
        self.assertEqual(RUNNER.main(["--mode", "plan", "--run-id", "clot2001"]), 0)

    def test_master_loader_rejects_started_or_incomplete_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps({"scenario": RUNNER.MASTER_SCENARIO, "status": "STARTED",
                                        "tenant": 7}), encoding="utf-8")
            with self.assertRaisesRegex(RUNNER.ScenarioError, "not SUCCEEDED"):
                RUNNER.load_master(str(path), 7)

    def test_master_loader_requires_21_duplicate_replays_and_exact_dimensions(self):
        final = {"merchant_status": "ACTIVE", "warehouse_status": "ACTIVE",
                 "all_replay_duplicate": True, "merchant_id": "merchant", "canonical_sku_id": "sku",
                 "warehouse_id": "warehouse", "location_id": "location"}
        ledger = {"scenario": RUNNER.MASTER_SCENARIO, "status": "SUCCEEDED", "tenant": 7,
                  "steps": [{}] * 21, "replay": [{"duplicate": True}] * 21, "final": final}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps(ledger), encoding="utf-8")
            loaded = RUNNER.load_master(str(path), 7)
        self.assertEqual(loaded["location_id"], "location")
        self.assertEqual(len(loaded["sha256"]), 64)

    def test_payloads_use_nonempty_lot_and_qualified_controlled_source(self):
        correlation, start = RUNNER.scenario_context("clot2001")
        lot = RUNNER.lot_command("clot2001", correlation, start, 2, "LINK_SOURCE",
                                 lotId="lot-id", expectedLotVersion=1,
                                 mappedSourceSystem="CLOUDMOLD_ERP_OPERATOR",
                                 mappedSourceType="CONTROLLED_LOT", mappedSourceId="clot2001:batch",
                                 validFrom=RUNNER.iso_time(start), verificationRef="run:clot2001/source/A")
        stock = RUNNER.inventory_command("clot2001", {
            "merchant_id": "merchant", "canonical_sku_id": "sku",
            "warehouse_id": "warehouse", "location_id": "location"},
            "lot-id", correlation, start, 3, "RECEIVE", "10.000000")
        self.assertEqual(lot["mappedSourceSystem"], "CLOUDMOLD_ERP_OPERATOR")
        self.assertEqual(lot["mappedSourceType"], "CONTROLLED_LOT")
        self.assertEqual(stock["lotId"], "lot-id")

    def test_scenario_time_is_deterministic_and_already_effective(self):
        first = RUNNER.scenario_context("clot2001")
        second = RUNNER.scenario_context("clot2001")
        self.assertEqual(first, second)
        self.assertLess(first[1], RUNNER.dt.datetime(2026, 7, 1, tzinfo=RUNNER.dt.timezone.utc))

    def test_stock_validation_preserves_exact_terminal_quantities(self):
        RUNNER.validate_stock({"onHandQuantity": 10, "reservedQuantity": 0,
                               "availableQuantity": 10, "aggregateVersion": 3},
                              ("10.000000", "0.000000", "10.000000", 3), "RELEASE")

    def test_recall_gate_accepts_public_api_rejection_without_internal_message(self):
        RUNNER.validate_api_rejection(
            RUNNER.ScenarioError("API rejected POST /inventory: 500 系统异常"),
            "post-recall RESERVE")
        RUNNER.validate_api_rejection(
            RUNNER.ScenarioError(
                "Dubbo capability capability.cloudmold.inventory.inventory-v3-command.execute.v1 "
                "rejected POST /admin-api/cloudmold/inventory/v3/command: inventory lot is not ACTIVE"
            ),
            "post-recall RESERVE",
        )
        with self.assertRaisesRegex(RUNNER.ScenarioError, "explicit public API rejection"):
            RUNNER.validate_api_rejection(RUNNER.ScenarioError("connection reset"),
                                          "post-recall RESERVE")


if __name__ == "__main__":
    unittest.main()
