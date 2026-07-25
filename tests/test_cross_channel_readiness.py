from pathlib import Path
import importlib.util
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cross_channel_readiness.py"
SPEC = importlib.util.spec_from_file_location("cross_channel_readiness", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CrossChannelReadinessTest(unittest.TestCase):

    def test_registry_is_complete_and_evidence_backed(self):
        result = MODULE.validate_registry()

        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["stages"], 22)
        self.assertEqual(result["phase_gates"], 5)
        self.assertEqual(
            result["status_counts"],
            {"connected": 0, "partial": 21, "missing": 1},
        )
        self.assertEqual(result["by_side"]["operator"]["stages"], 11)
        self.assertEqual(result["by_side"]["consumer"]["stages"], 11)
        self.assertGreater(result["consumer_critical_integration_percent"], 0)
        self.assertLess(result["consumer_critical_integration_percent"], 10)


if __name__ == "__main__":
    unittest.main()
