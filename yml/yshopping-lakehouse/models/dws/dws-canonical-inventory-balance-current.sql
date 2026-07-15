CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_inventory_balance_current AS
SELECT
    tenant_id,
    balance_id,
    schema_version,
    canonical_sku_id,
    warehouse_id,
    location_id,
    lot_id,
    lot_code,
    legacy_lot_no,
    owner_type,
    owner_id,
    stock_status,
    quality_status,
    base_uom_code,
    aggregate_version,
    after_on_hand_quantity AS on_hand_quantity,
    after_reserved_quantity AS reserved_quantity,
    after_in_transit_quantity AS in_transit_quantity,
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
