CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_catalog_style_current AS
SELECT
    tenant_id,
    canonical_style_id,
    MAX(style_code) AS style_code,
    MAX(style_name) AS style_name,
    MAX(brand_ref) AS brand_ref,
    MAX(planning_category_ref) AS planning_category_ref,
    MAX(planning_year) AS planning_year,
    MAX(season_code) AS season_code,
    MAX(wave_code) AS wave_code,
    MAX(style_status) AS style_status,
    MAX(spu_status) AS spu_status,
    COUNT(DISTINCT canonical_spu_id) AS spu_count,
    COUNT(DISTINCT canonical_sku_id) AS sku_count,
    COUNT(DISTINCT IF(catalog_status = 'ACTIVE', canonical_sku_id, NULL)) AS active_sku_count,
    COUNT(DISTINCT color_id) AS color_count,
    COUNT(DISTINCT size_id) AS size_count,
    MAX(recorded_at) AS data_freshness_at
FROM yshopping_dim.dim_canonical_catalog_sku_current
GROUP BY tenant_id, canonical_style_id;
