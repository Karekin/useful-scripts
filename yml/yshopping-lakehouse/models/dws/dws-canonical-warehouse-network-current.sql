CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_warehouse_network_current AS
SELECT
    warehouse.tenant_id,
    warehouse.warehouse_id,
    warehouse.warehouse_code,
    warehouse.warehouse_name,
    warehouse.warehouse_type,
    warehouse.current_status AS warehouse_status,
    COALESCE(zone.zone_count, 0) AS zone_count,
    COALESCE(zone.active_zone_count, 0) AS active_zone_count,
    COALESCE(location.location_count, 0) AS location_count,
    COALESCE(location.active_location_count, 0) AS active_location_count,
    COALESCE(mapping.active_mapping_count, 0) AS active_mapping_count,
    COALESCE(operator.active_operator_count, 0) AS active_operator_count,
    GREATEST(
        warehouse.recorded_at,
        COALESCE(zone.zone_freshness_at, warehouse.recorded_at),
        COALESCE(location.location_freshness_at, warehouse.recorded_at),
        COALESCE(mapping.mapping_freshness_at, warehouse.recorded_at),
        COALESCE(operator.operator_freshness_at, warehouse.recorded_at)
    ) AS data_freshness_at
FROM yshopping_dim.dim_canonical_warehouse_current warehouse
LEFT JOIN (
    SELECT tenant_id, warehouse_id, COUNT(*) AS zone_count,
           COUNT(IF(current_status='ACTIVE', 1, NULL)) AS active_zone_count,
           MAX(recorded_at) AS zone_freshness_at
    FROM yshopping_dim.dim_canonical_warehouse_zone_current
    GROUP BY tenant_id, warehouse_id
) zone ON zone.tenant_id=warehouse.tenant_id AND zone.warehouse_id=warehouse.warehouse_id
LEFT JOIN (
    SELECT tenant_id, warehouse_id, COUNT(*) AS location_count,
           COUNT(IF(current_status='ACTIVE', 1, NULL)) AS active_location_count,
           MAX(recorded_at) AS location_freshness_at
    FROM yshopping_dim.dim_canonical_warehouse_location_current
    GROUP BY tenant_id, warehouse_id
) location ON location.tenant_id=warehouse.tenant_id AND location.warehouse_id=warehouse.warehouse_id
LEFT JOIN (
    SELECT latest.tenant_id, attributes.warehouse_id,
           COUNT(IF(latest.current_status='ACTIVE', 1, NULL)) AS active_mapping_count,
           MAX(latest.recorded_at) AS mapping_freshness_at
    FROM (
        SELECT ranked.* FROM (
            SELECT event.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY tenant_id, mapping_id
                       ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
                   ) AS row_num
            FROM yshopping_dwd.dwd_canonical_warehouse_source_mapping_event event
        ) ranked WHERE row_num=1
    ) latest
    JOIN (
        SELECT tenant_id, mapping_id, MAX(warehouse_id) AS warehouse_id
        FROM yshopping_dwd.dwd_canonical_warehouse_source_mapping_event
        GROUP BY tenant_id, mapping_id
    ) attributes ON attributes.tenant_id=latest.tenant_id AND attributes.mapping_id=latest.mapping_id
    GROUP BY latest.tenant_id, attributes.warehouse_id
) mapping ON mapping.tenant_id=warehouse.tenant_id AND mapping.warehouse_id=warehouse.warehouse_id
LEFT JOIN (
    SELECT tenant_id, warehouse_id,
           COUNT(IF(current_status='ACTIVE', 1, NULL)) AS active_operator_count,
           MAX(recorded_at) AS operator_freshness_at
    FROM (
        SELECT ranked.* FROM (
            SELECT event.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY tenant_id, assignment_id
                       ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
                   ) AS row_num
            FROM yshopping_dwd.dwd_canonical_warehouse_operator_assignment_event event
        ) ranked WHERE row_num=1
    ) latest_operator
    GROUP BY tenant_id, warehouse_id
) operator ON operator.tenant_id=warehouse.tenant_id AND operator.warehouse_id=warehouse.warehouse_id;
