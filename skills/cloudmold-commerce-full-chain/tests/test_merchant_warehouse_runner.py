import importlib.util
from pathlib import Path
import unittest
import uuid


SCRIPT = Path(__file__).parents[1] / "scripts" / "canonical_merchant_warehouse_runner.py"
SPEC = importlib.util.spec_from_file_location("canonical_merchant_warehouse_runner", SCRIPT)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class MerchantWarehouseRunnerTest(unittest.TestCase):
    def test_context_is_deterministic_and_utc(self):
        first = RUNNER.scenario_context("cmw001")
        second = RUNNER.scenario_context("cmw001")
        self.assertEqual(first, second)
        self.assertEqual(first[1].tzinfo, RUNNER.dt.timezone.utc)
        self.assertLess(first[1], RUNNER.dt.datetime(2025, 1, 1, tzinfo=RUNNER.dt.timezone.utc))

    def test_plan_is_read_only(self):
        self.assertEqual(RUNNER.main(["--mode", "plan", "--run-id", "cmw001"]), 0)

    def test_execute_requires_explicit_source_references(self):
        args = RUNNER.parse_args(["--mode", "execute", "--run-id", "cmw001"])
        self.assertIsNone(args.system_admin_source_id)
        self.assertIsNone(args.erp_warehouse_source_id)

    def test_source_id_pattern_rejects_sql_metacharacters(self):
        self.assertIsNone(RUNNER.SOURCE_ID_PATTERN.fullmatch("3' OR 1=1"))

    def test_command_ids_are_run_scoped(self):
        correlation, occurred_at = RUNNER.scenario_context("cmw001")
        command = RUNNER.base_command("DEFINE_WAREHOUSE", "cmw001", 1, correlation, occurred_at)
        self.assertEqual(command["idempotencyKey"], "cmw001-01-define-warehouse")
        self.assertEqual(command["sourceEventId"], "cmw001:01:DEFINE_WAREHOUSE")

    def test_long_source_event_id_falls_back_to_deterministic_uuid(self):
        correlation, occurred_at = RUNNER.scenario_context("cmw15master")
        command = RUNNER.base_command(
            "CHANGE_WAREHOUSE_STATUS", "cmw15master", 2, correlation, occurred_at
        )
        expected = str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            "cloudmold:warehouse:cmw15master:02:CHANGE_WAREHOUSE_STATUS",
        ))
        self.assertEqual(command["sourceEventId"], expected)
        self.assertEqual(len(command["sourceEventId"]), 36)

    def test_catalog_ledger_must_prove_active_same_tenant_catalog(self):
        with self.assertRaisesRegex(RUNNER.ScenarioError, "requires --catalog-ledger"):
            RUNNER.load_catalog_identity(None, 1)

    def test_identity_resolve_route_is_a_read_only_precondition(self):
        self.assertEqual(RUNNER.IDENTITY_RESOLVE_ROUTE,
                         "/admin-api/cloudmold/identity/source/resolve")
        self.assertEqual(RUNNER.WAREHOUSE_RESOLVE_ROUTE,
                         "/admin-api/cloudmold/warehouse/source/resolve-network")


if __name__ == "__main__":
    unittest.main()
