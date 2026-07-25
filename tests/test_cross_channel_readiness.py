from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cross_channel_readiness.py"
SPEC = importlib.util.spec_from_file_location("cross_channel_readiness", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


def build_v2_registry():
    audited_at = "2026-07-25T00:00:00+08:00"
    source_file = "yudao-mall-uniapp/sheep/api/cloudmold/address.js"
    receipt_path = "useful-scripts/tests/test_cross_channel_readiness.py"
    return {
        "schema_version": 2,
        "audit_id": "test-cross-channel-v2",
        "audited_at": audited_at,
        "evidence_scope": "LOCAL_REPOSITORY_AND_LOCAL_TEST",
        "scoring": {
            "dimensions": list(MODULE.DIMENSIONS),
        },
        "phase_gates": [{"id": "gate-1"}],
        "stages": [
            {
                "id": "consumer.checkout_order",
                "name": "结算与下单",
                "side": "consumer",
                "authority": "cloudmold-module-order facade",
                "gap": "none",
                "source_files": [source_file],
                "evidence_by_dimension": {
                    "surface": {
                        "kind": "SOURCE_FILE",
                        "scope": "LOCAL_REPOSITORY",
                        "stable": True,
                        "source_files": [source_file],
                        "denominator": {
                            "unit": "declared_surface_files",
                            "expected": 1,
                            "verified": 1,
                        },
                        "test_receipts": [],
                    },
                    "live_api": {
                        "kind": "INTEGRATION_TEST",
                        "scope": "LOCAL_TEST",
                        "stable": False,
                        "captured_at": audited_at,
                        "max_age_days": 30,
                        "source_files": [source_file],
                        "denominator": {
                            "unit": "governed_api_stage",
                            "expected": 1,
                            "verified": 1,
                        },
                        "test_receipts": [
                            {
                                "suite": "unittest",
                                "path": receipt_path,
                                "case": "CrossChannelReadinessTest.test_v2_registry_derives_status_from_evidence",
                                "captured_at": audited_at,
                                "max_age_days": 30,
                            }
                        ],
                    },
                    "canonical_sor": {
                        "kind": "SOURCE_FILE",
                        "scope": "LOCAL_REPOSITORY",
                        "stable": True,
                        "source_files": [source_file],
                        "denominator": {
                            "unit": "canonical_anchor",
                            "expected": 1,
                            "verified": 1,
                        },
                        "test_receipts": [],
                    },
                    "event": {
                        "kind": "SCENARIO_RECEIPT",
                        "scope": "LOCAL_TEST",
                        "stable": False,
                        "captured_at": audited_at,
                        "max_age_days": 30,
                        "source_files": [source_file],
                        "denominator": {
                            "unit": "event_lineage_contract",
                            "expected": 1,
                            "verified": 1,
                        },
                        "test_receipts": [
                            {
                                "suite": "unittest",
                                "path": receipt_path,
                                "case": "CrossChannelReadinessTest.test_v2_registry_derives_status_from_evidence",
                                "captured_at": audited_at,
                                "max_age_days": 30,
                            }
                        ],
                        "lineage": {
                            "run_id": "cross-channel-0725",
                            "tenant_id": "1",
                            "session_id": "00000000-0000-4000-8000-000000000001",
                        },
                    },
                    "agent": {
                        "kind": "SCENARIO_RECEIPT",
                        "scope": "LOCAL_TEST",
                        "stable": False,
                        "captured_at": audited_at,
                        "max_age_days": 30,
                        "source_files": [source_file],
                        "denominator": {
                            "unit": "agent_step_contract",
                            "expected": 1,
                            "verified": 1,
                        },
                        "test_receipts": [
                            {
                                "suite": "unittest",
                                "path": receipt_path,
                                "case": "CrossChannelReadinessTest.test_v2_registry_derives_status_from_evidence",
                                "captured_at": audited_at,
                                "max_age_days": 30,
                            }
                        ],
                        "lineage": {
                            "run_id": "cross-channel-0725",
                            "tenant_id": "1",
                            "principal_id": "principal-1",
                        },
                    },
                    "cross_channel": {
                        "kind": "RUNTIME_LINKAGE",
                        "scope": "LOCAL_RUNTIME_VERIFIED",
                        "stable": False,
                        "captured_at": audited_at,
                        "max_age_days": 30,
                        "source_files": [source_file],
                        "denominator": {
                            "unit": "exact_cross_channel_linkage",
                            "expected": 1,
                            "verified": 1,
                        },
                        "test_receipts": [
                            {
                                "suite": "unittest",
                                "path": receipt_path,
                                "case": "CrossChannelReadinessTest.test_v2_registry_derives_status_from_evidence",
                                "captured_at": audited_at,
                                "max_age_days": 30,
                            }
                        ],
                        "lineage": {
                            "run_id": "cross-channel-0725",
                            "tenant_id": "1",
                            "order_id": "order-1",
                        },
                    },
                },
            }
        ],
    }


class CrossChannelReadinessTest(unittest.TestCase):
    def test_registry_is_complete_and_evidence_backed(self):
        result = MODULE.validate_registry(now=NOW)
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["stages"], 22)
        self.assertEqual(result["phase_gates"], 5)
        self.assertEqual(
            result["status_counts"],
            {"connected": 22, "partial": 0, "missing": 0},
        )
        self.assertEqual(result["by_side"]["operator"]["stages"], 11)
        self.assertEqual(result["by_side"]["consumer"]["stages"], 11)
        self.assertEqual(result["consumer_critical_integration_percent"], 100.0)

    def test_v2_registry_derives_status_from_evidence(self):
        registry = build_v2_registry()
        with tempfile.TemporaryDirectory() as directory:
            registry_path = Path(directory) / "registry.json"
            registry_path.write_text(
                json.dumps(registry, ensure_ascii=False),
                encoding="utf-8",
            )
            result = MODULE.validate_registry(
                registry_path=registry_path,
                now=NOW,
            )
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["status_counts"], {"connected": 1, "partial": 0, "missing": 0})
        self.assertEqual(result["dimension_counts"]["cross_channel"], 1)

    def test_v2_mutations_fail_closed(self):
        variants = []
        missing_evidence = build_v2_registry()
        del missing_evidence["stages"][0]["evidence_by_dimension"]["cross_channel"]
        variants.append((missing_evidence, None))

        denominator = build_v2_registry()
        denominator["stages"][0]["evidence_by_dimension"]["live_api"]["denominator"]["verified"] = 0
        variants.append((denominator, "denominator verified"))

        stale = build_v2_registry()
        stale["stages"][0]["evidence_by_dimension"]["live_api"]["captured_at"] = "2026-05-01T00:00:00Z"
        stale["stages"][0]["evidence_by_dimension"]["live_api"]["test_receipts"][0]["captured_at"] = "2026-05-01T00:00:00Z"
        variants.append((stale, "older than 30 days"))

        bad_commit = build_v2_registry()
        bad_commit["stages"][0]["evidence_by_dimension"]["canonical_sor"]["stable"] = False
        bad_commit["stages"][0]["evidence_by_dimension"]["canonical_sor"]["captured_at"] = "2026-07-25T00:00:00+08:00"
        bad_commit["stages"][0]["evidence_by_dimension"]["canonical_sor"]["max_age_days"] = 30
        variants.append((bad_commit, "requires commit"))

        wrong_tenant = build_v2_registry()
        wrong_tenant["stages"][0]["evidence_by_dimension"]["cross_channel"]["lineage"] = {
            "run_id": "cross-channel-0725",
            "session_id": "00000000-0000-4000-8000-000000000001",
        }
        variants.append((wrong_tenant, "lineage.tenant_id"))

        for registry, expected_error in variants:
            with self.subTest(expected_error=expected_error):
                with tempfile.TemporaryDirectory() as directory:
                    registry_path = Path(directory) / "registry.json"
                    registry_path.write_text(
                        json.dumps(registry, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    if expected_error is None:
                        result = MODULE.validate_registry(registry_path=registry_path, now=NOW)
                        self.assertEqual(result["status_counts"]["partial"], 1)
                    else:
                        with self.assertRaisesRegex(MODULE.ReadinessError, expected_error):
                            MODULE.validate_registry(registry_path=registry_path, now=NOW)


if __name__ == "__main__":
    unittest.main()
