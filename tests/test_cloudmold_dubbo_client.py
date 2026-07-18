import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "cloudmold_dubbo_client.py"
SPEC = importlib.util.spec_from_file_location("cloudmold_dubbo_client", MODULE_PATH)
CLIENT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CLIENT)


class DubboClientTest(unittest.TestCase):

    def test_registry_exposes_only_dubbo_capabilities(self):
        client = CLIENT.DubboClient(tenant=1, timeout=5)
        paths = client.available_paths()
        self.assertEqual(
            "dubbo", paths["/admin-api/cloudmold/order/command"]["post"]["x-cloudmold-transport"])
        self.assertEqual(
            "capability.cloudmold.order.order-command.execute.v1",
            paths["/admin-api/cloudmold/order/command"]["post"]["x-cloudmold-capability-id"])

    def test_query_binding_requires_declared_parameter(self):
        with self.assertRaisesRegex(CLIENT.DubboTransportError, "query parameter id"):
            CLIENT.DubboClient(tenant=1, timeout=5).request(
                "GET", "/admin-api/erp/warehouse/get")

    def test_request_invokes_executor_and_writes_zero_http_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace.jsonl"
            environment = {
                "CLOUDMOLD_HSF_TRACE_FILE": str(trace),
                "CLOUDMOLD_HSF_RUN_ID": "hsf-test-run-001",
                "CLOUDMOLD_SKILL_ID": "skill.test.hsf.v1",
            }
            completed = subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout='noise\n{"status":"SUCCEEDED","result":{"warehouseId":3}}\n')
            with mock.patch.dict(os.environ, environment, clear=False), \
                    mock.patch.object(CLIENT.DubboClient, "_require_provider_ready"), \
                    mock.patch.object(CLIENT.subprocess, "run", return_value=completed) as run:
                result = CLIENT.DubboClient(tenant=1, timeout=5).request(
                    "GET", "/admin-api/erp/warehouse/get?id=3")

            self.assertEqual({"warehouseId": 3, "id": 3}, result)
            command = run.call_args.args[0]
            self.assertIn("--no-deps", command)
            self.assertIn("--run-id=hsf-test-run-001", command)
            self.assertIn(
                "--capability-id=capability.cloudmold.integration.yudao-legacy-master-data-query.get-erp-warehouse.v1",
                command)
            record = json.loads(trace.read_text(encoding="utf-8"))
            self.assertEqual("dubbo", record["transport"])
            self.assertFalse(record["http_used"])
            self.assertEqual("SUCCEEDED", record["status"])
            self.assertEqual("hsf-test-run-001", record["run_id"])

    def test_failed_executor_result_is_rejected_and_traced(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace.jsonl"
            completed = subprocess.CompletedProcess(
                args=[], returncode=2,
                stdout='{"status":"FAILED","message":"denied"}\n')
            with mock.patch.dict(os.environ, {"CLOUDMOLD_HSF_TRACE_FILE": str(trace)}, clear=False), \
                    mock.patch.object(CLIENT.DubboClient, "_require_provider_ready"), \
                    mock.patch.object(CLIENT.subprocess, "run", return_value=completed):
                with self.assertRaisesRegex(CLIENT.DubboTransportError, "denied"):
                    CLIENT.DubboClient(tenant=1, timeout=5).request(
                        "GET", "/admin-api/erp/warehouse/get?id=3")
            record = json.loads(trace.read_text(encoding="utf-8"))
            self.assertEqual("FAILED", record["status"])
            self.assertEqual(2, record["executor_exit_code"])

    def test_provider_preflight_rejects_unhealthy_base_stack(self):
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="starting\n")
        with mock.patch.object(CLIENT.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(CLIENT.DubboTransportError, "is not healthy"):
                CLIENT.DubboClient._require_provider_ready()


if __name__ == "__main__":
    unittest.main()
