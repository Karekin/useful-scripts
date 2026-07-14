CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_catalog_readiness AS
SELECT
    tenant_id,
    canonical_style_id,
    style_code,
    style_name,
    spu_count,
    sku_count,
    active_sku_count,
    color_count,
    size_count,
    CASE
        WHEN sku_count = 0 THEN 'MISSING_SKU'
        WHEN color_count = 0 OR size_count = 0 THEN 'MISSING_VARIANT_DIMENSION'
        WHEN style_status = 'ACTIVE' AND spu_status = 'ACTIVE' AND active_sku_count = sku_count
            THEN 'CATALOG_ACTIVE'
        ELSE 'CATALOG_DEFINED'
    END AS readiness_status,
    data_freshness_at
FROM yshopping_dws.dws_canonical_catalog_style_current;
