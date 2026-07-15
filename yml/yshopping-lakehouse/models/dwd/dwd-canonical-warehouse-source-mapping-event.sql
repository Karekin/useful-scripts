CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_warehouse_source_mapping_event AS
SELECT
    event_id, tenant_id, aggregate_id AS mapping_id, aggregate_version,
    occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
    get_json_string(payload, '$.source_system') AS mapping_source_system,
    get_json_string(payload, '$.source_type') AS source_type,
    get_json_string(payload, '$.source_id') AS source_id,
    get_json_string(payload, '$.canonical_type') AS canonical_type,
    get_json_string(payload, '$.canonical_id') AS canonical_id,
    get_json_string(payload, '$.warehouse_id') AS warehouse_id,
    get_json_string(payload, '$.zone_id') AS zone_id,
    get_json_string(payload, '$.location_id') AS location_id,
    get_json_string(payload, '$.current_status') AS current_status
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'warehouse.source_mapping.changed'
  AND schema_version = 1
  AND source_system = 'cloudmold-warehouse';
