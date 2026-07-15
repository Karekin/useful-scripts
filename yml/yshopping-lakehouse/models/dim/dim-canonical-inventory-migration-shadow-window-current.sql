CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_inventory_migration_shadow_window_current AS
SELECT latest.*
FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id,shadow_window_id) AS window_event_count,
           ROW_NUMBER() OVER (
             PARTITION BY tenant_id,shadow_window_id
             ORDER BY window_version DESC,recorded_at DESC,event_id DESC
           ) AS window_rank
    FROM yshopping_dwd.dwd_canonical_inventory_migration_shadow_window_event event
) latest
WHERE window_rank=1;
