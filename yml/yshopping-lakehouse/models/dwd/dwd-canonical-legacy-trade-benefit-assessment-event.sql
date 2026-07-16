CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_legacy_trade_benefit_assessment_event AS
SELECT
    event_id,
    schema_version,
    tenant_id,
    aggregate_id AS candidate_id,
    aggregate_version AS candidate_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.migration_run_id') AS migration_run_id,
    get_json_string(payload, '$.candidate_id') AS payload_candidate_id,
    get_json_string(payload, '$.source_scope') AS source_scope,
    CAST(get_json_string(payload, '$.legacy_order_id') AS BIGINT) AS legacy_order_id,
    get_json_string(payload, '$.legacy_order_no') AS legacy_order_no,
    CAST(REPLACE(SUBSTR(get_json_string(payload, '$.source_updated_at'), 1, 19), 'T', ' ') AS DATETIME)
        AS source_updated_at,
    get_json_string(payload, '$.source_snapshot_hash') AS source_snapshot_hash,
    CAST(get_json_string(payload, '$.is_deleted') AS BOOLEAN) AS is_deleted,
    CAST(get_json_string(payload, '$.header_quantity') AS BIGINT) AS header_quantity,
    CAST(get_json_string(payload, '$.item_row_count') AS BIGINT) AS item_row_count,
    CAST(get_json_string(payload, '$.item_quantity') AS BIGINT) AS item_quantity,
    CAST(get_json_string(payload, '$.header_gross_amount_minor') AS BIGINT) AS header_gross_amount_minor,
    CAST(get_json_string(payload, '$.header_benefit_amount_minor') AS BIGINT) AS header_benefit_amount_minor,
    CAST(get_json_string(payload, '$.header_pay_amount_minor') AS BIGINT) AS header_pay_amount_minor,
    CAST(get_json_string(payload, '$.item_gross_amount_minor') AS BIGINT) AS item_gross_amount_minor,
    CAST(get_json_string(payload, '$.item_benefit_amount_minor') AS BIGINT) AS item_benefit_amount_minor,
    CAST(get_json_string(payload, '$.item_pay_amount_minor') AS BIGINT) AS item_pay_amount_minor,
    CAST(get_json_string(payload, '$.negative_money') AS BOOLEAN) AS negative_money,
    CAST(get_json_string(payload, '$.header_money_mismatch') AS BOOLEAN) AS header_money_mismatch,
    CAST(get_json_string(payload, '$.header_item_mismatch') AS BOOLEAN) AS header_item_mismatch,
    CAST(get_json_string(payload, '$.invalid_item_money_count') AS BIGINT) AS invalid_item_money_count,
    get_json_string(payload, '$.assessment_status') AS assessment_status,
    json_query(payload, '$.blocker_codes') AS blocker_codes,
    CAST(get_json_string(payload, '$.canonical_import_allowed') AS BOOLEAN) AS canonical_import_allowed,
    json_query(payload, '$.components') AS components,
    get_json_string(payload, '$.policy_version') AS policy_version,
    get_json_string(payload, '$.verification_ref') AS verification_ref,
    CAST(REPLACE(SUBSTR(get_json_string(payload, '$.assessed_at'), 1, 19), 'T', ' ') AS DATETIME) AS assessed_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'order.migration.legacy_trade_benefit_assessed'
  AND schema_version = 1
  AND source_system = 'cloudmold-order'
  AND aggregate_type = 'legacy_trade_benefit_migration_assessment';
