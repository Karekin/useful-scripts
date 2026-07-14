SELECT 'canonical_catalog_required_fields' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_catalog_sku_snapshot
WHERE canonical_style_id IS NULL OR canonical_style_id = ''
   OR canonical_spu_id IS NULL OR canonical_spu_id = ''
   OR canonical_sku_id IS NULL OR canonical_sku_id = ''
   OR style_code IS NULL OR style_code = '' OR spu_code IS NULL OR spu_code = ''
   OR sku_code IS NULL OR sku_code = '' OR color_code IS NULL OR color_code = ''
   OR size_group_code IS NULL OR size_group_code = '' OR size_code IS NULL OR size_code = ''
   OR primary_barcode IS NULL OR primary_barcode = '' OR base_uom_code <> 'PCS'
UNION ALL
SELECT 'canonical_catalog_aggregate_version_unique', COUNT(*)
FROM (
    SELECT tenant_id, canonical_sku_id, aggregate_version
    FROM yshopping_dwd.dwd_canonical_catalog_sku_snapshot
    GROUP BY tenant_id, canonical_sku_id, aggregate_version
    HAVING COUNT(*) > 1
) duplicate
UNION ALL
SELECT 'canonical_catalog_business_code_unique', COUNT(*)
FROM (
    SELECT tenant_id, sku_code
    FROM yshopping_dim.dim_canonical_catalog_sku_current
    GROUP BY tenant_id, sku_code
    HAVING COUNT(*) > 1
) duplicate
UNION ALL
SELECT 'canonical_catalog_variant_unique', COUNT(*)
FROM (
    SELECT tenant_id, canonical_spu_id, variant_key_hash
    FROM yshopping_dim.dim_canonical_catalog_sku_current
    GROUP BY tenant_id, canonical_spu_id, variant_key_hash
    HAVING COUNT(*) > 1
) duplicate
UNION ALL
SELECT 'canonical_catalog_active_hierarchy', COUNT(*)
FROM yshopping_dim.dim_canonical_catalog_sku_current
WHERE catalog_status = 'ACTIVE' AND (style_status <> 'ACTIVE' OR spu_status NOT IN ('APPROVED', 'ACTIVE'))
UNION ALL
SELECT 'canonical_catalog_status_event_version', COUNT(*)
FROM yshopping_dwd.dwd_canonical_catalog_status_change
WHERE aggregate_version < 2 OR entity_id IS NULL OR entity_id = '' OR current_status IS NULL;
