CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_inventory_migration_shadow_round_event AS
SELECT
    event_id,tenant_id,aggregate_id AS shadow_round_id,aggregate_version AS round_version,
    occurred_at,recorded_at,correlation_id,causation_id,idempotency_key,
    get_json_string(payload,'$.shadow_window_id') AS shadow_window_id,
    get_json_string(payload,'$.pilot_batch_id') AS pilot_batch_id,
    get_json_string(payload,'$.manifest_hash') AS manifest_hash,
    get_json_string(payload,'$.expected_item_set_hash') AS expected_item_set_hash,
    CAST(get_json_string(payload,'$.round_sequence') AS BIGINT) AS round_sequence,
    CAST(get_json_string(payload,'$.expected_item_count') AS BIGINT) AS expected_item_count,
    CAST(get_json_string(payload,'$.observed_item_count') AS BIGINT) AS reported_observed_item_count,
    CAST(get_json_string(payload,'$.match_item_count') AS BIGINT) AS reported_match_item_count,
    CAST(get_json_string(payload,'$.different_item_count') AS BIGINT) AS reported_different_item_count,
    CAST(get_json_string(payload,'$.uncomparable_item_count') AS BIGINT) AS reported_uncomparable_item_count,
    get_json_string(payload,'$.watermark_kind') AS watermark_kind,
    get_json_string(payload,'$.previous_source_gtid_set') AS previous_source_gtid_set,
    get_json_string(payload,'$.source_gtid_set') AS source_gtid_set,
    get_json_string(payload,'$.previous_target_gtid_set') AS previous_target_gtid_set,
    get_json_string(payload,'$.target_gtid_set') AS target_gtid_set,
    CAST(REPLACE(SUBSTR(get_json_string(payload,'$.source_watermark_captured_at'),1,19),'T',' ') AS DATETIME) AS source_watermark_captured_at,
    CAST(REPLACE(SUBSTR(get_json_string(payload,'$.target_watermark_applied_at'),1,19),'T',' ') AS DATETIME) AS target_watermark_applied_at,
    CAST(get_json_string(payload,'$.source_monotonic') AS BOOLEAN) AS source_monotonic,
    CAST(get_json_string(payload,'$.target_monotonic') AS BOOLEAN) AS target_monotonic,
    CAST(get_json_string(payload,'$.target_contains_source') AS BOOLEAN) AS target_contains_source,
    get_json_string(payload,'$.gtid_validator_version') AS gtid_validator_version,
    get_json_string(payload,'$.gtid_evidence_hash') AS gtid_evidence_hash,
    CAST(get_json_string(payload,'$.lag_seconds') AS BIGINT) AS reported_lag_seconds,
    CAST(REPLACE(SUBSTR(get_json_string(payload,'$.round_started_at'),1,19),'T',' ') AS DATETIME) AS round_started_at,
    CAST(REPLACE(SUBSTR(get_json_string(payload,'$.round_completed_at'),1,19),'T',' ') AS DATETIME) AS round_completed_at,
    get_json_string(payload,'$.round_status') AS round_status,
    get_json_string(payload,'$.round_result') AS round_result,
    CAST(get_json_string(payload,'$.execution_available') AS BOOLEAN) AS execution_available,
    CAST(get_json_string(payload,'$.cutover_ready') AS BOOLEAN) AS cutover_ready
FROM yshopping_dwd.dwd_domain_event
WHERE event_type='inventory.migration.shadow_round_completed'
  AND schema_version=1 AND source_system='cloudmold-inventory'
  AND aggregate_type='inventory_migration_shadow_round';
