CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_paid_order_cancellation_saga_current AS
WITH paid_saga AS (
    SELECT *
    FROM yshopping_dim.dim_canonical_order_cancellation_saga_current
    WHERE schema_version = 2 AND cancellation_mode = 'PAID_UNSHIPPED'
), latest_reservation AS (
    SELECT reservation.*
    FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_reservation_event reservation
    JOIN paid_saga saga
      ON saga.tenant_id = reservation.tenant_id
     AND saga.saga_id = reservation.saga_id
     AND saga.aggregate_version = reservation.aggregate_version
    WHERE reservation.schema_version = 2
), declared_fulfillment AS (
    SELECT
        saga.tenant_id,
        saga.saga_id,
        get_json_string(entry.`value`, '$.fulfillment_id') AS fulfillment_id,
        get_json_string(entry.`value`, '$.status') AS reported_status
    FROM paid_saga saga,
         LATERAL json_each(saga.fulfillments) entry
), inventory_by_reservation AS (
    SELECT
        tenant_id,
        business_id AS order_id,
        business_item_id AS order_item_id,
        reservation_id,
        COUNT(IF(movement_type = 'RESERVATION', 1, NULL)) AS reservation_fact_count,
        COUNT(IF(movement_type = 'RESERVATION_RELEASE', 1, NULL)) AS release_fact_count,
        COUNT(IF(movement_type = 'RESERVATION_RELEASE' AND schema_version = 2, 1, NULL)) AS paid_release_fact_count,
        COUNT(IF(movement_type = 'SALE_SHIPMENT', 1, NULL)) AS sale_shipment_fact_count,
        MAX(IF(movement_type = 'RESERVATION_RELEASE', cancellation_saga_id, NULL)) AS release_saga_id,
        MAX(IF(movement_type = 'RESERVATION_RELEASE', step_ordinal, NULL)) AS release_step_ordinal,
        MAX(IF(movement_type = 'RESERVATION_RELEASE', recorded_at, NULL)) AS release_recorded_at,
        COUNT(DISTINCT IF(movement_type = 'RESERVATION_RELEASE', idempotency_key, NULL)) AS release_idempotency_count
    FROM yshopping_dwd.dwd_canonical_inventory_movement
    WHERE business_type = 'TRADE_ORDER'
      AND movement_type IN ('RESERVATION', 'RESERVATION_RELEASE', 'SALE_SHIPMENT')
    GROUP BY tenant_id, business_id, business_item_id, reservation_id
), reservation_evidence AS (
    SELECT
        reservation.tenant_id,
        reservation.saga_id,
        COUNT(*) AS declared_reservation_row_count,
        COUNT(DISTINCT CONCAT(reservation.order_item_id, '|', reservation.reservation_id)) AS declared_reservation_count,
        COUNT(IF(order_item.order_item_id IS NOT NULL AND order_item.quantity = reservation.quantity, 1, NULL))
          AS matched_order_item_reservation_count,
        COUNT(IF(inventory.reservation_fact_count = 1, 1, NULL)) AS exact_reservation_fact_count,
        COUNT(IF(inventory.release_fact_count = 1 AND inventory.paid_release_fact_count = 1
                  AND inventory.release_saga_id = reservation.saga_id
                  AND inventory.release_step_ordinal = 3, 1, NULL)) AS exact_release_fact_count,
        SUM(COALESCE(inventory.sale_shipment_fact_count, 0)) AS sale_shipment_fact_count,
        MAX(inventory.release_recorded_at) AS last_release_recorded_at,
        SUM(COALESCE(inventory.release_idempotency_count, 0)) AS release_idempotency_count
    FROM latest_reservation reservation
    LEFT JOIN yshopping_dws.dws_canonical_order_item_current order_item
      ON order_item.tenant_id = reservation.tenant_id
     AND order_item.order_id = reservation.order_id
     AND order_item.order_item_id = reservation.order_item_id
     AND order_item.reservation_id = reservation.reservation_id
    LEFT JOIN inventory_by_reservation inventory
      ON inventory.tenant_id = reservation.tenant_id
     AND inventory.order_id = reservation.order_id
     AND inventory.order_item_id = reservation.order_item_id
     AND inventory.reservation_id = reservation.reservation_id
    GROUP BY reservation.tenant_id, reservation.saga_id
), order_milestone AS (
    SELECT
        tenant_id,
        order_id,
        MAX(IF(schema_version = 3 AND current_status = 'CANCELLATION_PENDING', recorded_at, NULL)) AS order_fenced_recorded_at,
        MAX(IF(schema_version = 3 AND current_status = 'CANCELLED', recorded_at, NULL)) AS order_cancelled_recorded_at,
        MAX(IF(schema_version = 3 AND current_status = 'CANCELLED', step_ordinal, NULL)) AS order_cancel_step_ordinal,
        COUNT(IF(schema_version = 3 AND current_status = 'CANCELLATION_PENDING', 1, NULL)) AS order_fence_event_count,
        COUNT(IF(schema_version = 3 AND current_status = 'CANCELLED', 1, NULL)) AS order_cancel_event_count,
        COUNT(DISTINCT IF(schema_version = 3 AND current_status = 'CANCELLED', idempotency_key, NULL))
          AS order_cancel_idempotency_count
    FROM yshopping_dwd.dwd_canonical_order_status_event
    GROUP BY tenant_id, order_id
), payment_evidence AS (
    SELECT
        tenant_id,
        payment_id,
        order_id,
        COUNT(IF(current_status = 'CAPTURED', 1, NULL)) AS capture_event_count,
        COUNT(IF(schema_version = 2 AND current_status = 'REFUNDED', 1, NULL)) AS refund_event_count,
        MAX(IF(current_status = 'CAPTURED', recorded_at, NULL)) AS captured_recorded_at,
        MAX(IF(schema_version = 2 AND current_status = 'REFUNDED', recorded_at, NULL)) AS refunded_recorded_at,
        MAX(IF(schema_version = 2 AND current_status = 'REFUNDED', cancellation_saga_id, NULL)) AS refund_saga_id,
        MAX(IF(schema_version = 2 AND current_status = 'REFUNDED', step_ordinal, NULL)) AS refund_step_ordinal,
        MAX(IF(schema_version = 2 AND current_status = 'REFUNDED', transaction_id, NULL)) AS refund_transaction_id,
        COUNT(DISTINCT IF(schema_version = 2 AND current_status = 'REFUNDED', idempotency_key, NULL))
          AS refund_idempotency_count
    FROM yshopping_dwd.dwd_canonical_payment_status_event
    GROUP BY tenant_id, payment_id, order_id
), fulfillment_evidence AS (
    SELECT
        declared.tenant_id,
        declared.saga_id,
        MAX(declared.fulfillment_id) AS reported_fulfillment_id,
        COUNT(*) AS declared_fulfillment_row_count,
        COUNT(DISTINCT declared.fulfillment_id) AS declared_fulfillment_count,
        COUNT(IF(current.fulfillment_id IS NOT NULL AND current.order_id = saga.order_id, 1, NULL))
          AS matched_fulfillment_count,
        COUNT(IF(current.current_status = 'CANCELLED' AND declared.reported_status = 'CANCELLED'
                  AND current.cancellation_saga_id = declared.saga_id
                  AND current.step_ordinal = 1, 1, NULL)) AS exact_cancelled_fulfillment_count,
        SUM(COALESCE(current.fulfillment_event_count, 0)) AS fulfillment_event_count,
        MAX(IF(current.current_status = 'CANCELLED', current.recorded_at, NULL)) AS fulfillment_cancelled_recorded_at,
        SUM(IF(current.shipment_id IS NOT NULL OR current.carrier_code IS NOT NULL OR current.waybill_no IS NOT NULL
               OR current.shipped_at IS NOT NULL OR current.in_transit_at IS NOT NULL
               OR current.delivered_at IS NOT NULL, 1, 0)) AS shipment_fact_count,
        SUM(COALESCE(items.item_count, 0)) AS fulfillment_item_count,
        SUM(COALESCE(items.valid_order_item_link_count, 0)) AS valid_fulfillment_item_link_count
    FROM declared_fulfillment declared
    JOIN paid_saga saga
      ON saga.tenant_id = declared.tenant_id AND saga.saga_id = declared.saga_id
    LEFT JOIN yshopping_dim.dim_canonical_fulfillment_current current
      ON current.tenant_id = declared.tenant_id AND current.fulfillment_id = declared.fulfillment_id
    LEFT JOIN (
        SELECT tenant_id, fulfillment_id,
               COUNT(*) AS item_count,
               COUNT(IF(order_item_link_valid = TRUE, 1, NULL)) AS valid_order_item_link_count
        FROM yshopping_dws.dws_canonical_fulfillment_item_current
        GROUP BY tenant_id, fulfillment_id
    ) items ON items.tenant_id = declared.tenant_id AND items.fulfillment_id = declared.fulfillment_id
    GROUP BY declared.tenant_id, declared.saga_id
)
SELECT
    saga.tenant_id,
    saga.run_id,
    saga.saga_id,
    saga.order_id,
    saga.order_no,
    saga.aggregate_version,
    saga.saga_event_count,
    saga.retry_event_count,
    saga.manual_review_event_count,
    saga.max_attempt,
    saga.recovered_after_failure,
    saga.cancellation_mode,
    saga.previous_status,
    saga.current_status AS saga_status,
    saga.active_step,
    saga.step_ordinal,
    saga.attempt,
    saga.payment_id AS reported_payment_id,
    saga.payment_refund_transaction_id AS reported_refund_transaction_id,
    saga.payment_status AS reported_payment_status,
    saga.expected_fulfillment_count,
    saga.cancelled_fulfillment_count AS reported_cancelled_fulfillment_count,
    saga.expected_reservation_count,
    saga.released_reservation_count AS reported_released_reservation_count,
    COALESCE(fulfillment.declared_fulfillment_row_count, 0) AS declared_fulfillment_row_count,
    fulfillment.reported_fulfillment_id,
    COALESCE(fulfillment.declared_fulfillment_count, 0) AS declared_fulfillment_count,
    COALESCE(fulfillment.matched_fulfillment_count, 0) AS matched_fulfillment_count,
    COALESCE(fulfillment.exact_cancelled_fulfillment_count, 0) AS exact_cancelled_fulfillment_count,
    COALESCE(fulfillment.fulfillment_event_count, 0) AS fulfillment_event_count,
    COALESCE(fulfillment.fulfillment_item_count, 0) AS fulfillment_item_count,
    COALESCE(fulfillment.valid_fulfillment_item_link_count, 0) AS valid_fulfillment_item_link_count,
    COALESCE(fulfillment.shipment_fact_count, 0) AS shipment_fact_count,
    COALESCE(reservation.declared_reservation_row_count, 0) AS declared_reservation_row_count,
    COALESCE(reservation.declared_reservation_count, 0) AS declared_reservation_count,
    COALESCE(reservation.matched_order_item_reservation_count, 0) AS matched_order_item_reservation_count,
    COALESCE(reservation.exact_reservation_fact_count, 0) AS exact_reservation_fact_count,
    COALESCE(reservation.exact_release_fact_count, 0) AS exact_release_fact_count,
    COALESCE(reservation.sale_shipment_fact_count, 0) AS sale_shipment_fact_count,
    COALESCE(reservation.release_idempotency_count, 0) AS release_idempotency_count,
    order_current.previous_status AS order_previous_status,
    order_current.pre_cancellation_status AS order_pre_cancellation_status,
    order_current.current_status AS order_status,
    order_current.cancellation_saga_id AS order_cancellation_saga_id,
    order_current.cancellation_mode AS order_cancellation_mode,
    order_current.step_ordinal AS order_step_ordinal,
    order_current.payment_id AS order_payment_id,
    order_current.fulfillment_id AS order_fulfillment_id,
    order_current.shipment_id AS order_shipment_id,
    order_current.refund_id AS order_refund_id,
    order_current.payable_amount_minor,
    order_current.currency_code AS order_currency_code,
    order_current.order_event_count,
    order_event.order_fence_event_count,
    order_event.order_cancel_event_count,
    order_event.order_cancel_idempotency_count,
    payment.current_status AS payment_status,
    payment.captured_amount_minor,
    payment.refunded_amount_minor,
    payment.currency_code AS payment_currency_code,
    payment_event.capture_event_count,
    payment_event.refund_event_count,
    payment_event.refund_saga_id,
    payment_event.refund_step_ordinal,
    payment_event.refund_transaction_id,
    payment_event.refund_idempotency_count,
    order_event.order_fenced_recorded_at,
    fulfillment.fulfillment_cancelled_recorded_at,
    payment_event.refunded_recorded_at AS payment_refunded_recorded_at,
    reservation.last_release_recorded_at,
    order_event.order_cancelled_recorded_at,
    saga.recorded_at AS saga_completed_recorded_at,
    order_event.order_fenced_recorded_at IS NOT NULL
      AND fulfillment.fulfillment_cancelled_recorded_at IS NOT NULL
      AND payment_event.refunded_recorded_at IS NOT NULL
      AND reservation.last_release_recorded_at IS NOT NULL
      AND order_event.order_cancelled_recorded_at IS NOT NULL
      AND order_event.order_fenced_recorded_at <= fulfillment.fulfillment_cancelled_recorded_at
      AND fulfillment.fulfillment_cancelled_recorded_at <= payment_event.refunded_recorded_at
      AND payment_event.refunded_recorded_at <= reservation.last_release_recorded_at
      AND reservation.last_release_recorded_at <= order_event.order_cancelled_recorded_at
      AND order_event.order_cancelled_recorded_at <= saga.recorded_at
      AS recorded_order_valid,
    saga.error_code,
    saga.error_message,
    saga.next_retry_at,
    saga.first_recovery_at,
    GREATEST(saga.recorded_at, COALESCE(order_current.recorded_at, saga.recorded_at),
             COALESCE(fulfillment.fulfillment_cancelled_recorded_at, saga.recorded_at),
             COALESCE(payment_event.refunded_recorded_at, saga.recorded_at),
             COALESCE(reservation.last_release_recorded_at, saga.recorded_at)) AS data_freshness_at
FROM paid_saga saga
LEFT JOIN reservation_evidence reservation
  ON reservation.tenant_id = saga.tenant_id AND reservation.saga_id = saga.saga_id
LEFT JOIN fulfillment_evidence fulfillment
  ON fulfillment.tenant_id = saga.tenant_id AND fulfillment.saga_id = saga.saga_id
LEFT JOIN yshopping_dim.dim_canonical_order_current order_current
  ON order_current.tenant_id = saga.tenant_id AND order_current.order_id = saga.order_id
LEFT JOIN order_milestone order_event
  ON order_event.tenant_id = saga.tenant_id AND order_event.order_id = saga.order_id
LEFT JOIN yshopping_dim.dim_canonical_payment_current payment
  ON payment.tenant_id = saga.tenant_id AND payment.payment_id = saga.payment_id
LEFT JOIN payment_evidence payment_event
  ON payment_event.tenant_id = saga.tenant_id
 AND payment_event.payment_id = saga.payment_id
 AND payment_event.order_id = saga.order_id;
