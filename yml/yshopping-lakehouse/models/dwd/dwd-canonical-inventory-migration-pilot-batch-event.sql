CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_inventory_migration_pilot_batch_event AS
SELECT
    event_id,
    tenant_id,
    aggregate_id AS pilot_batch_id,
    aggregate_version AS batch_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.pilot_batch_id') AS payload_pilot_batch_id,
    get_json_string(payload, '$.migration_run_id') AS migration_run_id,
    get_json_string(payload, '$.environment') AS environment,
    get_json_string(payload, '$.environment_fingerprint') AS environment_fingerprint,
    get_json_string(payload, '$.source_system') AS migration_source_system,
    get_json_string(payload, '$.source_type') AS migration_source_type,
    get_json_string(payload, '$.source_classification') AS source_classification,
    get_json_string(payload, '$.manifest_hash') AS manifest_hash,
    get_json_string(payload, '$.policy_version') AS policy_version,
    get_json_string(payload, '$.policy_hash') AS policy_hash,
    CAST(get_json_string(payload, '$.expected_item_count') AS BIGINT) AS expected_item_count,
    CAST(get_json_string(payload, '$.expected_on_hand_quantity') AS DECIMAL(24,6)) AS expected_on_hand_quantity,
    CAST(get_json_string(payload, '$.approved_item_count') AS BIGINT) AS approved_item_count,
    CAST(get_json_string(payload, '$.approved_on_hand_quantity') AS DECIMAL(24,6)) AS approved_on_hand_quantity,
    CAST(get_json_string(payload, '$.admitted_item_count') AS BIGINT) AS admitted_item_count,
    CAST(get_json_string(payload, '$.admitted_on_hand_quantity') AS DECIMAL(24,6)) AS admitted_on_hand_quantity,
    CAST(get_json_string(payload, '$.approval_count') AS BIGINT) AS approval_count,
    get_json_string(payload, '$.approval_roles') AS approval_roles_json,
    CAST(get_json_string(payload, '$.requester_system_user_id') AS BIGINT) AS requester_system_user_id,
    get_json_string(payload, '$.approver_system_user_ids') AS approver_system_user_ids_json,
    CAST(get_json_string(payload, '$.approver_system_user_ids[0]') AS BIGINT) AS first_approver_system_user_id,
    CAST(get_json_string(payload, '$.approver_system_user_ids[1]') AS BIGINT) AS second_approver_system_user_id,
    CAST(get_json_string(payload, '$.executor_system_user_id') AS BIGINT) AS executor_system_user_id,
    get_json_string(payload, '$.warehouse_id') AS warehouse_id,
    get_json_string(payload, '$.base_uom_code') AS base_uom_code,
    get_json_string(payload, '$.source_watermark_kind') AS source_watermark_kind,
    get_json_string(payload, '$.source_watermark_value') AS source_watermark_value,
    CAST(REPLACE(SUBSTR(get_json_string(payload, '$.source_watermark_captured_at'),1,19),'T',' ') AS DATETIME)
      AS source_watermark_captured_at,
    get_json_string(payload, '$.target_watermark_kind') AS target_watermark_kind,
    get_json_string(payload, '$.target_watermark_value') AS target_watermark_value,
    CAST(REPLACE(SUBSTR(get_json_string(payload, '$.target_watermark_applied_at'),1,19),'T',' ') AS DATETIME)
      AS target_watermark_applied_at,
    CAST(get_json_string(payload, '$.max_lag_seconds') AS BIGINT) AS max_lag_seconds,
    CAST(REPLACE(SUBSTR(get_json_string(payload, '$.execution_window_start'),1,19),'T',' ') AS DATETIME)
      AS execution_window_start,
    CAST(REPLACE(SUBSTR(get_json_string(payload, '$.execution_window_end'),1,19),'T',' ') AS DATETIME)
      AS execution_window_end,
    get_json_string(payload, '$.batch_status') AS batch_status,
    CAST(get_json_string(payload, '$.execution_available') AS BOOLEAN) AS execution_available,
    CAST(get_json_string(payload, '$.cutover_ready') AS BOOLEAN) AS cutover_ready
FROM yshopping_dwd.dwd_domain_event
WHERE event_type='inventory.migration.pilot_batch_status_changed'
  AND schema_version=1
  AND source_system='cloudmold-inventory'
  AND aggregate_type='inventory_migration_pilot_batch';
