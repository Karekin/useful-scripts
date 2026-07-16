import subprocess
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "lakehousectl"


class LakehouseCtlContractTest(unittest.TestCase):
    def run_ctl(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(SCRIPT), *args], text=True, capture_output=True, check=False)

    def test_usage_registers_master_data_reconciliation_commands(self):
        result = self.run_ctl()
        self.assertEqual(result.returncode, 2)
        self.assertIn("reconcile-canonical-order-benefit", result.stdout)
        self.assertIn("reconcile-canonical-merchant", result.stdout)
        self.assertIn("reconcile-canonical-merchant-deposit", result.stdout)
        self.assertIn("reconcile-canonical-warehouse-network", result.stdout)
        self.assertIn("reconcile-canonical-listing-unpublish-saga", result.stdout)
        self.assertIn("reconcile-canonical-inventory-migration", result.stdout)
        self.assertIn("reconcile-legacy-trade-benefit-assessment", result.stdout)
        self.assertIn("submit-legacy-mall-cdc", result.stdout)

    def test_legacy_trade_benefit_assessment_fails_closed_on_missing_evidence(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"$source_benefit" == "$component_amount"', script)
        self.assertIn('"$unresolved_identity" == "$components"', script)
        self.assertIn('"$unresolved_funding" == "$components"', script)
        self.assertIn('"$import_allowed" == "0"', script)
        self.assertIn('"$production_enabled" == "0"', script)
        self.assertIn('"$readiness" == "BLOCKED_REQUIRES_GOVERNED_EVIDENCE"', script)
        self.assertIn('"$source_scope" == "LOCAL_YUDAO_TRADE_NOT_YSHOPPING_SOURCE"', script)

    def test_order_benefit_reconciliation_requires_nonempty_conserved_evidence(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"$applications" =~ ^[1-9][0-9]*$', script)
        self.assertIn('"$header_discount" == "$application_amount"', script)
        self.assertIn('"$application_amount" == "$allocation_amount"', script)
        self.assertIn('"$allocation_amount" == "$funding_amount"', script)
        self.assertIn('"$funding_amount" == "$item_discount"', script)
        self.assertIn('"$readiness" == "RECONCILED"', script)

    def test_aftersales_reconciliation_accepts_partial_and_full_cumulative_returns(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('saga_baseline=8', script)
        self.assertIn('saga_baseline=10', script)
        self.assertIn('saga_baseline=$((saga_baseline + 4))', script)
        self.assertIn('$(((saga_version - saga_baseline) % 2)) -eq 0', script)
        self.assertIn('"$gross" -eq $((benefit + net))', script)
        self.assertIn('"$benefit_reversal_status" == "RECORDED"', script)
        self.assertIn('"$recorded_benefit" == "$benefit"', script)
        self.assertIn('"$funding_reversed" == "$benefit"', script)
        self.assertIn('"$entitlement_apps" == "$entitlement_effects"', script)
        self.assertIn('"$payment_effect_status" == "PARTIALLY_REFUNDED"', script)
        self.assertIn('"$payment_effect_status" == "REFUNDED"', script)
        self.assertIn('"$settlement_qty" == "$requested_qty"', script)

    def test_aftersales_reconciliation_rejects_non_uuid_after_sale_id(self):
        result = self.run_ctl(
            "reconcile-canonical-aftersales",
            "--tenant", "1",
            "--run-id", "run-1",
            "--after-sale-id", "not-a-uuid",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--after-sale-id must be a UUID", result.stderr)

    def test_aftersales_reconciliation_can_select_one_case_from_a_multi_case_run(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("after_sale_filter=\" AND after_sale_id='$AFTER_SALE_ID'\"", script)
        self.assertIn("run_id='$safe_run_id'$after_sale_filter", script)

    def test_merchant_reconciliation_rejects_non_uuid_before_querying(self):
        result = self.run_ctl(
            "reconcile-canonical-merchant", "--tenant", "1", "--merchant-id", "not-a-uuid"
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--merchant-id must be a UUID", result.stderr)

    def test_merchant_reconciliation_accepts_cumulative_lifecycle_events(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"$merchant_events" -ge 2', script)
        self.assertIn('"$shop_events" -ge 2', script)
        self.assertIn('"$ledger_entries" == "$account_version"', script)
        self.assertIn('"$saga_readiness" == "RECONCILED"', script)

    def test_source_reference_rejects_sql_metacharacters_before_querying(self):
        result = self.run_ctl(
            "reconcile-canonical-warehouse-network",
            "--tenant", "1",
            "--warehouse-id", "10000000-0000-4000-8000-000000000001",
            "--source-system", "ERP",
            "--source-type", "WAREHOUSE",
            "--source-id", "3' OR 1=1",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--source-id contains unsupported characters", result.stderr)

    def test_listing_unpublish_reconciliation_rejects_non_uuid_saga(self):
        result = self.run_ctl(
            "reconcile-canonical-listing-unpublish-saga",
            "--tenant", "1",
            "--run-id", "run-1",
            "--saga-id", "not-a-uuid",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--saga-id must be a UUID", result.stderr)

    def test_inventory_migration_reconciliation_requires_uuid_run_id(self):
        result = self.run_ctl(
            "reconcile-canonical-inventory-migration", "--tenant", "1", "--run-id", "not-a-uuid"
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--run-id must be a UUID for canonical Inventory migration", result.stderr)


if __name__ == "__main__":
    unittest.main()
