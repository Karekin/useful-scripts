import copy
import importlib.machinery
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "reportctl"


def load_module():
    loader = importlib.machinery.SourceFileLoader("reportctl_test_target", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


reportctl = load_module()


class ReportContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = reportctl.load_json(reportctl.METRIC_CATALOG)
        cls.metrics = reportctl.metric_map(cls.catalog)
        cls.report = reportctl.find_report("supply-chain-health")

    def test_checked_in_analytics_contracts_are_valid(self):
        metric_count, report_count = reportctl.validate_all()
        self.assertGreaterEqual(metric_count, 20)
        self.assertEqual(4, report_count)

    def test_unknown_metric_is_rejected(self):
        report = copy.deepcopy(self.report)
        report["metrics"].append("inventory.fabricated_metric")
        errors = reportctl.validate_report(report, self.metrics, self.catalog["evidence_scope"])
        self.assertTrue(any("unknown metrics" in error for error in errors))

    def test_required_tenant_filter_is_enforced(self):
        report = copy.deepcopy(self.report)
        report["filters"] = [item for item in report["filters"] if item["field"] != "tenant_id"]
        errors = reportctl.validate_report(report, self.metrics, self.catalog["evidence_scope"])
        self.assertTrue(any("tenant_id" in error for error in errors))

    def test_local_evidence_cannot_be_published_as_production(self):
        report = copy.deepcopy(self.report)
        report["publication_scope"] = "production"
        errors = reportctl.validate_report(report, self.metrics, self.catalog["evidence_scope"])
        self.assertTrue(any("production metric evidence" in error for error in errors))

    def test_metric_expression_cannot_embed_a_query(self):
        catalog = copy.deepcopy(self.catalog)
        catalog["metrics"][0]["expression"] = "SELECT COUNT(*) FROM secret"
        with self.assertRaises(reportctl.ReportError):
            reportctl.metric_map(catalog)

    def test_governed_metric_requires_freshness_but_candidate_may_expose_gap(self):
        catalog = copy.deepcopy(self.catalog)
        catalog["metrics"][0]["freshness_field"] = None
        catalog["metrics"][0]["freshness_slo_minutes"] = None
        with self.assertRaises(reportctl.ReportError):
            reportctl.metric_map(catalog)
        catalog["metrics"][0]["status"] = "candidate"
        self.assertIn(catalog["metrics"][0]["id"], reportctl.metric_map(catalog))

    def test_wren_models_are_allowlisted_and_privacy_minimized(self):
        self.assertEqual([], reportctl.validate_wren())

    def test_metric_sql_is_tenant_scoped_and_read_only(self):
        sql = reportctl.metric_sql("inventory.available_quantity", 1)
        self.assertIn("FROM yshopping_ads.ads_canonical_inventory_health", sql)
        self.assertIn("WHERE tenant_id = 1", sql)
        self.assertNotIn("SELECT *", sql)
        with self.assertRaises(reportctl.ReportError):
            reportctl.metric_sql("inventory.available_quantity", 0)

    def test_lakehousectl_exposes_report_validation_and_health(self):
        lakehousectl = (ROOT / "scripts" / "lakehousectl").read_text(encoding="utf-8")
        self.assertIn("report-contract-test)", lakehousectl)
        self.assertIn("report-status)", lakehousectl)
        self.assertIn('"$ROOT_DIR/scripts/reportctl" validate', lakehousectl)


if __name__ == "__main__":
    unittest.main()
