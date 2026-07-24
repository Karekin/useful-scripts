import importlib.util
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


if __name__ == "__main__":
    unittest.main()
