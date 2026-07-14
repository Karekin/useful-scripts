SELECT 'canonical_paid_cancellation_saga_version_continuity' AS check_name, COUNT(*) AS violations
FROM (
  SELECT tenant_id, saga_id
  FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event
  WHERE schema_version = 2
  GROUP BY tenant_id, saga_id
  HAVING MIN(aggregate_version) <> 1 OR MAX(aggregate_version) <> COUNT(*)
) gap
UNION ALL
SELECT 'canonical_paid_cancellation_saga_status_continuity', COUNT(*)
FROM (
  SELECT previous_status,
         LAG(current_status) OVER (PARTITION BY tenant_id, saga_id ORDER BY aggregate_version) AS expected_previous,
         aggregate_version
  FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event
  WHERE schema_version = 2
) history
WHERE (aggregate_version = 1 AND previous_status IS NOT NULL)
   OR (aggregate_version > 1 AND NOT previous_status <=> expected_previous)
UNION ALL
SELECT 'canonical_paid_cancellation_saga_allowed_transition', COUNT(*)
FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event
WHERE schema_version = 2 AND NOT (
       (previous_status IS NULL AND current_status = 'REQUESTED')
    OR (previous_status = 'REQUESTED' AND current_status = 'CANCELLING_FULFILLMENT')
    OR (previous_status = 'CANCELLING_FULFILLMENT' AND current_status IN ('FULFILLMENT_CANCELLED', 'RETRY_SCHEDULED', 'MANUAL_REVIEW'))
    OR (previous_status = 'FULFILLMENT_CANCELLED' AND current_status = 'REFUNDING_PAYMENT')
    OR (previous_status = 'REFUNDING_PAYMENT' AND current_status IN ('PAYMENT_REFUNDED', 'RETRY_SCHEDULED', 'MANUAL_REVIEW'))
    OR (previous_status = 'PAYMENT_REFUNDED' AND current_status = 'RELEASING_RESERVATIONS')
    OR (previous_status = 'RELEASING_RESERVATIONS' AND current_status IN ('RESERVATIONS_RELEASED', 'RETRY_SCHEDULED', 'MANUAL_REVIEW'))
    OR (previous_status = 'RESERVATIONS_RELEASED' AND current_status = 'CANCELLING_ORDER')
    OR (previous_status = 'CANCELLING_ORDER' AND current_status IN ('COMPLETED', 'RETRY_SCHEDULED', 'MANUAL_REVIEW'))
    OR (previous_status = 'RETRY_SCHEDULED' AND current_status IN ('CANCELLING_FULFILLMENT', 'REFUNDING_PAYMENT', 'RELEASING_RESERVATIONS', 'CANCELLING_ORDER', 'MANUAL_REVIEW'))
    OR (previous_status = 'MANUAL_REVIEW' AND current_status IN ('RETRY_SCHEDULED', 'CANCELLING_FULFILLMENT', 'REFUNDING_PAYMENT', 'RELEASING_RESERVATIONS', 'CANCELLING_ORDER'))
)
UNION ALL
SELECT 'canonical_paid_cancellation_saga_identity_stable', COUNT(*)
FROM (
  SELECT tenant_id, saga_id
  FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event
  WHERE schema_version = 2
  GROUP BY tenant_id, saga_id
  HAVING COUNT(DISTINCT cancellation_mode) <> 1
      OR MAX(cancellation_mode) <> 'PAID_UNSHIPPED'
      OR COUNT(DISTINCT run_id) <> 1 OR COUNT(DISTINCT order_id) <> 1
      OR COUNT(DISTINCT payment_id) <> 1
      OR COUNT(DISTINCT expected_fulfillment_count) <> 1
      OR COUNT(DISTINCT expected_reservation_count) <> 1
) drift
UNION ALL
SELECT 'canonical_paid_cancellation_saga_state_shape', COUNT(*)
FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event
WHERE schema_version = 2 AND (
       (current_status = 'REQUESTED' AND (active_step <> 'CANCEL_FULFILLMENT' OR step_ordinal <> 1))
    OR (current_status = 'CANCELLING_FULFILLMENT' AND (active_step <> 'CANCEL_FULFILLMENT' OR step_ordinal <> 1))
    OR (current_status = 'FULFILLMENT_CANCELLED' AND (active_step <> 'REFUND_PAYMENT' OR step_ordinal <> 2))
    OR (current_status = 'REFUNDING_PAYMENT' AND (active_step <> 'REFUND_PAYMENT' OR step_ordinal <> 2))
    OR (current_status = 'PAYMENT_REFUNDED' AND (active_step <> 'RELEASE_RESERVATIONS' OR step_ordinal <> 3 OR payment_status <> 'REFUNDED'))
    OR (current_status = 'RELEASING_RESERVATIONS' AND (active_step <> 'RELEASE_RESERVATIONS' OR step_ordinal <> 3))
    OR (current_status = 'RESERVATIONS_RELEASED' AND (active_step <> 'CANCEL_ORDER' OR step_ordinal <> 4 OR released_reservation_count <> expected_reservation_count))
    OR (current_status = 'CANCELLING_ORDER' AND (active_step <> 'CANCEL_ORDER' OR step_ordinal <> 4))
    OR (current_status = 'COMPLETED' AND (active_step <> 'NONE' OR step_ordinal <> 5
        OR payment_status <> 'REFUNDED' OR payment_refund_transaction_id IS NULL
        OR cancelled_fulfillment_count <> expected_fulfillment_count
        OR released_reservation_count <> expected_reservation_count
        OR error_code IS NOT NULL OR error_message IS NOT NULL OR next_retry_at IS NOT NULL))
)
UNION ALL
SELECT 'canonical_paid_cancellation_saga_recovery_shape', COUNT(*)
FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event
WHERE schema_version = 2 AND (
      (current_status = 'RETRY_SCHEDULED' AND (active_step = 'NONE' OR error_code IS NULL OR error_message IS NULL OR next_retry_at IS NULL))
   OR (current_status = 'MANUAL_REVIEW' AND (active_step = 'NONE' OR error_code IS NULL OR error_message IS NULL OR next_retry_at IS NOT NULL))
)
UNION ALL
SELECT 'canonical_paid_cancellation_saga_snapshot_count', COUNT(*)
FROM (
  SELECT event.tenant_id, event.saga_id, event.aggregate_version,
         event.expected_reservation_count, event.expected_fulfillment_count,
         COUNT(DISTINCT CONCAT(reservation.order_item_id, '|', reservation.reservation_id)) AS reservation_count,
         COUNT(DISTINCT get_json_string(fulfillment.`value`, '$.fulfillment_id')) AS fulfillment_count
  FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event event
  LEFT JOIN yshopping_dwd.dwd_canonical_order_cancellation_saga_reservation_event reservation
    ON reservation.tenant_id = event.tenant_id AND reservation.saga_id = event.saga_id
   AND reservation.aggregate_version = event.aggregate_version AND reservation.schema_version = 2,
       LATERAL json_each(event.fulfillments) fulfillment
  WHERE event.schema_version = 2
  GROUP BY event.tenant_id, event.saga_id, event.aggregate_version,
           event.expected_reservation_count, event.expected_fulfillment_count
  HAVING reservation_count <> event.expected_reservation_count
      OR fulfillment_count <> event.expected_fulfillment_count
) invalid_snapshot
UNION ALL
SELECT 'canonical_paid_cancellation_order_and_money', COUNT(*)
FROM yshopping_dws.dws_canonical_paid_order_cancellation_saga_current
WHERE order_cancellation_saga_id <> saga_id
   OR order_cancellation_mode <> 'PAID_UNSHIPPED'
   OR order_payment_id <> reported_payment_id
   OR order_fulfillment_id <> reported_fulfillment_id
   OR (saga_status = 'COMPLETED' AND (
       order_status <> 'CANCELLED' OR order_previous_status <> 'CANCELLATION_PENDING'
       OR order_pre_cancellation_status <> 'PAYMENT_CONFIRMED' OR order_step_ordinal <> 4
       OR order_shipment_id IS NOT NULL OR order_fence_event_count <> 1 OR order_cancel_event_count <> 1
       OR payment_status <> 'REFUNDED' OR reported_payment_status <> 'REFUNDED'
       OR capture_event_count <> 1 OR refund_event_count <> 1 OR refund_step_ordinal <> 2
       OR refund_transaction_id <> reported_refund_transaction_id
       OR order_refund_id <> CAST(refund_transaction_id AS VARCHAR)
       OR payable_amount_minor <> captured_amount_minor OR captured_amount_minor <> refunded_amount_minor
       OR order_currency_code <> payment_currency_code))
UNION ALL
SELECT 'canonical_paid_cancellation_fulfillment', COUNT(*)
FROM yshopping_dws.dws_canonical_paid_order_cancellation_saga_current
WHERE declared_fulfillment_row_count <> declared_fulfillment_count
   OR declared_fulfillment_count <> expected_fulfillment_count
   OR matched_fulfillment_count <> expected_fulfillment_count
   OR exact_cancelled_fulfillment_count > expected_fulfillment_count
   OR shipment_fact_count <> 0
   OR (saga_status = 'COMPLETED' AND (
       fulfillment_event_count <> 3
       OR exact_cancelled_fulfillment_count <> expected_fulfillment_count
       OR reported_cancelled_fulfillment_count <> expected_fulfillment_count
       OR fulfillment_item_count <> valid_fulfillment_item_link_count))
UNION ALL
SELECT 'canonical_paid_cancellation_inventory', COUNT(*)
FROM yshopping_dws.dws_canonical_paid_order_cancellation_saga_current
WHERE declared_reservation_row_count <> declared_reservation_count
   OR declared_reservation_count <> expected_reservation_count
   OR matched_order_item_reservation_count <> expected_reservation_count
   OR exact_reservation_fact_count <> expected_reservation_count
   OR exact_release_fact_count > expected_reservation_count
   OR sale_shipment_fact_count <> 0
   OR (saga_status = 'COMPLETED' AND (
       exact_release_fact_count <> expected_reservation_count
       OR reported_released_reservation_count <> expected_reservation_count))
UNION ALL
SELECT 'canonical_paid_cancellation_stable_effect_idempotency', COUNT(*)
FROM yshopping_dws.dws_canonical_paid_order_cancellation_saga_current
WHERE order_cancel_idempotency_count > 1 OR refund_idempotency_count > 1
   OR release_idempotency_count > expected_reservation_count
   OR (saga_status = 'COMPLETED' AND (
       order_cancel_idempotency_count <> 1 OR refund_idempotency_count <> 1
       OR release_idempotency_count <> expected_reservation_count))
UNION ALL
SELECT 'canonical_paid_cancellation_participant_shape', COUNT(*)
FROM (
  SELECT event_id
  FROM yshopping_dwd.dwd_canonical_order_status_event
  WHERE schema_version = 3 AND NOT (
       cancellation_mode = 'PAID_UNSHIPPED' AND cancellation_saga_id IS NOT NULL
       AND ((current_status = 'CANCELLATION_PENDING' AND previous_status = 'PAYMENT_CONFIRMED' AND step_ordinal = 0)
         OR (current_status = 'CANCELLED' AND previous_status = 'CANCELLATION_PENDING' AND step_ordinal = 4
             AND idempotency_key = CONCAT('cancel-saga:', cancellation_saga_id, ':order-finalize'))))
  UNION ALL
  SELECT event_id
  FROM yshopping_dwd.dwd_canonical_fulfillment_status_event
  WHERE schema_version = 2 AND NOT (
       cancellation_saga_id IS NOT NULL AND step_ordinal = 1
       AND ((current_status = 'CANCELLATION_PENDING' AND previous_status = 'CREATED'
             AND idempotency_key = CONCAT('cancel-saga:', cancellation_saga_id, ':fulfillment:', fulfillment_id, ':request'))
         OR (current_status = 'CANCELLED' AND previous_status = 'CANCELLATION_PENDING'
             AND idempotency_key = CONCAT('cancel-saga:', cancellation_saga_id, ':fulfillment:', fulfillment_id, ':finalize'))))
  UNION ALL
  SELECT event_id
  FROM yshopping_dwd.dwd_canonical_payment_status_event
  WHERE schema_version = 2 AND NOT (
       cancellation_saga_id IS NOT NULL AND step_ordinal = 2
       AND previous_status = 'CAPTURED' AND current_status = 'REFUNDED'
       AND idempotency_key = CONCAT('cancel-saga:', cancellation_saga_id, ':payment:', payment_id, ':refund'))
  UNION ALL
  SELECT event_id
  FROM yshopping_dwd.dwd_canonical_inventory_movement
  WHERE schema_version = 2 AND NOT (
       cancellation_saga_id IS NOT NULL AND step_ordinal = 3
       AND movement_type = 'RESERVATION_RELEASE' AND business_type = 'TRADE_ORDER'
       AND idempotency_key = CONCAT('cancel-saga:', cancellation_saga_id, ':release:', reservation_id))
) invalid_participant
UNION ALL
SELECT 'canonical_paid_cancellation_participant_replay_unique', COUNT(*)
FROM (
  SELECT participant, tenant_id, idempotency_key
  FROM (
    SELECT 'ORDER' participant, tenant_id, idempotency_key
    FROM yshopping_dwd.dwd_canonical_order_status_event WHERE schema_version = 3
    UNION ALL
    SELECT 'FULFILLMENT', tenant_id, idempotency_key
    FROM yshopping_dwd.dwd_canonical_fulfillment_status_event WHERE schema_version = 2
    UNION ALL
    SELECT 'PAYMENT', tenant_id, idempotency_key
    FROM yshopping_dwd.dwd_canonical_payment_status_event WHERE schema_version = 2
    UNION ALL
    SELECT 'INVENTORY', tenant_id, idempotency_key
    FROM yshopping_dwd.dwd_canonical_inventory_movement WHERE schema_version = 2
  ) participant_event
  GROUP BY participant, tenant_id, idempotency_key
  HAVING COUNT(*) > 1
) duplicate_effect
UNION ALL
SELECT 'canonical_paid_cancellation_recorded_order', COUNT(*)
FROM yshopping_dws.dws_canonical_paid_order_cancellation_saga_current
WHERE saga_status = 'COMPLETED' AND recorded_order_valid <> TRUE
UNION ALL
SELECT 'canonical_paid_cancellation_completed_reconciled', COUNT(*)
FROM yshopping_ads.ads_canonical_paid_order_cancellation_saga_readiness
WHERE saga_status = 'COMPLETED' AND readiness_status <> 'RECONCILED'
UNION ALL
SELECT 'canonical_paid_cancellation_recovery_not_reconciled', COUNT(*)
FROM yshopping_ads.ads_canonical_paid_order_cancellation_saga_readiness
WHERE saga_status IN ('RETRY_SCHEDULED', 'MANUAL_REVIEW') AND readiness_status = 'RECONCILED';
