import importlib.machinery
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "sourceassetctl"
LOADER = importlib.machinery.SourceFileLoader("sourceassetctl", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
SOURCE_ASSETS = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(SOURCE_ASSETS)


class SourceAssetCtlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = SOURCE_ASSETS.extract_inventory()

    def test_checked_in_source_snapshot_validates(self):
        self.assertEqual([], SOURCE_ASSETS.validate_inventory(self.inventory))
        self.assertEqual(6, len(self.inventory["documents"]))

    def test_inventory_is_complete_and_deterministic_for_the_locked_snapshot(self):
        summary = self.inventory["summary"]
        self.assertEqual(1790, summary["unique_asset_count"])
        self.assertEqual(728, summary["unique_logical_asset_count"])
        self.assertEqual(728, summary["global_unique_name_count"])
        self.assertEqual(
            {
                "candidate": 718,
                "create_target": 491,
                "dependency": 303,
                "insert_target": 278,
            },
            summary["unique_by_kind"],
        )
        self.assertEqual(2364, summary["document_role_unique_count"])
        self.assertEqual(
            {
                "candidate": 1139,
                "create_target": 501,
                "dependency": 442,
                "insert_target": 282,
            },
            summary["document_role_unique_by_kind"],
        )
        self.assertEqual(752, summary["reference_occurrence_count"])
        self.assertEqual(
            {
                "code_symbol": 35,
                "cte": 124,
                "physical_table": 561,
                "python_import": 26,
                "unclassified_reference": 6,
            },
            summary["references_by_kind"],
        )
        self.assertEqual(1327, summary["topic_count"])
        self.assertEqual(1, summary["unparsed_statement_line_count"])
        asset_ids = [item["asset_id"] for item in self.inventory["assets"]]
        self.assertEqual(asset_ids, sorted(asset_ids))
        self.assertEqual(len(asset_ids), len(set(asset_ids)))
        logical_ids = [item["logical_asset_id"] for item in self.inventory["logical_assets"]]
        self.assertEqual(logical_ids, sorted(logical_ids))
        self.assertEqual(len(logical_ids), len(set(logical_ids)))

    def test_known_source_defects_remain_visible_instead_of_being_normalized_away(self):
        assets = {item["asset_id"]: item for item in self.inventory["assets"]}
        self.assertIn("ods:create_target:ods_goods_goods_white_df", assets)
        misplaced = assets["ods:create_target:ods_goods_goods_white_df"]
        self.assertEqual(["DIM", "ODS"], misplaced["document_layers"])
        self.assertIn("wrong_layer_create", misplaced["occurrences"][0]["risk_flags"])
        self.assertIn("ods:create_target:ods_scm_sorting_di", assets)
        duplicate = assets["dws:create_target:dws_com_trend_user_target_1d"]
        self.assertEqual(2, len(duplicate["occurrences"]))
        issue = self.inventory["unparsed_statement_lines"][0]
        self.assertEqual(6141, issue["line"])
        self.assertIn("{full_name}", issue["text"])
        self.assertIn("ods:candidate:ods_eliminate_user_coin_log_df", assets)
        self.assertIn("ods:candidate:ods__", assets)

    def test_code_references_are_classified_without_polluting_physical_dependencies(self):
        assets = {item["asset_id"] for item in self.inventory["assets"]}
        for false_dependency in ("pathlib", "typing", "__future__", "tt0", "base"):
            self.assertFalse(any(item.endswith(f":{false_dependency}") for item in assets))
        reference_kinds = {
            (item["qualified_name"], item["reference_kind"])
            for item in self.inventory["references"]
        }
        self.assertIn(("typing", "python_import"), reference_kinds)
        self.assertIn(("tt0", "cte"), reference_kinds)

    def test_qualified_names_and_markdown_bold_are_parsed_without_losing_source_location(self):
        assets = {item["asset_id"]: item for item in self.inventory["assets"]}
        login = assets["ods:create_target:ods_user_user_login_di"]
        self.assertEqual(1917, login["occurrences"][0]["line"])
        self.assertEqual("yshopping.ods_user_user_login_di", login["occurrences"][0]["qualified_name"])
        order = assets["dws:create_target:dws_trade_order_buyer_target_1d"]
        self.assertEqual("yshopping.dws_trade_order_buyer_target_1d", order["occurrences"][0]["qualified_name"])

    def test_source_drift_is_rejected_against_a_manifest_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {"source_documents": []}
            for layer, filename in SOURCE_ASSETS.LAYER_DOCUMENTS.items():
                path = root / filename
                path.write_text("# source\nCREATE TABLE sample_table (id BIGINT);\n", encoding="utf-8")
                manifest["source_documents"].append(
                    {
                        "filename": filename,
                        "sha256": SOURCE_ASSETS.sha256(path),
                        "line_count": 2,
                    }
                )
            inventory = SOURCE_ASSETS.extract_inventory(root)
            self.assertEqual([], SOURCE_ASSETS.validate_inventory(inventory, manifest))
            broken = json.loads(json.dumps(manifest))
            broken["source_documents"][0]["sha256"] = "0" * 64
            errors = SOURCE_ASSETS.validate_inventory(inventory, broken)
            self.assertTrue(any("source drift" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
