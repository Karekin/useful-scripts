CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_order_after_sale_settlement_event AS
SELECT
    event_id, schema_version, tenant_id, aggregate_id AS aggregate_order_id, aggregate_version,
    occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.settlement_effect_id') AS settlement_effect_id,
    get_json_string(payload, '$.after_sale_id') AS after_sale_id,
    get_json_string(payload, '$.after_sale_item_id') AS after_sale_item_id,
    get_json_string(payload, '$.order_id') AS order_id,
    get_json_string(payload, '$.order_item_id') AS order_item_id,
    CAST(get_json_string(payload, '$.quantity') AS DECIMAL(24,6)) AS quantity,
    CAST(get_json_string(payload, '$.gross_amount_minor') AS BIGINT) AS gross_amount_minor,
    CAST(get_json_string(payload, '$.benefit_amount_minor') AS BIGINT) AS benefit_amount_minor,
    CAST(get_json_string(payload, '$.net_amount_minor') AS BIGINT) AS net_amount_minor,
    CAST(get_json_string(payload, '$.inventory_operation_id') AS BIGINT) AS inventory_operation_id,
    CAST(get_json_string(payload, '$.inventory_ledger_transaction_id') AS BIGINT)
        AS inventory_ledger_transaction_id,
    CAST(get_json_string(payload, '$.payment_refund_transaction_id') AS BIGINT)
        AS payment_refund_transaction_id,
    get_json_string(payload, '$.benefit_reversal_batch_id') AS benefit_reversal_batch_id,
    CAST(get_json_string(payload, '$.item_returned_quantity') AS DECIMAL(24,6)) AS item_returned_quantity,
    CAST(get_json_string(payload, '$.item_ordered_quantity') AS DECIMAL(24,6)) AS item_ordered_quantity,
    CAST(get_json_string(payload, '$.order_returned_quantity') AS DECIMAL(24,6)) AS order_returned_quantity,
    CAST(get_json_string(payload, '$.order_total_quantity') AS DECIMAL(24,6)) AS order_total_quantity,
    CAST(get_json_string(payload, '$.refunded_net_amount_minor') AS BIGINT) AS refunded_net_amount_minor,
    CAST(get_json_string(payload, '$.reversed_benefit_amount_minor') AS BIGINT)
        AS reversed_benefit_amount_minor,
    get_json_string(payload, '$.settlement_status') AS settlement_status,
    get_json_bool(payload, '$.full_return') AS full_return
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'order.after_sale_settlement.recorded'
  AND schema_version = 1
  AND source_system = 'cloudmold-order';
