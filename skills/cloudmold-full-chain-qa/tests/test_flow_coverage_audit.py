import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/flow_coverage_audit.py"
SPEC = importlib.util.spec_from_file_location("flow_coverage_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FlowCoverageAuditTest(unittest.TestCase):
    def test_normalizes_query_and_template_parameters(self):
        self.assertEqual("/erp/order/get", MODULE.normalize_endpoint("/erp/order/get?id=${id}"))

    def test_extracts_typed_multiline_request(self):
        with tempfile.TemporaryDirectory() as temp:
            ui_root = Path(temp)
            api_root = ui_root / "apps/web-antd/src/api/erp/order"
            api_root.mkdir(parents=True)
            (api_root / "index.ts").write_text(
                "return requestClient.get<PageResult<Order>>(\n  '/erp/order/page',\n  { params },\n);\n",
                encoding="utf-8",
            )
            rows = MODULE.extract_api_endpoints(ui_root / "apps/web-antd/src/api", ui_root)
            self.assertEqual([("GET", "/erp/order/page", "apps/web-antd/src/api/erp/order/index.ts")], rows)

    def test_classification_never_equates_zero_execution_with_dead_code(self):
        self.assertEqual(
            "TEST_GAP",
            MODULE.classify(referenced=2, skill_referenced=False, runtime_called=False),
        )
        self.assertEqual(
            "TEST_GAP",
            MODULE.classify(referenced=0, skill_referenced=True, runtime_called=False),
        )
        self.assertEqual(
            "REDUNDANCY_CANDIDATE",
            MODULE.classify(referenced=0, skill_referenced=False, runtime_called=False),
        )

    def test_parses_erp_catalog_routes(self):
        with tempfile.TemporaryDirectory() as temp:
            catalog = Path(temp) / "catalog.md"
            catalog.write_text(
                "| POST | `/erp/purchase-order/create` | `createPurchaseOrder` |\n",
                encoding="utf-8",
            )
            self.assertEqual(
                {("POST", "/erp/purchase-order/create")},
                MODULE.collect_erp_catalog(catalog),
            )

    def test_manual_override_prevents_false_dead_code_label(self):
        override = {
            "path_prefix": "/mes/pro/task-issue/",
            "classification": "ADAPTER_OR_MIGRATION_PENDING",
        }
        self.assertEqual(
            override,
            MODULE.find_override("/mes/pro/task-issue/page", [override]),
        )


if __name__ == "__main__":
    unittest.main()
