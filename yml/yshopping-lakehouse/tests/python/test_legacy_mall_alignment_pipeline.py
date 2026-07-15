import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
PIPELINE = ROOT / "pipelines" / "legacy-mall-alignment-mysql-to-starrocks.yaml"
COMPOSE = ROOT / "docker-compose.yml"
LAKEHOUSECTL = ROOT / "scripts" / "lakehousectl"

EXPECTED_TABLE_PATTERN = (
    "ruoyi-vue-pro.(promotion_coupon|promotion_coupon_template|"
    "promotion_bargain_activity|promotion_combination_activity|"
    "promotion_discount_activity|promotion_point_activity|"
    "promotion_reward_activity|promotion_seckill_activity|"
    "trade_order|trade_order_item|product_favorite)"
)


class LegacyMallAlignmentPipelineTest(unittest.TestCase):
    def test_source_and_route_use_the_exact_bounded_table_set(self):
        text = PIPELINE.read_text(encoding="utf-8")
        table_patterns = re.findall(
            r"^\s*(?:tables|-\s+source-table):\s*(.+)$", text, re.MULTILINE
        )
        self.assertEqual([EXPECTED_TABLE_PATTERN, EXPECTED_TABLE_PATTERN], table_patterns)
        self.assertNotIn("product_spu", text)
        self.assertIn("sink-table: yshopping_ods.<>", text)
        self.assertIn("replace-symbol: <>", text)

    def test_pipeline_reserves_a_non_overlapping_mysql_server_id_range(self):
        text = PIPELINE.read_text(encoding="utf-8")
        self.assertEqual(["5700-5704"], re.findall(r"^\s*server-id:\s*(\S+)$", text, re.MULTILINE))

    def test_compose_registers_the_legacy_mall_tool_service(self):
        text = COMPOSE.read_text(encoding="utf-8")
        self.assertIn("legacy-mall-cdc-cli:", text)
        self.assertIn("container_name: yshopping-legacy-mall-cdc-cli", text)
        self.assertIn("/opt/pipelines/legacy-mall-alignment-mysql-to-starrocks.yaml", text)
        self.assertIn("/tmp/legacy-mall-alignment-mysql-to-starrocks.yaml", text)

    def test_lakehousectl_registers_the_submission_command(self):
        text = LAKEHOUSECTL.read_text(encoding="utf-8")
        self.assertIn("submit-legacy-mall-cdc", text)
        self.assertIn("--profile tools run --rm legacy-mall-cdc-cli", text)
        self.assertIn('test -f "$ROOT_DIR/pipelines/legacy-mall-alignment-mysql-to-starrocks.yaml"', text)


if __name__ == "__main__":
    unittest.main()
