CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_paid_order_cancellation_saga_readiness AS
SELECT
    saga.*,
    CASE
        WHEN cancellation_mode <> 'PAID_UNSHIPPED'
          OR declared_fulfillment_row_count <> declared_fulfillment_count
          OR declared_fulfillment_count <> expected_fulfillment_count
          OR matched_fulfillment_count <> expected_fulfillment_count
          OR exact_cancelled_fulfillment_count > expected_fulfillment_count
          OR shipment_fact_count <> 0 OR sale_shipment_fact_count <> 0
          OR declared_reservation_row_count <> declared_reservation_count
          OR declared_reservation_count <> expected_reservation_count
          OR matched_order_item_reservation_count <> expected_reservation_count
          OR exact_reservation_fact_count <> expected_reservation_count
          OR exact_release_fact_count > expected_reservation_count
          OR order_cancellation_saga_id IS NULL OR order_cancellation_saga_id <> saga_id
          OR order_cancellation_mode <> 'PAID_UNSHIPPED'
          OR order_payment_id IS NULL OR order_payment_id <> reported_payment_id
          OR order_fulfillment_id IS NULL OR order_fulfillment_id <> reported_fulfillment_id
          OR order_shipment_id IS NOT NULL
          OR payment_status IS NULL
          OR (payment_status = 'REFUNDED' AND (refund_saga_id IS NULL OR refund_saga_id <> saga_id))
        THEN 'INCONSISTENT'
        WHEN saga_status = 'COMPLETED'
         AND saga_event_count = 9
         AND step_ordinal = 5
         AND order_status = 'CANCELLED'
         AND order_previous_status = 'CANCELLATION_PENDING'
         AND order_pre_cancellation_status = 'PAYMENT_CONFIRMED'
         AND order_step_ordinal = 4
         AND order_event_count = 5
         AND order_fence_event_count = 1 AND order_cancel_event_count = 1
         AND order_cancel_idempotency_count = 1
         AND payment_status = 'REFUNDED'
         AND reported_payment_status = 'REFUNDED'
         AND capture_event_count = 1 AND refund_event_count = 1
         AND refund_step_ordinal = 2
         AND refund_transaction_id = reported_refund_transaction_id
         AND order_refund_id = CAST(refund_transaction_id AS VARCHAR)
         AND refund_idempotency_count = 1
         AND payable_amount_minor = captured_amount_minor
         AND captured_amount_minor = refunded_amount_minor
         AND order_currency_code = payment_currency_code
         AND declared_fulfillment_count = expected_fulfillment_count
         AND exact_cancelled_fulfillment_count = expected_fulfillment_count
         AND reported_cancelled_fulfillment_count = expected_fulfillment_count
         AND fulfillment_event_count = 3
         AND fulfillment_item_count = valid_fulfillment_item_link_count
         AND fulfillment_item_count = expected_reservation_count
         AND exact_release_fact_count = expected_reservation_count
         AND reported_released_reservation_count = expected_reservation_count
         AND release_idempotency_count = expected_reservation_count
         AND recorded_order_valid = TRUE
        THEN 'RECONCILED'
        WHEN saga_status = 'COMPLETED' THEN 'INCONSISTENT'
        WHEN saga_status = 'MANUAL_REVIEW' THEN 'RECOVERY_REQUIRED'
        WHEN saga_status = 'RETRY_SCHEDULED' THEN 'RECOVERY_PENDING'
        ELSE 'IN_PROGRESS'
    END AS readiness_status,
    CASE
        WHEN saga_status = 'COMPLETED' AND recovered_after_failure = TRUE THEN 'RECOVERED'
        WHEN saga_status = 'COMPLETED' THEN 'NOT_REQUIRED'
        WHEN saga_status = 'MANUAL_REVIEW' THEN 'REQUIRED'
        WHEN saga_status = 'RETRY_SCHEDULED' THEN 'PENDING'
        ELSE 'NOT_REQUIRED'
    END AS recovery_status
FROM yshopping_dws.dws_canonical_paid_order_cancellation_saga_current saga;
