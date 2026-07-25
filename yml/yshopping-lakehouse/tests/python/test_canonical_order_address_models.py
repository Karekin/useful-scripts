import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = json.loads((ROOT / "contracts/event-manifest-v1.json").read_text(encoding="utf-8"))


class CanonicalOrderAddressModelsTest(unittest.TestCase):
    def test_order_event_manifest_registers_address_vault_version(self):
        versions = MANIFEST["events"]["order.status.changed"]["versions"]
        self.assertEqual([1, 2, 3, 4], [entry["schema_version"] for entry in versions])
        self.assertEqual(
            "events/order-status-changed-v4.schema.json",
            versions[-1]["payload_schema"],
        )

    def test_order_event_and_current_dim_project_only_canonical_address_fields(self):
        dwd = (ROOT / "models/dwd/dwd-canonical-order-status-event.sql").read_text(encoding="utf-8")
        dim = (ROOT / "models/dim/dim-canonical-order-current.sql").read_text(encoding="utf-8")
        for token in ("address_ref", "address_snapshot_version", "destination_region_code"):
            self.assertIn(token, dwd)
            self.assertIn(token, dim)
        self.assertIn("schema_version IN (1, 2, 3, 4)", dwd)
        self.assertNotIn("receiver_name", dwd)
        self.assertNotIn("receiver_phone", dwd)
        self.assertNotIn("receiver_detail_address", dwd)
        self.assertNotIn("full_address", dwd)

    def test_listing_fulfillment_contract_accepts_v4_order_links(self):
        dqc = (
            ROOT / "tests/sql/11-canonical-listing-fulfillment-commerce-v2-contract.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("order_schema_version NOT IN (2, 3, 4)", dqc)
        self.assertIn("schema_version IN (2, 4)", dqc)


if __name__ == "__main__":
    unittest.main()
