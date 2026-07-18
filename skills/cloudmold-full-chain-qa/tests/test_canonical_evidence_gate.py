import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/canonical_evidence_gate.py"
SPEC = importlib.util.spec_from_file_location("canonical_evidence_gate", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CanonicalEvidenceGateTest(unittest.TestCase):
    def test_validates_product_centric_chain(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_id = "e2e-test"
            child_ids = {
                "catalog": "cat",
                "projection": "proj",
                "master": "master",
                "aftersales": "after",
            }
            ledgers = {
                root / "yshopping-aftersales" / run_id / "ledger.json": {
                    "run_id": run_id, "status": "SUCCEEDED", "child_run_ids": child_ids
                },
                root / "catalog" / "cat" / "ledger.json": {
                    "final": {"catalog_status": "ACTIVE", "sku_count": 1}
                },
                root / "projection" / "proj" / "ledger.json": {
                    "final": {"projection_count": 3}
                },
                root / "merchant-warehouse" / "master" / "ledger.json": {
                    "status": "SUCCEEDED",
                    "final": {"merchant_status": "ACTIVE", "shop_status": "ACTIVE", "warehouse_status": "ACTIVE"},
                },
                root / "aftersales" / "after" / "ledger.json": {
                    "status": "SUCCEEDED",
                    "final": {
                        "all_replay_duplicate": True,
                        "aftersales": {
                            "caseStatus": "COMPLETED",
                            "refundStatus": "SUCCEEDED",
                            "resolutionSagaStatus": "COMPLETED",
                        },
                    },
                },
            }
            for path, payload in ledgers.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual("SUCCEEDED", MODULE.validate(root, run_id)["status"])

    def test_rejects_failed_parent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "yshopping-aftersales" / "failed" / "ledger.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"run_id": "failed", "status": "FAILED"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not SUCCEEDED"):
                MODULE.validate(root, "failed")


if __name__ == "__main__":
    unittest.main()
