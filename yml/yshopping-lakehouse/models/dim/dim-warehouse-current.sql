CREATE OR REPLACE VIEW yshopping_dim.dim_warehouse_current AS
SELECT
    'yudao-erp' AS source_system,
    tenant_id,
    id AS source_id,
    id AS warehouse_id,
    name AS warehouse_name,
    address,
    principal,
    status,
    default_status,
    create_time AS recorded_at,
    update_time AS updated_at,
    deleted AS source_deleted
FROM yshopping_ods.erp_warehouse
WHERE deleted = FALSE;
