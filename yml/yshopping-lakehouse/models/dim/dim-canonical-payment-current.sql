CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_payment_current AS
SELECT
    ranked.event_id, ranked.schema_version, ranked.tenant_id, ranked.payment_id, ranked.payment_no,
    ranked.order_id, COALESCE(order_payment.run_id, ranked.run_id) AS run_id, ranked.aggregate_version,
    ranked.transaction_id, ranked.transaction_type, ranked.previous_status, ranked.current_status,
    ranked.payable_amount_minor, ranked.captured_amount_minor, ranked.refunded_amount_minor,
    ranked.refund_amount_minor, ranked.remaining_refundable_amount_minor, ranked.currency_code,
    ranked.provider_code, ranked.provider_transaction_id, ranked.test_mode, ranked.reason,
    ranked.cancellation_saga_id, ranked.step_ordinal, ranked.correlation_id,
    ranked.occurred_at, ranked.recorded_at, ranked.payment_event_count
FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id, payment_id) AS payment_event_count,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, payment_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_payment_status_event event
) ranked
LEFT JOIN (
    SELECT tenant_id, order_id, payment_id, run_id
    FROM (
        SELECT event.*,
               ROW_NUMBER() OVER (
                   PARTITION BY tenant_id, order_id, payment_id
                   ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
               ) AS row_num
        FROM yshopping_dwd.dwd_canonical_order_status_event event
        WHERE current_status = 'PAYMENT_CONFIRMED'
    ) payment_confirmation
    WHERE row_num = 1
) order_payment
  ON order_payment.tenant_id = ranked.tenant_id
 AND order_payment.order_id = ranked.order_id
 AND order_payment.payment_id = ranked.payment_id
WHERE ranked.row_num = 1;
