SELECT 'catalog_sku_authority' AS check_name, COUNT(*) AS violations
FROM (
  SELECT tenant_id, canonical_sku_id
  FROM yshopping_dim.dim_catalog_sku_current
  GROUP BY tenant_id, canonical_sku_id
  HAVING COUNT(*) > 1
) duplicates
UNION ALL
SELECT 'catalog_sku_parent_relation', COUNT(*)
FROM yshopping_ods.product_sku sku
LEFT JOIN yshopping_ods.product_spu spu
  ON spu.tenant_id = sku.tenant_id AND spu.id = sku.spu_id AND spu.deleted = FALSE
WHERE sku.deleted = FALSE AND spu.id IS NULL;
