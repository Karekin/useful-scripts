CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_catalog_sku_current AS
SELECT
    ranked.event_id, ranked.tenant_id, ranked.canonical_sku_id, ranked.aggregate_version,
    ranked.canonical_style_id, ranked.style_code, ranked.style_name, ranked.brand_ref, ranked.planning_category_ref,
    ranked.planning_year, ranked.season_code, ranked.wave_code, ranked.canonical_spu_id, ranked.spu_code, ranked.product_name,
    ranked.sales_category_ref, ranked.sku_code, ranked.variant_key, ranked.variant_key_hash, ranked.color_id, ranked.color_code,
    ranked.color_name, ranked.size_group_id, ranked.size_group_code, ranked.size_id, ranked.size_code, ranked.size_name,
    ranked.base_uom_code, ranked.primary_barcode,
    COALESCE(style_status.current_status, 'DRAFT') AS style_status,
    COALESCE(spu_status.current_status, 'DRAFT') AS spu_status,
    COALESCE(sku_status.current_status, ranked.catalog_status) AS catalog_status,
    ranked.correlation_id, ranked.occurred_at, ranked.recorded_at
FROM (
    SELECT snapshot.*,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, canonical_sku_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_catalog_sku_snapshot snapshot
) ranked
LEFT JOIN yshopping_dim.dim_canonical_catalog_entity_status_current style_status
  ON style_status.tenant_id = ranked.tenant_id
 AND style_status.entity_type = 'STYLE' AND style_status.entity_id = ranked.canonical_style_id
LEFT JOIN yshopping_dim.dim_canonical_catalog_entity_status_current spu_status
  ON spu_status.tenant_id = ranked.tenant_id
 AND spu_status.entity_type = 'SPU' AND spu_status.entity_id = ranked.canonical_spu_id
LEFT JOIN yshopping_dim.dim_canonical_catalog_entity_status_current sku_status
  ON sku_status.tenant_id = ranked.tenant_id
 AND sku_status.entity_type = 'SKU' AND sku_status.entity_id = ranked.canonical_sku_id
WHERE row_num = 1;
