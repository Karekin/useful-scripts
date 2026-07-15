CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_warehouse_current AS
SELECT
    current.event_id, current.tenant_id, current.warehouse_id,
    attributes.warehouse_code, attributes.entity_name AS warehouse_name, attributes.warehouse_type,
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
        WHERE entity_type = 'WAREHOUSE'
    ) ranked WHERE row_num = 1
) current
JOIN (
    SELECT tenant_id, warehouse_id,
           MAX(warehouse_code) AS warehouse_code,
           MAX(entity_name) AS entity_name,
           MAX(warehouse_type) AS warehouse_type
    FROM yshopping_dwd.dwd_canonical_warehouse_entity_status_event
    WHERE entity_type = 'WAREHOUSE'
    GROUP BY tenant_id, warehouse_id
) attributes ON attributes.tenant_id=current.tenant_id AND attributes.warehouse_id=current.warehouse_id;
