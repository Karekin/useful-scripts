import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "canonical_inventory_migration_canary_runner.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("canonical_inventory_migration_canary_runner", SCRIPT)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class InventoryMigrationCanaryRunnerTest(unittest.TestCase):
    def test_commands_are_deterministic_and_select_one_source(self):
        args = ("cmig15canary", "40000000-0000-4000-8000-000000000001",
                "40000000-0000-4000-8000-000000000002",
                "40000000-0000-4000-8000-000000000003",
                "40000000-0000-4000-8000-000000000004")
        first = RUNNER.commands(*args)
        self.assertEqual(first, RUNNER.commands(*args))
        self.assertEqual(first["receive"]["businessType"], "MIGRATION_CANARY")
        self.assertTrue(first["mapping"]["sourceMapping"]["sourceId"].startswith("migration-canary:"))
        self.assertIsNone(first["assess"]["sourceBalanceId"])
        self.assertEqual(first["qualify"]["lotTrackingPolicy"], "NOT_TRACKED")
        self.assertEqual(first["migrate"]["expectedVersion"], 1)
        self.assertEqual(first["fence_probe"]["businessType"], "MIGRATION_FENCE_PROBE")
        self.assertEqual(first["fence_probe"]["quantity"], "1.000000")
        self.assertNotEqual(first["fence_probe"]["idempotencyKey"], first["receive"]["idempotencyKey"])

    def test_plan_declares_one_opening_after_all_gates(self):
        output = io.StringIO()
        required = ["--owner-id", "40000000-0000-4000-8000-000000000001",
                    "--sku-id", "40000000-0000-4000-8000-000000000002",
                    "--warehouse-id", "40000000-0000-4000-8000-000000000003",
                    "--location-id", "40000000-0000-4000-8000-000000000004"]
        with contextlib.redirect_stdout(output):
            code = RUNNER.main(["--mode", "plan", "--run-id", "cmig15canary", *required])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["stages"], ["MAP_SOURCE", "CREATE_CANARY", "ASSESS", "QUALIFY", "MIGRATE",
                                             "VERIFY_SOURCE_FENCE"])
        self.assertEqual(result["opening_writes"], 1)


if __name__ == "__main__":
    unittest.main()
