CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_merchant_deposit_ledger_event AS
SELECT
    event_id,
    tenant_id,
    aggregate_id AS account_id,
    aggregate_version AS account_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.merchant_id') AS merchant_id,
    get_json_string(payload, '$.account_id') AS payload_account_id,
    get_json_string(payload, '$.ledger_entry_id') AS ledger_entry_id,
    get_json_string(payload, '$.entry_type') AS entry_type,
    CAST(get_json_string(payload, '$.amount_minor') AS BIGINT) AS amount_minor,
    get_json_string(payload, '$.currency') AS currency,
    CAST(get_json_string(payload, '$.held_delta_minor') AS BIGINT) AS held_delta_minor,
    CAST(get_json_string(payload, '$.frozen_delta_minor') AS BIGINT) AS frozen_delta_minor,
    CAST(get_json_string(payload, '$.held_before_minor') AS BIGINT) AS held_before_minor,
    CAST(get_json_string(payload, '$.held_after_minor') AS BIGINT) AS held_after_minor,
    CAST(get_json_string(payload, '$.frozen_before_minor') AS BIGINT) AS frozen_before_minor,
    CAST(get_json_string(payload, '$.frozen_after_minor') AS BIGINT) AS frozen_after_minor,
    CAST(get_json_string(payload, '$.required_before_minor') AS BIGINT) AS required_before_minor,
    CAST(get_json_string(payload, '$.required_after_minor') AS BIGINT) AS required_after_minor,
    CAST(get_json_string(payload, '$.paid_after_minor') AS BIGINT) AS paid_after_minor,
    CAST(get_json_string(payload, '$.deducted_after_minor') AS BIGINT) AS deducted_after_minor,
    get_json_string(payload, '$.previous_coverage_status') AS previous_coverage_status,
    get_json_string(payload, '$.current_coverage_status') AS current_coverage_status,
    get_json_string(payload, '$.previous_enforcement_status') AS previous_enforcement_status,
    get_json_string(payload, '$.current_enforcement_status') AS current_enforcement_status,
    get_json_string(payload, '$.policy_version') AS policy_version,
    get_json_string(payload, '$.business_reference') AS business_reference,
    get_json_string(payload, '$.reason_code') AS reason_code,
    get_json_string(payload, '$.evidence_ref') AS evidence_ref
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'merchant.deposit.ledger_posted'
  AND schema_version = 1
  AND source_system = 'cloudmold-merchant'
  AND aggregate_type = 'MERCHANT_DEPOSIT_ACCOUNT';
