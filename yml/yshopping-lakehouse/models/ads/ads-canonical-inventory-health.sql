CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_inventory_health AS
SELECT
    tenant_id,
    balance_id,
    schema_version,
    canonical_sku_id,
    warehouse_id,
    location_id,
    lot_id,
    lot_code,
    owner_type,
    owner_id,
    stock_status,
    quality_status,
    base_uom_code,
    on_hand_quantity,
    reserved_quantity,
    in_transit_quantity,
    available_quantity,
    aggregate_version,
    CASE
        WHEN on_hand_quantity < 0 OR reserved_quantity < 0
          OR COALESCE(in_transit_quantity, 0) < 0 OR available_quantity < 0 THEN 'INVALID'
        WHEN stock_status IS NOT NULL AND stock_status <> 'SELLABLE' THEN 'NON_SELLABLE'
        WHEN quality_status IS NOT NULL AND quality_status <> 'QUALIFIED' THEN 'NON_SELLABLE'
        WHEN available_quantity = 0 THEN 'OUT_OF_STOCK'
        WHEN available_quantity <= 5 THEN 'LOW_STOCK'
        ELSE 'HEALTHY'
    END AS health_status,
    CASE
        WHEN schema_version = 3 AND location_id IS NOT NULL
          AND (lot_id IS NULL OR lot_code IS NOT NULL) THEN 'CANONICAL_V3'
        ELSE 'LEGACY_UNRESOLVED'
    END AS dimension_resolution_status,
    last_recorded_at AS data_freshness_at
FROM yshopping_dws.dws_canonical_inventory_balance_current;
