CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_payment_current AS
SELECT
    event_id, schema_version, tenant_id, payment_id, payment_no, order_id, run_id, aggregate_version,
    transaction_id, transaction_type, previous_status, current_status,
    payable_amount_minor, captured_amount_minor, refunded_amount_minor,
    refund_amount_minor, remaining_refundable_amount_minor, currency_code,
    provider_code, provider_transaction_id, test_mode, reason, cancellation_saga_id,
    step_ordinal, correlation_id,
    occurred_at, recorded_at, payment_event_count
FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id, payment_id) AS payment_event_count,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, payment_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_payment_status_event event
) ranked
WHERE row_num = 1;
