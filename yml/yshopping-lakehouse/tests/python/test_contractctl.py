import importlib.machinery
import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "contractctl"
LOADER = importlib.machinery.SourceFileLoader("contractctl", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
CONTRACT = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(CONTRACT)


class ContractCtlTest(unittest.TestCase):
    def test_checked_in_contracts_and_examples_validate(self):
        CONTRACT.validate_all()

    def test_non_utc_event_time_is_rejected(self):
        errors = CONTRACT.validate_instance(
            "2026-07-12T10:00:00", {"type": "string", "format": "date-time"}, "$.occurred_at"
        )
        self.assertTrue(any("UTC" in error for error in errors))

    def test_removed_property_is_breaking(self):
        old = {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}}
        new = {"type": "object", "required": [], "properties": {}}
        errors = CONTRACT.compatibility_errors(old, new)
        self.assertTrue(any("property removed" in error for error in errors))
        self.assertTrue(any("required fields changed" in error for error in errors))

    def test_enum_widening_is_compatible_but_narrowing_is_not(self):
        old = {"type": "string", "enum": ["A", "B"]}
        wider = {"type": "string", "enum": ["A", "B", "C"]}
        narrower = {"type": "string", "enum": ["A"]}
        self.assertEqual(CONTRACT.compatibility_errors(old, wider), [])
        self.assertTrue(CONTRACT.compatibility_errors(old, narrower))

    def test_cancellation_saga_contract_has_exact_durable_states(self):
        schema = CONTRACT.load(
            CONTRACT.CONTRACTS / "events" / "order-cancellation-saga-status-changed-v1.schema.json"
        )
        states = schema["properties"]["current_status"]["enum"]
        self.assertEqual(
            states,
            [
                "REQUESTED",
                "RELEASING_RESERVATIONS",
                "RESERVATIONS_RELEASED",
                "CANCELLING_ORDER",
                "RETRY_SCHEDULED",
                "MANUAL_REVIEW",
                "COMPLETED",
            ],
        )
        reservation = schema["properties"]["reservations"]["items"]
        self.assertEqual(
            set(reservation["required"]),
            {"order_item_id", "reservation_id", "quantity"},
        )
        self.assertFalse(reservation["additionalProperties"])

    def test_order_contracts_accept_non_breaking_cancellation_pending_metadata(self):
        for version in (1, 2):
            schema = CONTRACT.load(
                CONTRACT.CONTRACTS / "events" / f"order-status-changed-v{version}.schema.json"
            )
            self.assertIn("CANCELLATION_PENDING", schema["properties"]["current_status"]["enum"])
            self.assertIn("CANCELLATION_PENDING", schema["properties"]["previous_status"]["enum"])
            self.assertIn("cancellation_saga_id", schema["properties"])
            self.assertIn("pre_cancellation_status", schema["properties"])
            self.assertNotIn("cancellation_saga_id", schema["required"])
            self.assertNotIn("pre_cancellation_status", schema["required"])

    def test_paid_cancellation_contracts_are_versioned_and_exact(self):
        manifest = CONTRACT.load(CONTRACT.CONTRACTS / "event-manifest-v1.json")
        expected_versions = {
            "inventory.stock.changed": [1, 2],
            "order.status.changed": [1, 2, 3],
            "order.cancellation_saga.status_changed": [1, 2],
            "fulfillment.status.changed": [1, 2],
            "payment.status.changed": [1, 2],
        }
        for event_type, versions in expected_versions.items():
            configs = manifest["events"][event_type]["versions"]
            self.assertEqual([config["schema_version"] for config in configs], versions)

        saga = CONTRACT.load(
            CONTRACT.CONTRACTS / "events" / "order-cancellation-saga-status-changed-v2.schema.json"
        )
        self.assertEqual(saga["properties"]["cancellation_mode"]["const"], "PAID_UNSHIPPED")
        self.assertEqual(
            saga["properties"]["active_step"]["enum"],
            ["NONE", "CANCEL_FULFILLMENT", "REFUND_PAYMENT", "RELEASE_RESERVATIONS", "CANCEL_ORDER"],
        )
        self.assertEqual(set(saga["properties"]["fulfillments"]["items"]["required"]),
                         {"fulfillment_id", "status"})

        fulfillment = CONTRACT.load(
            CONTRACT.CONTRACTS / "events" / "fulfillment-status-changed-v2.schema.json"
        )
        self.assertIn("CANCELLATION_PENDING", fulfillment["properties"]["current_status"]["enum"])
        self.assertIn("CANCELLED", fulfillment["properties"]["current_status"]["enum"])
        for field in ("cancellation_saga_id", "step_ordinal"):
            self.assertIn(field, fulfillment["required"])

        for filename in ("payment-status-changed-v2.schema.json", "inventory-stock-changed-v2.schema.json"):
            schema = CONTRACT.load(CONTRACT.CONTRACTS / "events" / filename)
            self.assertIn("cancellation_saga_id", schema["required"])
            self.assertIn("step_ordinal", schema["required"])

    def test_aftersales_contracts_are_registered_and_pii_minimized(self):
        manifest = CONTRACT.load(CONTRACT.CONTRACTS / "event-manifest-v1.json")
        expected = {
            "after_sale.status.changed",
            "after_sale.refund.status.changed",
            "return_fulfillment.status.changed",
            "return_fulfillment.inspection.decided",
            "after_sale.resolution_saga.status.changed",
        }
        self.assertTrue(expected <= set(manifest["events"]))
        forbidden = {"buyer_name", "buyer_phone", "receiver_name", "receiver_phone", "address"}
        for event_type in expected:
            config = manifest["events"][event_type]
            schema = CONTRACT.load(CONTRACT.CONTRACTS / config["payload_schema"])
            self.assertFalse(forbidden & set(schema["properties"]))

        return_schema = CONTRACT.load(
            CONTRACT.CONTRACTS / "events" / "return-fulfillment-status-changed-v1.schema.json"
        )
        return_payload = {
            "run_id", "return_fulfillment_id", "return_fulfillment_no", "after_sale_id",
            "return_fulfillment_item_id", "after_sale_item_id", "order_id", "order_item_id",
            "canonical_sku_id", "quantity", "owner_id", "warehouse_id", "uom_code",
            "return_shipping_amount_minor", "currency_code", "return_shipment_id", "carrier_code",
            "waybill_no", "handed_over_at", "in_transit_at", "received_at", "inspection_id",
            "receiver_id", "quality_status", "received_quantity", "accepted_quantity", "rejected_quantity",
            "inspection_result", "inspector_id", "inspected_at",
        }
        self.assertEqual(set(return_schema["properties"]), return_payload | {"previous_status", "current_status"})
        self.assertEqual(set(return_schema["required"]), set(return_schema["properties"]))
        self.assertEqual(
            return_schema["properties"]["current_status"]["enum"],
            ["CREATED", "HANDED_OVER", "IN_TRANSIT", "RECEIVED", "INSPECTION_ACCEPTED"],
        )
        inspection_schema = CONTRACT.load(
            CONTRACT.CONTRACTS / "events" / "return-fulfillment-inspection-decided-v1.schema.json"
        )
        self.assertEqual(set(inspection_schema["properties"]), return_payload | {"decision"})
        self.assertEqual(set(inspection_schema["required"]), set(inspection_schema["properties"]))

        case_payload = {
            "run_id", "after_sale_id", "after_sale_no", "after_sale_item_id", "after_sale_type",
            "reason_code", "responsibility", "reason", "order_id", "order_item_id",
            "canonical_sku_id", "quantity", "listing_id", "listing_offer_id", "buyer_id",
            "approved_amount_minor", "currency_code", "payment_id", "forward_fulfillment_id",
            "forward_shipment_id", "return_fulfillment_id", "return_shipment_id", "inspection_id",
            "resolution_saga_id", "refund_status",
        }
        case_schema = CONTRACT.load(
            CONTRACT.CONTRACTS / "events" / "after-sale-status-changed-v1.schema.json"
        )
        self.assertEqual(set(case_schema["properties"]), case_payload | {"previous_status", "current_status"})
        self.assertEqual(set(case_schema["required"]), set(case_schema["properties"]))
        refund_schema = CONTRACT.load(
            CONTRACT.CONTRACTS / "events" / "after-sale-refund-status-changed-v1.schema.json"
        )
        self.assertEqual(
            set(refund_schema["properties"]),
            case_payload | {"previous_status", "current_status", "payment_refund_transaction_id",
                            "refund_id", "refunded_amount_minor", "provider_code", "step_ordinal"},
        )
        self.assertEqual(set(refund_schema["required"]), set(refund_schema["properties"]))
        saga_schema = CONTRACT.load(
            CONTRACT.CONTRACTS / "events" / "after-sale-resolution-saga-status-changed-v1.schema.json"
        )
        saga_payload = {
            "run_id", "saga_id", "after_sale_id", "after_sale_item_id", "order_id", "order_item_id",
            "payment_id", "return_fulfillment_id", "return_shipment_id", "inspection_id",
            "canonical_sku_id", "quantity", "accepted_quantity", "returned_quantity", "uom_code",
            "approved_amount_minor", "refunded_amount_minor", "currency_code", "previous_status",
            "current_status", "active_step", "step_ordinal", "attempt", "inventory_operation_id",
            "inventory_ledger_transaction_id", "payment_refund_transaction_id",
            "order_refund_operation_id", "order_return_operation_id", "order_version", "checkpoints",
            "error_code", "error_message", "next_retry_at",
        }
        self.assertEqual(set(saga_schema["properties"]), saga_payload)
        self.assertEqual(set(saga_schema["required"]), saga_payload)


if __name__ == "__main__":
    unittest.main()
