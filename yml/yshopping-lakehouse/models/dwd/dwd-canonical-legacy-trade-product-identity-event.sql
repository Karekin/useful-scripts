CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_legacy_trade_product_identity_event AS
SELECT
    event_id,
    schema_version,
    tenant_id,
    aggregate_id AS identity_item_id,
    aggregate_version AS identity_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.identity_run_id') AS identity_run_id,
    get_json_string(payload, '$.source_migration_run_id') AS source_migration_run_id,
    get_json_string(payload, '$.identity_item_id') AS payload_identity_item_id,
    get_json_string(payload, '$.candidate_id') AS candidate_id,
    get_json_string(payload, '$.item_evidence_id') AS item_evidence_id,
    CAST(get_json_string(payload, '$.legacy_order_id') AS BIGINT) AS legacy_order_id,
    CAST(get_json_string(payload, '$.legacy_order_item_id') AS BIGINT) AS legacy_order_item_id,
    CAST(get_json_string(payload, '$.legacy_spu_id') AS BIGINT) AS legacy_spu_id,
    CAST(get_json_string(payload, '$.legacy_sku_id') AS BIGINT) AS legacy_sku_id,
    get_json_string(payload, '$.source_item_evidence_hash') AS source_item_evidence_hash,
    CAST(get_json_string(payload, '$.source_parent_cardinality') AS BIGINT) AS source_parent_cardinality,
    get_json_string(payload, '$.source_pair_status') AS source_pair_status,
    get_json_string(payload, '$.current_reference_status') AS current_reference_status,
    get_json_string(payload, '$.current_product_snapshot_hash') AS current_product_snapshot_hash,
    get_json_string(payload, '$.qualification_id') AS qualification_id,
    get_json_string(payload, '$.historical_identity_status') AS historical_identity_status,
    json_query(payload, '$.blocker_codes') AS blocker_codes,
    CAST(get_json_string(payload, '$.identity_admission_allowed') AS BOOLEAN) AS identity_admission_allowed,
    CAST(get_json_string(payload, '$.target_mapping_allowed') AS BOOLEAN) AS target_mapping_allowed,
    get_json_string(payload, '$.evidence_hash') AS evidence_hash,
    CAST(get_json_string(payload, '$.run_source_item_count') AS BIGINT) AS run_source_item_count,
    CAST(get_json_string(payload, '$.run_active_item_count') AS BIGINT) AS run_active_item_count,
    CAST(get_json_string(payload, '$.run_source_pair_unambiguous_count') AS BIGINT)
        AS run_source_pair_unambiguous_count,
    CAST(get_json_string(payload, '$.run_source_parent_conflict_item_count') AS BIGINT)
        AS run_source_parent_conflict_item_count,
    CAST(get_json_string(payload, '$.run_current_relation_observed_count') AS BIGINT)
        AS run_current_relation_observed_count,
    CAST(get_json_string(payload, '$.run_historical_identity_qualified_count') AS BIGINT)
        AS run_historical_identity_qualified_count,
    CAST(get_json_string(payload, '$.run_identity_admitted_item_count') AS BIGINT)
        AS run_identity_admitted_item_count,
    CAST(get_json_string(payload, '$.target_mapping_enabled') AS BOOLEAN) AS target_mapping_enabled,
    get_json_string(payload, '$.run_status') AS run_status,
    get_json_string(payload, '$.governance_evidence_hash') AS governance_evidence_hash,
    get_json_string(payload, '$.policy_version') AS policy_version,
    get_json_string(payload, '$.verification_ref') AS verification_ref,
    CAST(REPLACE(SUBSTR(get_json_string(payload, '$.assessed_at'), 1, 19), 'T', ' ') AS DATETIME) AS assessed_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'order.migration.legacy_trade_product_identity_assessed'
  AND schema_version = 1
  AND source_system = 'cloudmold-order'
  AND aggregate_type = 'legacy_trade_product_identity';
