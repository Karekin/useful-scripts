CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_warehouse_entity_status_event AS
SELECT
    event_id, tenant_id, aggregate_type, aggregate_id AS entity_id, aggregate_version,
    occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
    get_json_string(payload, '$.entity_type') AS entity_type,
    get_json_string(payload, '$.warehouse_id') AS warehouse_id,
    get_json_string(payload, '$.warehouse_code') AS warehouse_code,
    get_json_string(payload, '$.name') AS entity_name,
    get_json_string(payload, '$.warehouse_type') AS warehouse_type,
    get_json_string(payload, '$.zone_id') AS zone_id,
    get_json_string(payload, '$.zone_code') AS zone_code,
    get_json_string(payload, '$.zone_type') AS zone_type,
    get_json_string(payload, '$.location_id') AS location_id,
    get_json_string(payload, '$.location_code') AS location_code,
    get_json_string(payload, '$.location_type') AS location_type,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'warehouse.entity.status_changed'
  AND schema_version = 1
  AND source_system = 'cloudmold-warehouse';
