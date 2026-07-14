CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_inventory_balance_current AS
SELECT
    tenant_id,
    balance_id,
    canonical_sku_id,
    warehouse_id,
    owner_id,
    quality_status,
    uom_code,
    aggregate_version,
    after_on_hand_quantity AS on_hand_quantity,
    after_reserved_quantity AS reserved_quantity,
    after_available_quantity AS available_quantity,
    occurred_at AS last_occurred_at,
    recorded_at AS last_recorded_at
FROM (
    SELECT movement.*,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, balance_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS version_rank
    FROM yshopping_dwd.dwd_canonical_inventory_movement movement
) ranked
WHERE version_rank = 1;
