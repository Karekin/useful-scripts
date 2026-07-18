import importlib.util
import argparse
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "yudao_dubbo_flow.py"
SPEC = importlib.util.spec_from_file_location("yudao_dubbo_flow", MODULE_PATH)
FLOW = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(FLOW)


def authority_input() -> dict:
    return {
        "authority": {
            "reference": {"merchantId": "merchant-uuid", "shopId": "shop-uuid"},
            "operator": {
                "merchantId": "merchant-uuid",
                "shopId": "shop-uuid",
                "principalId": "principal-uuid",
                "roleCode": "OWNER",
            },
        }
    }


class ValidateAuthorityTest(unittest.TestCase):

    def test_accepts_consistent_owner_authority(self):
        FLOW.validate_authority(authority_input())

    def test_rejects_virtual_identifier(self):
        inputs = authority_input()
        inputs["authority"]["reference"]["merchantId"] = "internal-company"
        with self.assertRaisesRegex(RuntimeError, "canonical non-virtual"):
            FLOW.validate_authority(inputs)

    def test_resolves_list_element_from_prior_rpc_result(self):
        context = {"steps": {"lines": {"result": [{"purchaseOrderLineId": 31}]}}}

        self.assertEqual(31, FLOW.resolve("$steps.lines.result.0.purchaseOrderLineId", context))

    def test_assertion_resolves_expected_value_from_input(self):
        step = {"id": "read", "expect": {"result.assetId": "$input.assetId"}}

        FLOW.assert_expected(step, {"result": {"assetId": "asset-1"}}, {"input": {"assetId": "asset-1"}})


class StepTimeoutTest(unittest.TestCase):

    def test_requires_healthy_provider_before_workflow(self):
        unhealthy = subprocess.CompletedProcess(["docker"], 0, stdout="starting\n")
        with patch.object(FLOW.subprocess, "run", return_value=unhealthy):
            with self.assertRaisesRegex(RuntimeError, "is not healthy"):
                FLOW.require_provider_ready()

    def test_one_shot_executor_never_recreates_provider_dependencies(self):
        args = argparse.Namespace(
            tenant_id=1,
            operator_id=1,
            operator_type=1,
            skill_id="skill.test",
            run_id="run-1",
            write_approved=False,
            step_timeout_seconds=3,
        )
        step = {"id": "query", "capabilityId": "capability.test.query.v1", "write": False}
        output = '{"status":"SUCCEEDED","result":{}}\n'
        completed = subprocess.CompletedProcess(["docker"], 0, stdout=output)
        with patch.object(FLOW.subprocess, "run", return_value=completed) as run:
            FLOW.execute_step(step, [], args)
        command = run.call_args.args[0]
        self.assertIn("--no-deps", command)
        self.assertLess(command.index("--no-deps"), command.index("cloudmold-agent-executor"))

    def test_reports_bounded_dubbo_executor_timeout(self):
        args = argparse.Namespace(
            tenant_id=1,
            operator_id=1,
            operator_type=1,
            skill_id="skill.test",
            run_id="run-1",
            write_approved=True,
            step_timeout_seconds=3,
        )
        step = {"id": "create", "capabilityId": "capability.test.create.v1", "write": True}
        with patch.object(FLOW.subprocess, "run", side_effect=subprocess.TimeoutExpired("docker", 3)):
            with self.assertRaisesRegex(RuntimeError, "timed out after 3s"):
                FLOW.execute_step(step, [], args)

    def test_rejects_operator_from_another_shop(self):
        inputs = authority_input()
        inputs["authority"]["operator"]["shopId"] = "another-shop"
        with self.assertRaisesRegex(RuntimeError, "must belong"):
            FLOW.validate_authority(inputs)

    def test_rejects_non_owner_role(self):
        inputs = authority_input()
        inputs["authority"]["operator"]["roleCode"] = "OPERATOR"
        with self.assertRaisesRegex(RuntimeError, "must be OWNER"):
            FLOW.validate_authority(inputs)


if __name__ == "__main__":
    unittest.main()
