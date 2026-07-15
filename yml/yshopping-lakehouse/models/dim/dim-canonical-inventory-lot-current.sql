CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_inventory_lot_current AS
SELECT
    event_id,
    tenant_id,
    lot_id,
    lot_version,
    owner_type,
    owner_id,
    canonical_sku_id,
    lot_code,
    manufactured_on,
    expires_on,
    received_at,
    previous_status,
    current_status,
    change_type,
    reason_code,
    evidence_ref,
    recall_reference,
    run_id,
    migration_run_id,
    occurred_at,
    recorded_at,
    correlation_id,
    lifecycle_event_count,
    minimum_lot_version
FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id, lot_id) AS lifecycle_event_count,
           MIN(lot_version) OVER (PARTITION BY tenant_id, lot_id) AS minimum_lot_version,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, lot_id
               ORDER BY lot_version DESC, recorded_at DESC, event_id DESC
           ) AS lot_version_rank
    FROM yshopping_dwd.dwd_canonical_inventory_lot_lifecycle_event event
) latest
WHERE lot_version_rank = 1;
