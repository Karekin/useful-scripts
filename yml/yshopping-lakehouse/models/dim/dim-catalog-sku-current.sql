-- Legacy Mall compatibility read model. Do not use its synthesized IDs or stock
-- as canonical Catalog/Inventory authority; use dim_canonical_catalog_sku_current
-- and dws_canonical_inventory_balance_current for new consumers.
CREATE OR REPLACE VIEW yshopping_dim.dim_catalog_sku_current AS
SELECT
    'yudao-mall' AS source_system,
    sku.tenant_id,
    sku.id AS source_id,
    CONCAT('yudao-mall:', CAST(sku.tenant_id AS STRING), ':sku:', CAST(sku.id AS STRING)) AS canonical_sku_id,
    spu.id AS canonical_spu_id,
    spu.name AS product_name,
    sku.bar_code,
    sku.properties AS variant_properties_json,
    spu.category_id,
    category.name AS category_name,
    spu.brand_id,
    brand.name AS brand_name,
    spu.status AS product_status,
    sku.price AS sale_price_amount_minor,
    sku.market_price AS market_price_amount_minor,
    sku.cost_price AS cost_price_amount_minor,
    'CNY' AS currency,
    sku.stock AS legacy_sellable_stock_quantity,
    sku.weight AS weight_grams,
    sku.volume AS volume_cm3,
    sku.pic_url,
    sku.create_time AS recorded_at,
    GREATEST(sku.update_time, spu.update_time) AS updated_at,
    sku.deleted AS source_deleted
FROM yshopping_ods.product_sku sku
JOIN yshopping_ods.product_spu spu
  ON spu.tenant_id = sku.tenant_id AND spu.id = sku.spu_id AND spu.deleted = FALSE
LEFT JOIN yshopping_ods.product_category category
  ON category.tenant_id = spu.tenant_id AND category.id = spu.category_id AND category.deleted = FALSE
LEFT JOIN yshopping_ods.product_brand brand
  ON brand.tenant_id = spu.tenant_id AND brand.id = spu.brand_id AND brand.deleted = FALSE
WHERE sku.deleted = FALSE;
