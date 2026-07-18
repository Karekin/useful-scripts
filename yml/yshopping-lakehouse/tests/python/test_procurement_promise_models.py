import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = json.loads((ROOT / "contracts/event-manifest-v1.json").read_text(encoding="utf-8"))


class ProcurementPromiseModelsTest(unittest.TestCase):
    def test_procurement_promise_contract_is_registered(self):
        config = MANIFEST["events"]["procurement.purchase_promise.status_changed"]
        self.assertEqual(1, config["schema_version"])
        schema = json.loads(
            (ROOT / "contracts" / config["payload_schema"]).read_text(encoding="utf-8")
        )
        for field in (
            "purchase_order_id",
            "purchase_order_line_id",
            "promised_receipt_at",
            "promise_timezone",
            "grace_minutes",
            "pause_minutes",
        ):
            self.assertIn(field, schema["properties"])

    def test_procurement_promise_models_keep_otif_separate_from_fulfillment(self):
        dwd = (ROOT / "models/dwd/dwd-canonical-procurement-purchase-promise-event.sql").read_text(
            encoding="utf-8"
        )
        dws = (ROOT / "models/dws/dws-canonical-procurement-otif-current.sql").read_text(
            encoding="utf-8"
        )
        ads = (ROOT / "models/ads/ads-canonical-procurement-otif-metrics.sql").read_text(
            encoding="utf-8"
        )
        self.assertIn("procurement.purchase_promise.status_changed", dwd)
        self.assertIn("effective_deadline_at", dws)
        self.assertIn("DUE_ON_TIME_IN_FULL", dws)
        self.assertIn("procurement_otif_rate", ads)
        self.assertNotIn("delivery_promise_version_ref", dws)
        self.assertNotIn("buyer_delivery_promise_hit_rate", ads)

    def test_procurement_promise_dqc_covers_current_and_metric_consistency(self):
        dqc = (ROOT / "tests/sql/43-canonical-procurement-otif-contract.sql").read_text(
            encoding="utf-8"
        )
        for check in (
            "procurement_promise_current_duplicate",
            "procurement_promise_invalid_current_fields",
            "procurement_otif_status_mismatch",
            "procurement_otif_metric_rate_mismatch",
        ):
            self.assertIn(check, dqc)

    def test_apply_order_places_procurement_promise_before_ads(self):
        lines = (
            ROOT / "models/apply-order-v1.txt"
        ).read_text(encoding="utf-8").splitlines()
        positions = {line: index for index, line in enumerate(lines)}
        dwd = "models/dwd/dwd-canonical-procurement-purchase-promise-event.sql"
        dim = "models/dim/dim-canonical-procurement-purchase-promise-current.sql"
        dws = "models/dws/dws-canonical-procurement-otif-current.sql"
        ads = "models/ads/ads-canonical-procurement-otif-metrics.sql"
        self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[dwd])
        self.assertLess(positions[dwd], positions[dim])
        self.assertLess(positions[dim], positions[dws])
        self.assertLess(positions[dws], positions[ads])


if __name__ == "__main__":
    unittest.main()
