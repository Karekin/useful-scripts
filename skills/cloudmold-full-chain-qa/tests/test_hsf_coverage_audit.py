import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/hsf_coverage_audit.py"
SPEC = importlib.util.spec_from_file_location("hsf_coverage_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class HsfCoverageAuditTest(unittest.TestCase):
    def test_parses_catalog_after_dubbo_logs(self):
        output = "log line\n" + json.dumps([{
            "capabilityId": "capability.cloudmold.catalog.catalog-query.get.v1",
            "interfaceName": "example.CatalogApi",
        }])
        self.assertEqual(1, len(MODULE.parse_live_capabilities(output)))

    def test_distinguishes_executed_test_and_flow_gaps(self):
        row = {"capabilityId": "capability.cloudmold.catalog.catalog-query.get.v1", "interfaceName": "example.Api"}
        self.assertEqual("EXECUTED_BY_HSF_SKILL", MODULE.classify(row, skill_referenced=True, executed=True))
        self.assertEqual("TEST_GAP", MODULE.classify(row, skill_referenced=True, executed=False))
        self.assertEqual("FLOW_GAP", MODULE.classify(row, skill_referenced=False, executed=False))

    def test_collects_succeeded_capabilities_from_retained_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "run.json").write_text(json.dumps({
                "steps": [{
                    "capabilityId": "capability.cloudmold.mes.work-order.get.v1",
                    "status": "SUCCEEDED",
                }]
            }), encoding="utf-8")
            capabilities, sources = MODULE.collect_executed_capabilities(root)
            self.assertIn("capability.cloudmold.mes.work-order.get.v1", capabilities)
            self.assertEqual(["run.json"], sources["capability.cloudmold.mes.work-order.get.v1"])

    def test_skill_scan_excludes_test_fixture_capability_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "real-skill"
            (skill / "references").mkdir(parents=True)
            (skill / "tests").mkdir()
            (root / "registries").mkdir()
            declared = "capability.cloudmold.order.order-command.create.v1"
            fixture = "capability.cloudmold.fake.fixture.get.v1"
            registry_only = "capability.cloudmold.fake.registry.get.v1"
            (skill / "skill.json").write_text("{}", encoding="utf-8")
            (skill / "references/scenario.json").write_text(declared, encoding="utf-8")
            (skill / "tests/test_fixture.py").write_text(fixture, encoding="utf-8")
            (root / "registries/capabilities.json").write_text(registry_only, encoding="utf-8")

            capabilities, sources = MODULE.collect_skill_capabilities(root)

            self.assertEqual({declared}, capabilities)
            self.assertEqual(["real-skill/references/scenario.json"], sources[declared])


if __name__ == "__main__":
    unittest.main()
