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
            "inventory.stock.changed": [1, 2, 3, 4],
            "order.status.changed": [1, 2, 3],
            "order.cancellation_saga.status_changed": [1, 2],
            "fulfillment.status.changed": [1, 2],
            "payment.status.changed": [1, 2],
        }
        for event_type, versions in expected_versions.items():
            configs = manifest["events"][event_type]["versions"]
            self.assertEqual([config["schema_version"] for config in configs], versions)

        inventory_v3 = manifest["events"]["inventory.stock.changed"]["versions"][2]
        self.assertEqual(inventory_v3["aggregate_type"], "inventory_balance_v3")

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

    def test_identity_merchant_and_warehouse_master_events_are_registered_and_pii_minimized(self):
        manifest = CONTRACT.load(CONTRACT.CONTRACTS / "event-manifest-v1.json")
        expected = {
            "identity.source.linked": "cloudmold-identity",
            "merchant.onboarding.status_changed": "cloudmold-merchant",
            "merchant.entity.status_changed": "cloudmold-merchant",
            "merchant.operator_assignment.changed": "cloudmold-merchant",
            "merchant.source_mapping.changed": "cloudmold-merchant",
            "warehouse.entity.status_changed": "cloudmold-warehouse",
            "warehouse.source_mapping.changed": "cloudmold-warehouse",
            "warehouse.operator_assignment.changed": "cloudmold-warehouse",
        }
        self.assertTrue(set(expected) <= set(manifest["events"]))

        envelope = CONTRACT.load(CONTRACT.CONTRACTS / manifest["envelope"])
        source_systems = set(envelope["properties"]["source_system"]["enum"])
        self.assertTrue(set(expected.values()) <= source_systems)

        forbidden = {
            "tenant_id", "registration_number", "license_no", "contact_mobile",
            "mobile", "id_card", "legal_representative_name", "bank_account_no",
        }
        for event_type in expected:
            config = manifest["events"][event_type]
            versions = config.get("versions", [config])
            for version in versions:
                schema = CONTRACT.load(CONTRACT.CONTRACTS / version["payload_schema"])
                self.assertFalse(
                    forbidden & set(schema["properties"]),
                    f"{event_type} v{version['schema_version']} exposes envelope-only or sensitive fields",
                )

        source_mapping = CONTRACT.load(
            CONTRACT.CONTRACTS / "events" / "merchant-source-mapping-changed-v1.schema.json"
        )
        source_mapping_payload = {
            "run_id", "migration_run_id", "mapping_id", "source_system", "source_type", "source_id",
            "target_type", "target_id", "valid_from", "valid_to", "previous_status", "current_status",
            "verification_ref",
        }
        self.assertEqual(set(source_mapping["properties"]), source_mapping_payload)
        self.assertEqual(set(source_mapping["required"]), source_mapping_payload)
        self.assertEqual(source_mapping["properties"]["target_type"]["enum"],
                         ["LEGAL_ENTITY", "MERCHANT", "SHOP"])
        self.assertEqual(source_mapping["properties"]["current_status"]["enum"], ["ACTIVE", "REVOKED"])

    def test_listing_unpublish_saga_contract_is_exact_and_registered(self):
        manifest = CONTRACT.load(CONTRACT.CONTRACTS / "event-manifest-v1.json")
        config = manifest["events"]["listing.sales_eligibility_enforcement.status_changed"]
        self.assertEqual(config["schema_version"], 1)
        self.assertEqual(config["aggregate_type"], "listing_sales_eligibility_enforcement")
        schema = CONTRACT.load(CONTRACT.CONTRACTS / config["payload_schema"])
        expected_fields = {
            "run_id", "saga_id", "source_event_id", "source_entity_type",
            "source_aggregate_version", "merchant_id", "shop_id", "previous_status",
            "current_status", "active_step", "attempt", "reason", "expected_listing_count",
            "unpublished_listing_count", "skipped_listing_count", "error_code", "error_message",
            "next_retry_at",
        }
        self.assertEqual(set(schema["properties"]), expected_fields)
        self.assertEqual(set(schema["required"]), expected_fields)
        self.assertEqual(
            schema["properties"]["current_status"]["enum"],
            ["REQUESTED", "UNPUBLISHING", "RETRY_SCHEDULED", "MANUAL_REVIEW", "COMPLETED"],
        )
        self.assertEqual(schema["properties"]["source_entity_type"]["enum"], ["MERCHANT", "SHOP"])

    def test_merchant_deposit_contract_is_minor_unit_exact_and_pii_minimized(self):
        manifest = CONTRACT.load(CONTRACT.CONTRACTS / "event-manifest-v1.json")
        config = manifest["events"]["merchant.deposit.ledger_posted"]
        self.assertEqual(config["schema_version"], 1)
        self.assertEqual(config["aggregate_type"], "MERCHANT_DEPOSIT_ACCOUNT")
        schema = CONTRACT.load(CONTRACT.CONTRACTS / config["payload_schema"])
        expected = {
            "run_id", "merchant_id", "account_id", "ledger_entry_id", "entry_type", "amount_minor",
            "currency", "held_delta_minor", "frozen_delta_minor", "held_before_minor", "held_after_minor",
            "frozen_before_minor", "frozen_after_minor", "required_before_minor", "required_after_minor",
            "paid_after_minor", "deducted_after_minor", "previous_coverage_status", "current_coverage_status",
            "previous_enforcement_status", "current_enforcement_status", "policy_version",
            "business_reference", "reason_code", "evidence_ref",
        }
        self.assertEqual(set(schema["properties"]), expected)
        self.assertEqual(set(schema["required"]), expected)
        self.assertEqual(schema["properties"]["currency"]["pattern"], "^[A-Z]{3}$")
        forbidden = {"bank_account", "phone", "identity_number", "voucher_url", "payment_credential"}
        self.assertFalse(forbidden & set(schema["properties"]))

    def test_inventory_lot_contracts_are_registered_and_keep_source_identity_distinct(self):
        manifest = CONTRACT.load(CONTRACT.CONTRACTS / "event-manifest-v1.json")
        lifecycle = manifest["events"]["inventory.lot.lifecycle.changed"]
        mapping = manifest["events"]["inventory.lot.source_mapping.changed"]
        self.assertEqual(lifecycle["aggregate_type"], "inventory_lot")
        self.assertEqual(mapping["aggregate_type"], "inventory_lot_source_mapping")
        lifecycle_schema = CONTRACT.load(CONTRACT.CONTRACTS / lifecycle["payload_schema"])
        mapping_schema = CONTRACT.load(CONTRACT.CONTRACTS / mapping["payload_schema"])
        self.assertEqual(lifecycle_schema["properties"]["current_status"]["enum"],
                         ["ACTIVE", "RECALLED", "CLOSED"])
        self.assertIn("recall_reference", lifecycle_schema["required"])
        self.assertIn("mapping_source_system", mapping_schema["required"])
        self.assertIn("source_id", mapping_schema["required"])
        self.assertIn("lot_id", mapping_schema["required"])
        self.assertNotEqual("source_id", "lot_id")

    def test_inventory_migration_contracts_preserve_provenance_and_single_opening_driver(self):
        manifest = CONTRACT.load(CONTRACT.CONTRACTS / "event-manifest-v1.json")
        config = manifest["events"]["inventory.migration.balance_assessed"]
        self.assertEqual([version["schema_version"] for version in config["versions"]], [1, 2])
        self.assertEqual(config["aggregate_type"], "inventory_migration_assessment")
        schema = CONTRACT.load(CONTRACT.CONTRACTS / config["versions"][1]["payload_schema"])
        self.assertEqual(set(schema["required"]), set(schema["properties"]))
        self.assertIn("active_reservation_count", schema["properties"])
        self.assertIn("reservation_allocation_count", schema["properties"])
        self.assertEqual(schema["properties"]["reservation_allocation_count"]["const"], 0)
        self.assertEqual(schema["properties"]["source_system"]["const"], "CLOUDMOLD_INVENTORY_V1")
        self.assertEqual(schema["properties"]["source_type"]["const"], "BALANCE")
        self.assertEqual(
            schema["properties"]["assessment_status"]["enum"],
            ["ELIGIBLE", "BLOCKED", "REJECTED"],
        )
        forbidden = {"contact_mobile", "contact_name", "id_card", "address", "buyer_id"}
        self.assertFalse(forbidden & set(schema["properties"]))

        qualified = manifest["events"]["inventory.migration.balance_qualified"]
        qualified_schema = CONTRACT.load(CONTRACT.CONTRACTS / qualified["payload_schema"])
        self.assertEqual(qualified["aggregate_type"], "inventory_migration_qualification")
        self.assertEqual(qualified_schema["properties"]["source_classification"]["const"],
                         "CONTROLLED_CANARY")
        self.assertEqual(qualified_schema["properties"]["source_reserved_quantity"]["pattern"],
                         "^0(\\.0{1,6})?$")

        opening = manifest["events"]["inventory.stock.changed"]["versions"][3]
        opening_schema = CONTRACT.load(CONTRACT.CONTRACTS / opening["payload_schema"])
        self.assertEqual(opening["aggregate_type"], "inventory_balance_v3")
        self.assertEqual(opening_schema["properties"]["movement_type"]["const"], "MIGRATION_OPENING")
        self.assertEqual(opening_schema["properties"]["opening_driver"]["const"],
                         "INVENTORY_MIGRATION_QUALIFICATION")
        self.assertEqual(opening_schema["properties"]["delta_reserved_quantity"]["pattern"],
                         "^0(\\.0{1,6})?$")

    def test_inventory_migration_pilot_is_admission_only_and_actor_ids_are_internal(self):
        manifest = CONTRACT.load(CONTRACT.CONTRACTS / "event-manifest-v1.json")
        batch = manifest["events"]["inventory.migration.pilot_batch_status_changed"]
        item = manifest["events"]["inventory.migration.pilot_item_status_changed"]
        self.assertEqual(batch["aggregate_type"], "inventory_migration_pilot_batch")
        self.assertEqual(item["aggregate_type"], "inventory_migration_pilot_item")
        batch_schema = CONTRACT.load(CONTRACT.CONTRACTS / batch["payload_schema"])
        item_schema = CONTRACT.load(CONTRACT.CONTRACTS / item["payload_schema"])
        self.assertEqual(set(batch_schema["required"]), set(batch_schema["properties"]))
        self.assertEqual(set(item_schema["required"]), set(item_schema["properties"]))
        self.assertFalse(batch_schema["properties"]["execution_available"]["const"])
        self.assertFalse(batch_schema["properties"]["cutover_ready"]["const"])
        self.assertEqual(batch_schema["properties"]["source_classification"]["const"],
                         "PRODUCTION_HISTORY")
        self.assertEqual(item_schema["properties"]["uom_conversion_ratio"]["pattern"],
                         "^1(\\.0+)?$")
        self.assertEqual(item_schema["properties"]["active_reservation_count"]["const"], 0)
        self.assertNotIn("principal_id", batch_schema["properties"])
        self.assertIn("requester_system_user_id", batch_schema["properties"])
        forbidden = {"mobile", "phone", "id_card", "contact_name", "address"}
        self.assertFalse(forbidden & set(batch_schema["properties"]))
        self.assertFalse(forbidden & set(item_schema["properties"]))

    def test_inventory_migration_shadow_contract_separates_state_result_and_effects(self):
        manifest = CONTRACT.load(CONTRACT.CONTRACTS / "event-manifest-v1.json")
        window = manifest["events"]["inventory.migration.shadow_window_status_changed"]
        round_config = manifest["events"]["inventory.migration.shadow_round_completed"]
        comparison = manifest["events"]["inventory.migration.shadow_item_compared"]
        self.assertEqual(window["aggregate_type"], "inventory_migration_shadow_window")
        self.assertEqual(round_config["aggregate_type"], "inventory_migration_shadow_round")
        self.assertEqual(comparison["aggregate_type"], "inventory_migration_shadow_comparison")
        window_schema = CONTRACT.load(CONTRACT.CONTRACTS / window["payload_schema"])
        round_schema = CONTRACT.load(CONTRACT.CONTRACTS / round_config["payload_schema"])
        comparison_schema = CONTRACT.load(CONTRACT.CONTRACTS / comparison["payload_schema"])
        self.assertEqual(window_schema["properties"]["window_status"]["enum"],
                         ["OPEN", "OBSERVING", "VERIFIED"])
        self.assertEqual(window_schema["properties"]["verification_result"]["enum"],
                         ["PENDING", "MATCH", "DIFFERENT", "UNCOMPARABLE"])
        self.assertEqual(window_schema["properties"]["watermark_kind"]["const"], "MYSQL_GTID_SET")
        self.assertEqual(round_schema["properties"]["gtid_validator_version"]["const"],
                         "MYSQL_GTID_SET_CONTAINS_V1")
        self.assertEqual(round_schema["properties"]["target_contains_source"],
                         {"type": "boolean"})
        self.assertEqual(comparison_schema["properties"]["target_projection_kind"]["const"],
                         "CANONICAL_INVENTORY_V3_SHADOW_PROJECTION")
        self.assertIn("TARGET_MISSING", comparison_schema["properties"]["reason_codes"]
                      ["items"]["enum"])
        reason_codes = set(comparison_schema["properties"]["reason_codes"]["items"]["enum"])
        self.assertTrue({
            "TARGET_WATERMARK_NOT_COVERED", "WATERMARK_LAG_EXCEEDED",
            "ROUND_GAP_EXCEEDED", "WATERMARK_VALIDATION_FAILED",
        } <= reason_codes)
        self.assertNotIn("SOURCE_READ_ERROR",
                         reason_codes)
        for schema in (window_schema, round_schema, comparison_schema):
            self.assertFalse(schema["properties"]["execution_available"]["const"])
            self.assertFalse(schema["properties"]["cutover_ready"]["const"])
            self.assertEqual(set(schema["required"]), set(schema["properties"]))


if __name__ == "__main__":
    unittest.main()
