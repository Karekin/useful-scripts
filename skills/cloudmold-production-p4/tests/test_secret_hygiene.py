from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "secret_hygiene.py"
SPEC = importlib.util.spec_from_file_location("secret_hygiene", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SecretHygieneTest(unittest.TestCase):
    def _repo(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q", str(root)], check=True)

    def test_reports_key_location_without_value(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._repo(root)
            config = root / "application.yaml"
            config.write_text("provider:\n  api-key: highly-sensitive-value\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "application.yaml"], check=True)
            result = MODULE.scan(root)
            self.assertEqual("BLOCKED", result["status"])
            self.assertEqual("api-key", result["findings"][0]["key"])
            self.assertNotIn("highly-sensitive-value", str(result))
            self.assertTrue(result["values_redacted"])

    def test_allows_external_reference_and_rejects_tracked_dotenv(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._repo(root)
            (root / "application.yaml").write_text(
                "provider:\n  api-key: ${PROVIDER_API_KEY:}\n", encoding="utf-8"
            )
            (root / ".env").write_text("PROVIDER_API_KEY=CHANGE_ME\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "-f", "application.yaml", ".env"], check=True)
            result = MODULE.scan(root)
            self.assertEqual(1, result["finding_count"])
            self.assertEqual("TRACKED_DOTENV", result["findings"][0]["key"])


if __name__ == "__main__":
    unittest.main()
