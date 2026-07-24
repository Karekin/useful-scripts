import importlib.util
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
