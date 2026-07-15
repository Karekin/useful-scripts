CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_warehouse_network_readiness AS
SELECT
    tenant_id, warehouse_id, warehouse_code, warehouse_name, warehouse_type, warehouse_status,
    zone_count, active_zone_count, location_count, active_location_count,
    active_mapping_count, active_operator_count,
    CASE
        WHEN warehouse_status='ACTIVE'
         AND zone_count>0 AND active_zone_count=zone_count
         AND location_count>0 AND active_location_count=location_count
         AND active_mapping_count>0
         AND active_operator_count>0
        THEN 'WAREHOUSE_NETWORK_READY'
        ELSE 'IN_PROGRESS'
    END AS readiness_status,
    data_freshness_at
FROM yshopping_dws.dws_canonical_warehouse_network_current;
