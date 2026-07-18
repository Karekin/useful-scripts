import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = json.loads((ROOT / "contracts/event-manifest-v1.json").read_text(encoding="utf-8"))


class InventoryCostAgingModelsTest(unittest.TestCase):
    def test_cost_evidenced_inventory_event_is_registered(self):
        versions = MANIFEST["events"]["inventory.stock.changed"]["versions"]
        self.assertTrue(any(version["schema_version"] == 5 for version in versions))

    def test_cost_layer_is_fifo_and_fail_closed(self):
        dws = (ROOT / "models/dws/dws-canonical-inventory-cost-layer-current.sql").read_text(
            encoding="utf-8"
        )
        ads = (ROOT / "models/ads/ads-canonical-inventory-cost-aging-metrics.sql").read_text(
            encoding="utf-8"
        )
        for token in ("newer_inbound_quantity", "remaining_quantity", "is_cost_complete"):
            self.assertIn(token, dws)
        self.assertIn("DATE_SUB(NOW(), INTERVAL 90 DAY)", ads)
        self.assertIn("BLOCKED_INCOMPLETE_COST_COVERAGE", ads)
        self.assertIn("READY_COSTED_FIFO_V1", ads)
        self.assertNotIn("COALESCE(cogs_90d.cost_of_goods_sold_amount_minor, 1)", ads)

    def test_dqc_covers_value_and_turnover_invariants(self):
        dqc = (ROOT / "tests/sql/44-canonical-inventory-cost-aging-contract.sql").read_text(
            encoding="utf-8"
        )
        for check in (
            "inventory_cost_v5_total_mismatch",
            "inventory_cost_v5_missing_authority",
            "inventory_aged_value_exceeds_inventory_value",
            "inventory_turnover_days_formula_mismatch",
            "inventory_cost_readiness_false_positive",
        ):
            self.assertIn(check, dqc)


if __name__ == "__main__":
    unittest.main()
