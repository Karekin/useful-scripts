CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_warehouse_location_current AS
SELECT
    current.event_id, current.tenant_id, current.location_id, current.warehouse_id, current.zone_id,
    attributes.location_code, attributes.location_type,
    current.previous_status, current.current_status, current.aggregate_version,
    current.occurred_at, current.recorded_at, current.correlation_id, current.entity_event_count
FROM (
    SELECT ranked.* FROM (
        SELECT event.*,
               COUNT(*) OVER (PARTITION BY tenant_id, entity_id) AS entity_event_count,
               ROW_NUMBER() OVER (
                   PARTITION BY tenant_id, entity_id
                   ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
               ) AS row_num
        FROM yshopping_dwd.dwd_canonical_warehouse_entity_status_event event
        WHERE entity_type = 'LOCATION'
    ) ranked WHERE row_num = 1
) current
JOIN (
    SELECT tenant_id, location_id,
           MAX(location_code) AS location_code,
           MAX(location_type) AS location_type
    FROM yshopping_dwd.dwd_canonical_warehouse_entity_status_event
    WHERE entity_type = 'LOCATION'
    GROUP BY tenant_id, location_id
) attributes ON attributes.tenant_id=current.tenant_id AND attributes.location_id=current.location_id;
