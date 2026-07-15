CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_inventory_migration_qualification_current AS
SELECT
    event_id, tenant_id, migration_run_id, assessment_id, qualification_id, qualification_version,
    migration_source_system, migration_source_type, source_id, source_classification,
    source_version, source_updated_at, source_snapshot_hash,
    owner_type, owner_id, canonical_sku_id, warehouse_source_mapping_id, warehouse_id, location_id,
    lot_tracking_policy, lot_id, stock_status, quality_status, base_uom_code,
    source_on_hand_quantity, source_reserved_quantity, source_in_transit_quantity,
    resolved_blocker_codes_json, qualification_status, policy_version, verification_ref, qualified_at,
    occurred_at, recorded_at, correlation_id, causation_id, idempotency_key, qualification_event_count
FROM (
    SELECT event.*,
           COUNT(*) OVER (
               PARTITION BY tenant_id, migration_run_id, migration_source_system, migration_source_type, source_id
           ) AS qualification_event_count,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, migration_run_id, migration_source_system, migration_source_type, source_id
               ORDER BY qualification_version DESC, recorded_at DESC, event_id DESC
           ) AS qualification_rank
    FROM yshopping_dwd.dwd_canonical_inventory_migration_qualification_event event
) latest
WHERE qualification_rank = 1;
