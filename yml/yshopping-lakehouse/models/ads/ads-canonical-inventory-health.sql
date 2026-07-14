CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_inventory_health AS
SELECT
    tenant_id,
    balance_id,
    canonical_sku_id,
    warehouse_id,
    owner_id,
    on_hand_quantity,
    reserved_quantity,
    available_quantity,
    aggregate_version,
    CASE
        WHEN on_hand_quantity < 0 OR reserved_quantity < 0 OR available_quantity < 0 THEN 'INVALID'
        WHEN available_quantity = 0 THEN 'OUT_OF_STOCK'
        WHEN available_quantity <= 5 THEN 'LOW_STOCK'
        ELSE 'HEALTHY'
    END AS health_status,
    last_recorded_at AS data_freshness_at
FROM yshopping_dws.dws_canonical_inventory_balance_current;
