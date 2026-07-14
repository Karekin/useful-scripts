CREATE OR REPLACE VIEW yshopping_dwd.dwd_inventory_movement AS
SELECT
    'yudao-erp' AS source_system,
    tenant_id,
    id AS inventory_movement_id,
    CONCAT('yudao-erp:', CAST(tenant_id AS STRING), ':erp_stock_record:', CAST(id AS STRING)) AS event_id,
    product_id,
    warehouse_id,
    count AS delta_quantity,
    total_count AS after_quantity,
    biz_type AS movement_type,
    biz_id,
    biz_item_id,
    biz_no,
    create_time AS occurred_at,
    create_time AS recorded_at,
    update_time AS updated_at,
    deleted AS source_deleted
FROM yshopping_ods.erp_stock_record
WHERE deleted = FALSE;
