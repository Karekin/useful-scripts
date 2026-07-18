import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
PIPELINE = ROOT / "pipelines" / "legacy-commerce-observability-mysql-to-starrocks.yaml"
COMPOSE = ROOT / "docker-compose.yml"
LAKEHOUSECTL = ROOT / "scripts" / "lakehousectl"

EXPECTED_TABLE_PATTERN = (
    "ruoyi-vue-pro.(pay_order|pay_refund|member_user|"
    "product_browse_history|trade_cart)"
)


class LegacyCommerceObservabilityPipelineTest(unittest.TestCase):
    def test_source_and_route_use_the_exact_bounded_table_set(self):
        text = PIPELINE.read_text(encoding="utf-8")
        table_patterns = re.findall(
            r"^\s*(?:tables|-\s+source-table):\s*(.+)$", text, re.MULTILINE
        )
        self.assertEqual(EXPECTED_TABLE_PATTERN, table_patterns[0])
        self.assertEqual(EXPECTED_TABLE_PATTERN, table_patterns[-1])
        self.assertEqual(
            [
                "ruoyi-vue-pro.pay_order",
                "ruoyi-vue-pro.pay_refund",
                "ruoyi-vue-pro.member_user",
                "ruoyi-vue-pro.product_browse_history",
                "ruoyi-vue-pro.trade_cart",
            ],
            table_patterns[1:-1],
        )
        self.assertIn("sink-table: yshopping_ods.<>", text)
        self.assertIn("replace-symbol: <>", text)
        self.assertNotIn("trade_order|", text)

    def test_pipeline_reserves_a_non_overlapping_mysql_server_id_range(self):
        text = PIPELINE.read_text(encoding="utf-8")
        self.assertEqual(
            ["5800-5804"],
            re.findall(r"^\s*server-id:\s*(\S+)$", text, re.MULTILINE),
        )

    def test_transform_uses_per_table_allowlists_and_excludes_sensitive_fields(self):
        text = PIPELINE.read_text(encoding="utf-8")
        projections = re.findall(r"^\s*projection:\s*(.+)$", text, re.MULTILINE)
        self.assertEqual(5, len(projections))
        projected_text = "\n".join(projections)
        for required in (
            "merchant_order_id",
            "refund_price",
            "register_terminal",
            "user_deleted",
            "selected",
        ):
            self.assertIn(required, projected_text)
        for forbidden in (
            "notify_url",
            "user_ip",
            "channel_user_id",
            "channel_notify_data",
            "channel_error_msg",
            "password",
            "mobile",
            "email",
            "nickname",
            "avatar",
            "birthday",
            "mark",
            "tag_ids",
        ):
            self.assertNotIn(forbidden, projected_text)

    def test_compose_registers_the_tool_service(self):
        text = COMPOSE.read_text(encoding="utf-8")
        self.assertIn("legacy-commerce-observability-cdc-cli:", text)
        self.assertIn(
            "container_name: yshopping-legacy-commerce-observability-cdc-cli", text
        )
        self.assertIn(
            "/opt/pipelines/legacy-commerce-observability-mysql-to-starrocks.yaml", text
        )

    def test_lakehousectl_registers_submission_and_reconciliation(self):
        text = LAKEHOUSECTL.read_text(encoding="utf-8")
        self.assertIn("submit-legacy-commerce-observability-cdc", text)
        self.assertIn("reconcile-legacy-commerce-observability", text)
        self.assertIn(
            "--profile tools run --rm legacy-commerce-observability-cdc-cli", text
        )


if __name__ == "__main__":
    unittest.main()
