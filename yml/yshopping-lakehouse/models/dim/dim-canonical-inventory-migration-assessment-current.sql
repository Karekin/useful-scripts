CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_inventory_migration_assessment_current AS
SELECT
    event_id, tenant_id, migration_run_id, assessment_id, assessment_version,
    legacy_balance_id, migration_source_system, migration_source_type, source_id,
    source_classification, source_version, source_updated_at, source_snapshot_hash,
    source_owner_id, resolved_owner_type, resolved_owner_id,
    source_sku_id, resolved_canonical_sku_id,
    source_warehouse_id, resolved_warehouse_id,
    source_location_id, resolved_location_id, source_lot_id, resolved_lot_id,
    lot_tracking_policy, stock_status, quality_status, source_uom_code, resolved_base_uom_code,
    source_on_hand_quantity, source_reserved_quantity, source_in_transit_quantity,
    active_reservation_count, active_reservation_quantity,
    reservation_allocation_count, reservation_allocation_quantity,
    assessment_status, blocker_codes_json, policy_version, verification_ref, assessed_at,
    occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
    assessment_event_count
FROM (
    SELECT event.*,
           COUNT(*) OVER (
               PARTITION BY tenant_id, migration_run_id, migration_source_system, migration_source_type, source_id
           ) AS assessment_event_count,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, migration_run_id, migration_source_system, migration_source_type, source_id
               ORDER BY assessment_version DESC, recorded_at DESC, event_id DESC
           ) AS assessment_rank
    FROM yshopping_dwd.dwd_canonical_inventory_migration_assessment_event event
) latest
WHERE assessment_rank = 1;
