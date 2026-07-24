import importlib.util
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/hsf_mcp_operator.py"
SPEC = importlib.util.spec_from_file_location("hsf_mcp_operator", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class InternalTestVisibilityTest(unittest.TestCase):
    def test_acceptance_threads_are_marked_internal(self):
        self.assertEqual(
            MODULE.internal_test_thread_metadata("cloudmold-r3-full-chain-e2e"),
            {
                "purpose": "cloudmold-r3-full-chain-e2e",
                "visibility": "internal_test",
            },
        )

    def test_machine_control_prompt_is_hidden_from_business_ui(self):
        message = MODULE.hidden_control_message("exact machine prompt")
        self.assertEqual(message["role"], "user")
        self.assertEqual(message["content"], "exact machine prompt")
        self.assertIs(message["additional_kwargs"]["hide_from_ui"], True)

    def test_acceptance_run_repeats_internal_metadata(self):
        body = MODULE.with_internal_test_metadata(
            {"assistant_id": "lead_agent"},
            "cloudmold-r3-full-chain-e2e",
        )

        self.assertEqual(body["assistant_id"], "lead_agent")
        self.assertEqual(
            body["metadata"],
            {
                "purpose": "cloudmold-r3-full-chain-e2e",
                "visibility": "internal_test",
            },
        )


    def test_approval_reference_requires_private_file_permissions(self):
        reference = "cma1:approval-0725:1785000000:" + "a" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "approval-ref"
            path.write_text(reference, encoding="utf-8")
            path.chmod(0o600)
            self.assertEqual(MODULE.load_approval_ref(path), reference)
            path.chmod(0o644)
            with self.assertRaisesRegex(MODULE.GateError, "group/world"):
                MODULE.load_approval_ref(path)

    def test_approval_reference_rejects_expired_timestamp(self):
        reference = "cma1:approval-0725:1785000000:" + "a" * 64
        fresh_now = datetime.fromtimestamp(
            1785000000 + MODULE.R3_APPROVAL_CLOCK_SKEW_SECONDS - 1,
            tz=timezone.utc,
        )
        stale_now = datetime.fromtimestamp(
            1785000000 + MODULE.R3_APPROVAL_CLOCK_SKEW_SECONDS + 1,
            tz=timezone.utc,
        )
        self.assertTrue(MODULE.approval_ref_is_fresh(reference, now=fresh_now))
        self.assertFalse(MODULE.approval_ref_is_fresh(reference, now=stale_now))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "approval-ref"
            path.write_text(reference, encoding="utf-8")
            path.chmod(0o600)
            with patch.object(MODULE, "approval_ref_is_fresh", return_value=False):
                with self.assertRaisesRegex(MODULE.GateError, "expired"):
                    MODULE.load_approval_ref(path)

    def test_r3_terminal_proof_binds_identity_input_and_all_hashes(self):
        task_input = {"z": 2, "a": {"value": "测试"}}
        input_sha256 = MODULE.canonical_object_sha256(task_input)
        task = {
            "skillId": MODULE.R3_SKILL_ID,
            "skillVersion": MODULE.R3_SKILL_VERSION,
            "riskLevel": "R3",
            "inputSha256": input_sha256,
            "definitionSha256": "a" * 64,
            "definitionClosureSha256": "b" * 64,
            "terminalResultSha256": "c" * 64,
        }
        self.assertEqual(
            MODULE.require_r3_terminal_proof(task, task_input),
            {
                "definitionSha256": "a" * 64,
                "definitionClosureSha256": "b" * 64,
                "terminalResultSha256": "c" * 64,
            },
        )
        task["inputSha256"] = "0" * 64
        with self.assertRaisesRegex(MODULE.GateError, "inputSha256"):
            MODULE.require_r3_terminal_proof(task, task_input)

    def test_r3_acceptance_agent_exposes_only_fixed_submit_and_query(self):
        desired = MODULE.r3_acceptance_agent_request()
        self.assertEqual(desired["tool_groups"], [])
        self.assertEqual(
            desired["skills"],
            [MODULE.DEERFLOW_R3_ACCEPTANCE_POLICY_SKILL],
        )
        policy_path = (
            SCRIPT.parents[2]
            / MODULE.DEERFLOW_R3_ACCEPTANCE_POLICY_SKILL
            / "SKILL.md"
        )
        policy = policy_path.read_text(encoding="utf-8")
        self.assertIn(MODULE.DEERFLOW_R3_SUBMIT_TOOL, policy)
        self.assertIn(MODULE.DEERFLOW_TASK_GET_TOOL, policy)
        self.assertNotIn("ask_clarification", policy)

    def test_r3_acceptance_agent_is_created_idempotently(self):
        desired = MODULE.r3_acceptance_agent_request()
        with patch.object(
            MODULE,
            "request_json",
            side_effect=[
                (404, {}, None),
                (201, {}, desired),
            ],
        ) as request:
            result = MODULE.ensure_deerflow_r3_acceptance_agent(
                "http://deerflow.test",
                {"Cookie": "test", "X-CSRF-Token": "test"},
            )
        self.assertEqual(result, MODULE.DEERFLOW_R3_ACCEPTANCE_AGENT)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args_list[1].args[:2], ("POST", "http://deerflow.test/api/agents"))

    def test_r3_acceptance_agent_drift_is_repaired(self):
        desired = MODULE.r3_acceptance_agent_request()
        drifted = {**desired, "skills": []}
        with patch.object(
            MODULE,
            "request_json",
            side_effect=[
                (200, {}, drifted),
                (200, {}, desired),
            ],
        ) as request:
            result = MODULE.ensure_deerflow_r3_acceptance_agent(
                "http://deerflow.test",
                {"Cookie": "test", "X-CSRF-Token": "test"},
            )
        self.assertEqual(result, MODULE.DEERFLOW_R3_ACCEPTANCE_AGENT)
        self.assertEqual(request.call_args_list[1].args[:2], (
            "PUT",
            "http://deerflow.test/api/agents/cloudmold-r3-acceptance-agent",
        ))

    def test_r3_waits_for_persisted_submit_after_gateway_504(self):
        partial_state = {
            "messages": [
                {
                    "type": "ai",
                    "content": "loading",
                    "tool_calls": [
                        {
                            "name": "tool_search",
                            "args": {"query": "select:cloudmold-hsf_cloudmold_skill_task_submit_commerce_full_chain_r3"},
                            "id": "call_partial",
                            "type": "tool_call",
                        }
                    ],
                },
                {"type": "tool", "name": "tool_search", "content": "[]"},
                {
                    "type": "tool",
                    "name": MODULE.DEERFLOW_R3_SUBMIT_TOOL,
                    "content": '{"taskId":"task-123"}',
                },
            ]
        }
        ready_state = {
            "messages": partial_state["messages"]
            + [
                {
                    "type": "ai",
                    "content": "query",
                    "tool_calls": [
                        {
                            "name": MODULE.DEERFLOW_TASK_GET_TOOL,
                            "args": {
                                "tenantId": 1,
                                "operatorId": 1,
                                "operatorType": 1,
                                "controlRunId": "run",
                                "taskId": "task-123",
                            },
                            "id": "call_get",
                            "type": "tool_call",
                        }
                    ],
                },
                {
                    "type": "tool",
                    "name": MODULE.DEERFLOW_TASK_GET_TOOL,
                    "content": '{"taskId":"task-123","status":"SUCCEEDED"}',
                },
            ]
        }
        with patch.object(
            MODULE,
            "request_json",
            side_effect=[(200, {}, {"values": ready_state})],
        ) as request, patch.object(MODULE.time, "monotonic", side_effect=[0, 0]), patch.object(
            MODULE.time, "sleep", return_value=None
        ):
            state = MODULE.wait_for_deerflow_r3_thread_state(
                "http://deerflow.test",
                {"Cookie": "test", "X-CSRF-Token": "test"},
                "thread-1",
                initial_state=partial_state,
                timeout_seconds=10,
            )

        self.assertIs(state, ready_state)
        self.assertEqual(request.call_count, 1)

    def test_r3_thread_state_polling_times_out_without_submit(self):
        partial_state = {
            "messages": [
                {
                    "type": "ai",
                    "content": "loading",
                    "tool_calls": [
                        {
                            "name": "tool_search",
                            "args": {"query": "select:cloudmold-hsf_cloudmold_skill_task_submit_commerce_full_chain_r3"},
                            "id": "call_partial",
                            "type": "tool_call",
                        }
                    ],
                },
                {"type": "tool", "name": "tool_search", "content": "[]"},
            ]
        }
        with patch.object(
            MODULE,
            "request_json",
            side_effect=[
                (200, {}, {"values": partial_state}),
                (200, {}, {"values": partial_state}),
            ],
        ) as request, patch.object(MODULE.time, "monotonic", side_effect=[0, 0, 0.5, 1.1]), patch.object(
            MODULE.time, "sleep", return_value=None
        ):
            with self.assertRaisesRegex(MODULE.GateError, "did not persist the fixed submit result"):
                MODULE.wait_for_deerflow_r3_thread_state(
                    "http://deerflow.test",
                    {"Cookie": "test", "X-CSRF-Token": "test"},
                    "thread-1",
                    initial_state=partial_state,
                    timeout_seconds=1,
                )

        self.assertGreaterEqual(request.call_count, 2)


if __name__ == "__main__":
    unittest.main()
