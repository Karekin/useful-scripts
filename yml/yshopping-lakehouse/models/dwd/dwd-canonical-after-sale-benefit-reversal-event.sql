CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_after_sale_benefit_reversal_event AS
SELECT
    event_id, schema_version, tenant_id, aggregate_id AS benefit_reversal_id, aggregate_version,
    occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.reversal_batch_id') AS reversal_batch_id,
    get_json_string(payload, '$.benefit_reversal_id') AS payload_benefit_reversal_id,
    get_json_string(payload, '$.after_sale_id') AS after_sale_id,
    get_json_string(payload, '$.after_sale_item_id') AS after_sale_item_id,
    get_json_string(payload, '$.order_id') AS order_id,
    get_json_string(payload, '$.order_item_id') AS order_item_id,
    get_json_string(payload, '$.benefit_application_id') AS benefit_application_id,
    get_json_string(payload, '$.benefit_allocation_id') AS benefit_allocation_id,
    get_json_string(payload, '$.benefit_type') AS benefit_type,
    get_json_string(payload, '$.benefit_source_type') AS benefit_source_type,
    get_json_string(payload, '$.benefit_source_id') AS benefit_source_id,
    CAST(get_json_string(payload, '$.benefit_source_version') AS BIGINT) AS benefit_source_version,
    get_json_string(payload, '$.entitlement_id') AS entitlement_id,
    get_json_string(payload, '$.entitlement_effect_status') AS entitlement_effect_status,
    CAST(get_json_string(payload, '$.amount_minor') AS BIGINT) AS amount_minor,
    get_json_string(payload, '$.currency_code') AS currency_code,
    json_query(payload, '$.funding') AS funding
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'after_sale.benefit_reversal.recorded'
  AND schema_version = 1
  AND source_system = 'cloudmold-aftersales';
