CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_inventory_migration_pilot_item_current AS
SELECT latest.*
FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id,pilot_item_id) AS item_event_count,
           ROW_NUMBER() OVER (
             PARTITION BY tenant_id,pilot_item_id
             ORDER BY item_version DESC,recorded_at DESC,event_id DESC
           ) AS item_rank
    FROM yshopping_dwd.dwd_canonical_inventory_migration_pilot_item_event event
) latest
WHERE item_rank=1;
