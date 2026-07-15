CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_warehouse_zone_current AS
SELECT
    current.event_id, current.tenant_id, current.zone_id, current.warehouse_id,
    attributes.zone_code, attributes.zone_type,
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
        WHERE entity_type = 'ZONE'
    ) ranked WHERE row_num = 1
) current
JOIN (
    SELECT tenant_id, zone_id, MAX(zone_code) AS zone_code, MAX(zone_type) AS zone_type
    FROM yshopping_dwd.dwd_canonical_warehouse_entity_status_event
    WHERE entity_type = 'ZONE'
    GROUP BY tenant_id, zone_id
) attributes ON attributes.tenant_id=current.tenant_id AND attributes.zone_id=current.zone_id;
