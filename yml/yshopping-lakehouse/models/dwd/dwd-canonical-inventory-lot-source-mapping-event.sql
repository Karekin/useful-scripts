CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_inventory_lot_source_mapping_event AS
SELECT
    event_id,
    tenant_id,
    aggregate_id AS mapping_id,
    aggregate_version AS mapping_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.migration_run_id') AS migration_run_id,
    get_json_string(payload, '$.mapping_id') AS payload_mapping_id,
    get_json_string(payload, '$.mapping_source_system') AS mapping_source_system,
    get_json_string(payload, '$.source_type') AS source_type,
    get_json_string(payload, '$.source_id') AS source_id,
    get_json_string(payload, '$.lot_id') AS lot_id,
    COALESCE(
      CAST(REPLACE(SUBSTR(get_json_string(payload, '$.valid_from'), 1, 19), 'T', ' ') AS DATETIME),
      CAST(FROM_UNIXTIME(CAST(CAST(get_json_string(payload, '$.valid_from') AS BIGINT) / 1000 AS BIGINT)) AS DATETIME)
    ) AS valid_from,
    COALESCE(
      CAST(REPLACE(SUBSTR(get_json_string(payload, '$.valid_to'), 1, 19), 'T', ' ') AS DATETIME),
      CAST(FROM_UNIXTIME(CAST(CAST(get_json_string(payload, '$.valid_to') AS BIGINT) / 1000 AS BIGINT)) AS DATETIME)
    ) AS valid_to,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status,
    get_json_string(payload, '$.change_type') AS change_type,
    get_json_string(payload, '$.verification_ref') AS verification_ref,
    get_json_string(payload, '$.change_reason_code') AS change_reason_code
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'inventory.lot.source_mapping.changed'
  AND schema_version = 1
  AND source_system = 'cloudmold-inventory'
  AND aggregate_type = 'inventory_lot_source_mapping';
