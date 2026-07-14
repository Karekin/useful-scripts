CREATE OR REPLACE VIEW yshopping_dim.dim_erp_product_current AS
SELECT
    'yudao-erp' AS source_system,
    p.tenant_id,
    p.id AS source_id,
    p.id AS erp_product_id,
    p.bar_code,
    p.name AS product_name,
    p.standard,
    p.category_id,
    c.code AS category_code,
    c.name AS category_name,
    p.unit_id,
    u.name AS uom_name,
    p.purchase_price AS purchase_price_amount_yuan,
    p.sale_price AS sale_price_amount_yuan,
    p.min_price AS min_price_amount_yuan,
    p.status,
    p.create_time AS recorded_at,
    p.update_time AS updated_at,
    p.deleted AS source_deleted
FROM yshopping_ods.erp_product p
LEFT JOIN yshopping_ods.erp_product_category c
  ON c.tenant_id = p.tenant_id AND c.id = p.category_id AND c.deleted = FALSE
LEFT JOIN yshopping_ods.erp_product_unit u
  ON u.tenant_id = p.tenant_id AND u.id = p.unit_id AND u.deleted = FALSE
WHERE p.deleted = FALSE;
