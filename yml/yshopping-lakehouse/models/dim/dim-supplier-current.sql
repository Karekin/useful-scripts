CREATE OR REPLACE VIEW yshopping_dim.dim_supplier_current AS
SELECT
    'yudao-erp' AS source_system,
    tenant_id,
    id AS source_id,
    id AS supplier_id,
    name AS supplier_name,
    status,
    tax_percent,
    create_time AS recorded_at,
    update_time AS updated_at,
    deleted AS source_deleted
FROM yshopping_ods.erp_supplier
WHERE deleted = FALSE;
