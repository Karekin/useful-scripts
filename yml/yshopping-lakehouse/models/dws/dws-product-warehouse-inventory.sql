CREATE OR REPLACE VIEW yshopping_dws.dws_product_warehouse_inventory AS
SELECT
    s.tenant_id,
    s.product_id,
    s.warehouse_id,
    s.count AS on_hand_quantity,
    CAST(0 AS DECIMAL(24,6)) AS reserved_quantity,
    s.count AS available_quantity,
    COALESCE(m.ledger_quantity, 0) AS ledger_quantity,
    COALESCE(m.movement_count, 0) AS movement_count,
    m.last_movement_at,
    s.update_time AS updated_at
FROM yshopping_ods.erp_stock s
LEFT JOIN (
    SELECT tenant_id, product_id, warehouse_id,
           SUM(delta_quantity) AS ledger_quantity,
           COUNT(*) AS movement_count,
           MAX(occurred_at) AS last_movement_at
    FROM yshopping_dwd.dwd_inventory_movement
    GROUP BY tenant_id, product_id, warehouse_id
) m ON m.tenant_id = s.tenant_id AND m.product_id = s.product_id AND m.warehouse_id = s.warehouse_id
WHERE s.deleted = FALSE;
