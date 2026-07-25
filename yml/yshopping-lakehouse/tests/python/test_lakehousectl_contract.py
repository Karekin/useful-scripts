import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Optional


SCRIPT = Path(__file__).parents[2] / "scripts" / "lakehousectl"
TRADE_SOURCE_DOCUMENT = Path(
    "/Users/karekin/Library/Mobile Documents/iCloud~md~obsidian/Documents/project/"
    "语兴好物（y shopping）-电商数仓搭建/ODS语兴好物（y shopping）电商数据表.md"
)


class LakehouseCtlContractTest(unittest.TestCase):
    def run_ctl(
        self, *args: str, env: Optional[Dict[str, str]] = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    def runtime_mock_environment(self, root: Path) -> Dict[str, str]:
        bin_dir = root / "bin"
        state_dir = root / "state"
        bin_dir.mkdir()
        state_dir.mkdir()
        docker = bin_dir / "docker"
        docker.write_text(
            """#!/usr/bin/env python3
import os
import pathlib
import sys

args = sys.argv[1:]
state = pathlib.Path(os.environ["MOCK_STATE_DIR"])
if args and args[0] == "inspect":
    print(os.environ.get("MOCK_STARROCKS_HEALTH", "healthy"))
elif args and args[0] == "exec":
    command = args[-1]
    if "df -Pk" in command:
        print(os.environ.get("MOCK_STARROCKS_FREE_KB", "10485760"))
    elif "test" in args and "-r" in args:
        if os.environ.get("MOCK_SAVEPOINT_PATH_MISSING") == "1":
            raise SystemExit(1)
    elif "savepoints" in command:
        print("4")
    elif "checkpoints" in command:
        print("8")
    else:
        raise SystemExit(2)
elif "compose" in args and "run" in args:
    mapping = {
        "event-cdc-cli": "outbox",
        "cdc-cli": "erp",
        "catalog-cdc-cli": "catalog",
        "legacy-mall-cdc-cli": "legacy_mall",
    }
    service = next((candidate for candidate in mapping if candidate in args), None)
    if service is None:
        raise SystemExit(2)
    key = mapping[service]
    with (state / "submission-order").open("a", encoding="utf-8") as handle:
        handle.write(service + "\\n")
    if os.environ.get("MOCK_RESTORE_FAILURE_SERVICE") == service:
        raise SystemExit(1)
    (state / key).write_text("submitted", encoding="utf-8")
else:
    raise SystemExit(2)
""",
            encoding="utf-8",
        )
        curl = bin_dir / "curl"
        curl.write_text(
            """#!/usr/bin/env python3
import json
import os
import pathlib
import sys

if os.environ.get("MOCK_API_FAILURE") == "1":
    raise SystemExit(22)
url = sys.argv[-1]
method = "POST" if "POST" in sys.argv else "GET"
state = pathlib.Path(os.environ["MOCK_STATE_DIR"])
jobs = [
    ("outbox", "job-outbox", "CloudMold Domain Event Outbox to StarRocks ODS"),
    ("erp", "job-erp", "Y Shopping ERP MySQL to StarRocks ODS"),
    ("catalog", "job-catalog", "Y Shopping Catalog MySQL to StarRocks ODS"),
    ("legacy_mall", "job-legacy", "Y Shopping Legacy Mall Alignment MySQL to StarRocks ODS"),
]
if ":8030/api/health" in url:
    print(json.dumps({"status": os.environ.get("MOCK_STARROCKS_API_STATUS", "OK")}))
elif url.endswith("/taskmanagers"):
    slots = int(os.environ.get("MOCK_TOTAL_SLOTS", "4"))
    print(json.dumps({"taskmanagers": [{"slotsNumber": slots, "freeSlots": slots}]}))
elif url.endswith("/jobs/overview"):
    job_state = os.environ.get("MOCK_JOB_STATE", "RUNNING")
    print(json.dumps({"jobs": [
        {"jid": job_id, "name": name, "state": job_state}
        for key, job_id, name in jobs if (state / key).exists()
    ]}))
elif url.endswith("/checkpoints"):
    job_id = url.split("/")[-2]
    if os.environ.get("MOCK_CHECKPOINT_BLOCK_JOB") == job_id:
        print(json.dumps({"counts": {"completed": 0, "failed": 0}, "latest": {}}))
        raise SystemExit(0)
    print(json.dumps({
        "counts": {"completed": 1, "failed": 0},
        "latest": {"completed": {
            "id": "checkpoint-" + job_id,
            "status": "COMPLETED",
            "is_savepoint": False,
            "trigger_timestamp": 1700000000000,
            "latest_ack_timestamp": 1700000001000,
            "end_to_end_duration": 1000,
            "external_path": "file:///checkpoints/" + job_id,
        }},
    }))
elif method == "POST" and url.endswith("/savepoints"):
    job_id = url.split("/")[-2]
    if os.environ.get("MOCK_SAVEPOINT_TRIGGER_FAILURE_JOB") == job_id:
        raise SystemExit(22)
    print(json.dumps({"request-id": "trigger-" + job_id}))
elif "/savepoints/trigger-" in url:
    job_id = url.split("/")[-3]
    if os.environ.get("MOCK_SAVEPOINT_POLL_FAILURE_JOB") == job_id:
        raise SystemExit(22)
    if os.environ.get("MOCK_SAVEPOINT_IN_PROGRESS_JOB") == job_id:
        print(json.dumps({"status": {"id": "IN_PROGRESS"}}))
        raise SystemExit(0)
    if os.environ.get("MOCK_SAVEPOINT_OPERATION_FAILURE_JOB") == job_id:
        print(json.dumps({
            "status": {"id": "COMPLETED"},
            "operation": {"failure-cause": {"class": "TestFailure", "stack-trace": "failed"}},
        }))
        raise SystemExit(0)
    print(json.dumps({
        "status": {"id": "COMPLETED"},
        "operation": {
            "location": "file:///opt/flink/savepoints/savepoint-" + job_id,
        },
    }))
else:
    raise SystemExit(22)
""",
            encoding="utf-8",
        )
        docker.chmod(0o755)
        curl.chmod(0o755)
        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{bin_dir}:{env['PATH']}",
                "MOCK_STATE_DIR": str(state_dir),
                "CDC_CHECKPOINT_TIMEOUT_SECONDS": "2",
                "CDC_CHECKPOINT_POLL_SECONDS": "0",
                "CDC_SAVEPOINT_TIMEOUT_SECONDS": "2",
                "CDC_SAVEPOINT_POLL_SECONDS": "0",
            }
        )
        return env

    @staticmethod
    def mark_all_runtime_jobs(env: Dict[str, str]) -> None:
        state_dir = Path(env["MOCK_STATE_DIR"])
        for key in ("outbox", "erp", "catalog", "legacy_mall"):
            (state_dir / key).write_text("running", encoding="utf-8")

    def create_savepoint_manifest(
        self, root: Path, env: Dict[str, str]
    ) -> Path:
        self.mark_all_runtime_jobs(env)
        manifest_path = root / "savepoint-manifest.json"
        result = self.run_ctl(
            "savepoint-set", "--manifest", str(manifest_path), env=env
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return manifest_path

    @staticmethod
    def clear_runtime_jobs(env: Dict[str, str]) -> None:
        state_dir = Path(env["MOCK_STATE_DIR"])
        for key in ("outbox", "erp", "catalog", "legacy_mall"):
            (state_dir / key).unlink(missing_ok=True)

    @staticmethod
    def reseal_savepoint_manifest(manifest: dict) -> None:
        manifest.pop("manifest_sha256", None)
        canonical = json.dumps(
            manifest, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        manifest["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()

    def test_usage_registers_master_data_reconciliation_commands(self):
        result = self.run_ctl()
        self.assertEqual(result.returncode, 2)
        self.assertIn("runtime-preflight", result.stdout)
        self.assertIn("runtime-gate", result.stdout)
        self.assertIn("start-cdc-set", result.stdout)
        self.assertIn("savepoint-set", result.stdout)
        self.assertIn("restore-cdc-set", result.stdout)
        self.assertIn("empty-recovery-rehearsal", result.stdout)
        self.assertIn("reconcile-canonical-order-benefit", result.stdout)
        self.assertIn("reconcile-canonical-merchant", result.stdout)
        self.assertIn("reconcile-canonical-merchant-deposit", result.stdout)
        self.assertIn("reconcile-canonical-warehouse-network", result.stdout)
        self.assertIn("reconcile-canonical-listing-unpublish-saga", result.stdout)
        self.assertIn("reconcile-canonical-inventory-migration", result.stdout)
        self.assertIn("reconcile-legacy-trade-benefit-assessment", result.stdout)
        self.assertIn("reconcile-canonical-legacy-trade-benefit-assessment", result.stdout)
        self.assertIn("submit-legacy-mall-cdc", result.stdout)
        self.assertIn("submit-legacy-commerce-observability-cdc", result.stdout)
        self.assertIn("reconcile-legacy-commerce-observability", result.stdout)
        self.assertIn("source-evidence-policy", result.stdout)

    @unittest.skipUnless(
        TRADE_SOURCE_DOCUMENT.exists(),
        "canonical Obsidian source document is not available in this checkout",
    )
    def test_trade_source_evidence_policy_is_executable(self):
        result = self.run_ctl("source-evidence-policy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Trade history admission policy valid", result.stdout)

    def test_legacy_trade_benefit_assessment_fails_closed_on_missing_evidence(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"$source_benefit" == "$component_amount"', script)
        self.assertIn('"$unresolved_identity" == "$components"', script)
        self.assertIn('"$unresolved_funding" == "$components"', script)
        self.assertIn('"$import_allowed" == "0"', script)
        self.assertIn('"$production_enabled" == "0"', script)
        self.assertIn('"$readiness" == "BLOCKED_REQUIRES_GOVERNED_EVIDENCE"', script)
        self.assertIn('"$source_scope" == "LOCAL_YUDAO_TRADE_NOT_YSHOPPING_SOURCE"', script)

    def test_canonical_legacy_trade_benefit_reconciliation_is_row_exact_and_fail_closed(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"$backend_orders" == "$offline_orders"', script)
        self.assertIn('"$candidate_mismatches" == "0"', script)
        self.assertIn('"$component_mismatches" == "0"', script)
        self.assertIn('"$import_allowed" == "0"', script)
        self.assertIn('MATCHED_LOCAL_SNAPSHOT_BLOCKED_REQUIRES_GOVERNED_EVIDENCE', script)

    def test_canonical_legacy_trade_benefit_reconciliation_requires_uuid_run(self):
        result = self.run_ctl(
            "reconcile-canonical-legacy-trade-benefit-assessment",
            "--tenant", "1", "--run-id", "not-a-uuid",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--run-id must be a UUID for canonical legacy Trade benefit assessment", result.stderr)

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

    def test_warehouse_reconciliation_allows_multiple_governed_source_mappings(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"$active_mappings" =~ ^[1-9][0-9]*$', script)
        self.assertIn('"$exact_source_mappings" == "1"', script)

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

    def test_runtime_preflight_remains_read_only_and_non_blocking(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env = self.runtime_mock_environment(Path(temp_dir))
            env["MOCK_API_FAILURE"] = "1"
            env["MOCK_STARROCKS_HEALTH"] = "unhealthy"
            result = self.run_ctl("runtime-preflight", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("dry_run=1", result.stdout)
        self.assertIn("runtime_gate=FAIL", result.stdout)

    def test_runtime_gate_fails_closed_for_each_runtime_dependency(self):
        scenarios = {
            "missing_jobs": {},
            "non_running_job": {"mark_jobs": "1", "MOCK_JOB_STATE": "FAILED"},
            "api_failure": {"mark_jobs": "1", "MOCK_API_FAILURE": "1"},
            "starrocks_failure": {"mark_jobs": "1", "MOCK_STARROCKS_HEALTH": "unhealthy"},
            "slot_shortage": {"mark_jobs": "1", "MOCK_TOTAL_SLOTS": "3"},
        }
        for label, overrides in scenarios.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                env = self.runtime_mock_environment(Path(temp_dir))
                if overrides.pop("mark_jobs", None):
                    self.mark_all_runtime_jobs(env)
                env.update(overrides)
                result = self.run_ctl("runtime-gate", env=env)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("runtime_gate=FAIL", result.stdout)

    def test_runtime_gate_accepts_exact_running_job_set(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env = self.runtime_mock_environment(Path(temp_dir))
            self.mark_all_runtime_jobs(env)
            result = self.run_ctl("runtime-gate", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("runtime_gate=PASS", result.stdout)

    def test_empty_recovery_rehearsal_reports_plan_not_recovery_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env = self.runtime_mock_environment(Path(temp_dir))
            result = self.run_ctl("empty-recovery-rehearsal", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("EMPTY_ENVIRONMENT_REHEARSAL_DRY_RUN=PLAN_READY", result.stdout)
        self.assertNotIn("EMPTY_ENVIRONMENT_REHEARSAL_DRY_RUN=PASS", result.stdout)

    def test_start_cdc_set_submits_in_order_and_emits_checkpoint_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            env = self.runtime_mock_environment(temp)
            env_file = temp / ".env"
            env_file.write_text("test-only=1\n", encoding="utf-8")
            env["CDC_ENV_FILE"] = str(env_file)
            manifest_path = temp / "cdc-runtime-manifest.json"
            result = self.run_ctl(
                "start-cdc-set", "--manifest", str(manifest_path), env=env
            )
            submission_order = (
                Path(env["MOCK_STATE_DIR"]) / "submission-order"
            ).read_text(encoding="utf-8").splitlines()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            submission_order,
            [
                "event-cdc-cli",
                "cdc-cli",
                "catalog-cdc-cli",
                "legacy-mall-cdc-cli",
            ],
        )
        self.assertEqual(manifest["status"], "RUNNING_WITH_CHECKPOINTS")
        self.assertEqual(
            [job["name"] for job in manifest["jobs"]],
            [
                "CloudMold Domain Event Outbox to StarRocks ODS",
                "Y Shopping ERP MySQL to StarRocks ODS",
                "Y Shopping Catalog MySQL to StarRocks ODS",
                "Y Shopping Legacy Mall Alignment MySQL to StarRocks ODS",
            ],
        )
        self.assertTrue(all(job["checkpoint"]["status"] == "COMPLETED" for job in manifest["jobs"]))
        self.assertTrue(all(job["submitted"] for job in manifest["jobs"]))
        self.assertTrue(all(job["submitted_at"] for job in manifest["jobs"]))
        self.assertTrue(all(len(job["pipeline_sha256"]) == 64 for job in manifest["jobs"]))
        self.assertEqual(len(manifest["lakehousectl_sha256"]), 64)
        self.assertEqual(len(manifest["compose_sha256"]), 64)

    def test_start_cdc_set_stops_before_next_submission_without_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            env = self.runtime_mock_environment(temp)
            env_file = temp / ".env"
            env_file.write_text("test-only=1\n", encoding="utf-8")
            env.update(
                {
                    "CDC_ENV_FILE": str(env_file),
                    "CDC_CHECKPOINT_TIMEOUT_SECONDS": "1",
                    "MOCK_CHECKPOINT_BLOCK_JOB": "job-erp",
                }
            )
            result = self.run_ctl("start-cdc-set", env=env)
            submission_order = (
                Path(env["MOCK_STATE_DIR"]) / "submission-order"
            ).read_text(encoding="utf-8").splitlines()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(submission_order, ["event-cdc-cli", "cdc-cli"])
        self.assertIn("timed out waiting for the first completed checkpoint", result.stderr)

    def test_savepoint_set_triggers_four_jobs_and_emits_atomic_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            env = self.runtime_mock_environment(temp)
            manifest_path = self.create_savepoint_manifest(temp, env)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "SAVEPOINTS_COMPLETED")
        self.assertEqual(manifest["job_count"], manifest["expected_job_count"])
        self.assertEqual(manifest["job_count"], 4)
        self.assertEqual(
            [job["savepoint"]["trigger_id"] for job in manifest["jobs"]],
            [
                "trigger-job-outbox",
                "trigger-job-erp",
                "trigger-job-catalog",
                "trigger-job-legacy",
            ],
        )
        self.assertTrue(
            all(
                job["savepoint"]["location"].startswith(
                    "file:///opt/flink/savepoints/savepoint-"
                )
                for job in manifest["jobs"]
            )
        )

    def test_savepoint_set_fails_on_trigger_api_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            env = self.runtime_mock_environment(temp)
            self.mark_all_runtime_jobs(env)
            env["MOCK_SAVEPOINT_TRIGGER_FAILURE_JOB"] = "job-erp"
            manifest_path = temp / "savepoints.json"
            result = self.run_ctl(
                "savepoint-set", "--manifest", str(manifest_path), env=env
            )
            manifest_exists = manifest_path.exists()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("failed to trigger savepoint", result.stderr)
        self.assertFalse(manifest_exists)

    def test_savepoint_set_fails_on_poll_timeout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            env = self.runtime_mock_environment(temp)
            self.mark_all_runtime_jobs(env)
            env.update(
                {
                    "CDC_SAVEPOINT_TIMEOUT_SECONDS": "1",
                    "MOCK_SAVEPOINT_IN_PROGRESS_JOB": "job-outbox",
                }
            )
            manifest_path = temp / "savepoints.json"
            result = self.run_ctl(
                "savepoint-set", "--manifest", str(manifest_path), env=env
            )
            manifest_exists = manifest_path.exists()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("timed out waiting for savepoint", result.stderr)
        self.assertFalse(manifest_exists)

    def test_restore_cdc_set_defaults_to_non_mutating_dry_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            env = self.runtime_mock_environment(temp)
            manifest_path = self.create_savepoint_manifest(temp, env)
            self.clear_runtime_jobs(env)
            order_path = Path(env["MOCK_STATE_DIR"]) / "submission-order"
            order_path.unlink(missing_ok=True)
            result = self.run_ctl(
                "restore-cdc-set", "--manifest", str(manifest_path), env=env
            )
            plan = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(plan["status"], "RESTORE_PLAN_VALIDATED")
        self.assertTrue(plan["dry_run"])
        self.assertFalse(order_path.exists())

    def test_restore_cdc_set_rejects_hash_tampering(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            env = self.runtime_mock_environment(temp)
            manifest_path = self.create_savepoint_manifest(temp, env)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["compose_sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = self.run_ctl(
                "restore-cdc-set", "--manifest", str(manifest_path), env=env
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manifest checksum mismatch", result.stderr)

    def test_restore_cdc_set_rejects_compose_hash_drift_after_valid_checksum(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            env = self.runtime_mock_environment(temp)
            manifest_path = self.create_savepoint_manifest(temp, env)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["compose_sha256"] = "0" * 64
            self.reseal_savepoint_manifest(manifest)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = self.run_ctl(
                "restore-cdc-set", "--manifest", str(manifest_path), env=env
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("compose hash mismatch", result.stderr)

    def test_restore_cdc_set_rejects_pipeline_hash_drift_after_valid_checksum(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            env = self.runtime_mock_environment(temp)
            manifest_path = self.create_savepoint_manifest(temp, env)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["jobs"][0]["pipeline_sha256"] = "0" * 64
            self.reseal_savepoint_manifest(manifest)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = self.run_ctl(
                "restore-cdc-set", "--manifest", str(manifest_path), env=env
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pipeline hash mismatch", result.stderr)

    def test_restore_cdc_set_rejects_missing_manifest_location(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            env = self.runtime_mock_environment(temp)
            manifest_path = self.create_savepoint_manifest(temp, env)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["jobs"][0]["savepoint"]["location"]
            self.reseal_savepoint_manifest(manifest)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = self.run_ctl(
                "restore-cdc-set", "--manifest", str(manifest_path), env=env
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("savepoint location", result.stderr)

    def test_restore_cdc_set_rejects_unreadable_savepoint_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            env = self.runtime_mock_environment(temp)
            manifest_path = self.create_savepoint_manifest(temp, env)
            env["MOCK_SAVEPOINT_PATH_MISSING"] = "1"
            result = self.run_ctl(
                "restore-cdc-set", "--manifest", str(manifest_path), env=env
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("savepoint path is not readable", result.stderr)

    def test_restore_cdc_set_executes_in_order_and_waits_for_checkpoints(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            env = self.runtime_mock_environment(temp)
            env_file = temp / ".env"
            env_file.write_text("test-only=1\n", encoding="utf-8")
            env["CDC_ENV_FILE"] = str(env_file)
            manifest_path = self.create_savepoint_manifest(temp, env)
            self.clear_runtime_jobs(env)
            order_path = Path(env["MOCK_STATE_DIR"]) / "submission-order"
            order_path.unlink(missing_ok=True)
            result = self.run_ctl(
                "restore-cdc-set",
                "--manifest",
                str(manifest_path),
                "--execute",
                env=env,
            )
            restored = json.loads(result.stdout)
            submission_order = order_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(restored["status"], "RESTORED_WITH_CHECKPOINTS")
        self.assertFalse(restored["dry_run"])
        self.assertEqual(
            submission_order,
            [
                "event-cdc-cli",
                "cdc-cli",
                "catalog-cdc-cli",
                "legacy-mall-cdc-cli",
            ],
        )
        self.assertTrue(
            all(job["checkpoint"]["status"] == "COMPLETED" for job in restored["jobs"])
        )

    def test_restore_cdc_set_stops_after_restore_submission_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            env = self.runtime_mock_environment(temp)
            env_file = temp / ".env"
            env_file.write_text("test-only=1\n", encoding="utf-8")
            env["CDC_ENV_FILE"] = str(env_file)
            manifest_path = self.create_savepoint_manifest(temp, env)
            self.clear_runtime_jobs(env)
            order_path = Path(env["MOCK_STATE_DIR"]) / "submission-order"
            order_path.unlink(missing_ok=True)
            env["MOCK_RESTORE_FAILURE_SERVICE"] = "catalog-cdc-cli"
            result = self.run_ctl(
                "restore-cdc-set",
                "--manifest",
                str(manifest_path),
                "--execute",
                env=env,
            )
            submission_order = order_path.read_text(encoding="utf-8").splitlines()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(
            submission_order,
            ["event-cdc-cli", "cdc-cli", "catalog-cdc-cli"],
        )


if __name__ == "__main__":
    unittest.main()
