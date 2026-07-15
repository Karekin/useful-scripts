CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_inventory_migration_shadow_window_event AS
SELECT
    event_id,tenant_id,aggregate_id AS shadow_window_id,aggregate_version AS window_version,
    occurred_at,recorded_at,correlation_id,causation_id,idempotency_key,
    get_json_string(payload,'$.pilot_batch_id') AS pilot_batch_id,
    get_json_string(payload,'$.migration_run_id') AS migration_run_id,
    get_json_string(payload,'$.admission_event_id') AS admission_event_id,
    get_json_string(payload,'$.manifest_hash') AS manifest_hash,
    get_json_string(payload,'$.expected_item_set_hash') AS expected_item_set_hash,
    get_json_string(payload,'$.environment') AS environment,
    get_json_string(payload,'$.environment_fingerprint') AS environment_fingerprint,
    get_json_string(payload,'$.policy_version') AS policy_version,
    get_json_string(payload,'$.policy_hash') AS policy_hash,
    CAST(get_json_string(payload,'$.expected_item_count') AS BIGINT) AS expected_item_count,
    get_json_string(payload,'$.target_projection_kind') AS target_projection_kind,
    CAST(get_json_string(payload,'$.target_materialized') AS BOOLEAN) AS target_materialized,
    get_json_string(payload,'$.watermark_kind') AS watermark_kind,
    CAST(get_json_string(payload,'$.required_round_count') AS BIGINT) AS required_round_count,
    CAST(get_json_string(payload,'$.required_duration_seconds') AS BIGINT) AS required_duration_seconds,
    CAST(get_json_string(payload,'$.max_round_gap_seconds') AS BIGINT) AS max_round_gap_seconds,
    CAST(get_json_string(payload,'$.max_lag_seconds') AS BIGINT) AS max_lag_seconds,
    CAST(REPLACE(SUBSTR(get_json_string(payload,'$.window_started_at'),1,19),'T',' ') AS DATETIME) AS window_started_at,
    CAST(REPLACE(SUBSTR(get_json_string(payload,'$.window_verified_at'),1,19),'T',' ') AS DATETIME) AS window_verified_at,
    get_json_string(payload,'$.window_status') AS window_status,
    get_json_string(payload,'$.verification_result') AS verification_result,
    get_json_string(payload,'$.gtid_validator_version') AS gtid_validator_version,
    get_json_string(payload,'$.collector_artifact_hash') AS collector_artifact_hash,
    CAST(get_json_string(payload,'$.execution_available') AS BOOLEAN) AS execution_available,
    CAST(get_json_string(payload,'$.cutover_ready') AS BOOLEAN) AS cutover_ready
FROM yshopping_dwd.dwd_domain_event
WHERE event_type='inventory.migration.shadow_window_status_changed'
  AND schema_version=1 AND source_system='cloudmold-inventory'
  AND aggregate_type='inventory_migration_shadow_window';
