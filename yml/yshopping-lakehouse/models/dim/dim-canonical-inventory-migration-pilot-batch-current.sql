CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_inventory_migration_pilot_batch_current AS
SELECT latest.*
FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id,pilot_batch_id) AS batch_event_count,
           ROW_NUMBER() OVER (
             PARTITION BY tenant_id,pilot_batch_id
             ORDER BY batch_version DESC,recorded_at DESC,event_id DESC
           ) AS batch_rank
    FROM yshopping_dwd.dwd_canonical_inventory_migration_pilot_batch_event event
) latest
WHERE batch_rank=1;
