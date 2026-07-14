CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_order_cancellation_saga_current AS
WITH latest_reservation AS (
    SELECT reservation.*
    FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_reservation_event reservation
    JOIN yshopping_dim.dim_canonical_order_cancellation_saga_current saga
      ON saga.tenant_id = reservation.tenant_id
     AND saga.saga_id = reservation.saga_id
     AND saga.aggregate_version = reservation.aggregate_version
), inventory_by_reservation AS (
    SELECT
        tenant_id,
        business_id AS order_id,
        business_item_id AS order_item_id,
        reservation_id,
        COUNT(IF(movement_type = 'RESERVATION', 1, NULL)) AS reservation_fact_count,
        COUNT(IF(movement_type = 'RESERVATION_RELEASE', 1, NULL)) AS release_fact_count,
        MAX(IF(movement_type = 'RESERVATION_RELEASE', occurred_at, NULL)) AS released_at,
        MAX(IF(movement_type = 'RESERVATION_RELEASE', recorded_at, NULL)) AS released_recorded_at
    FROM yshopping_dwd.dwd_canonical_inventory_movement
    WHERE business_type = 'TRADE_ORDER'
      AND movement_type IN ('RESERVATION', 'RESERVATION_RELEASE')
    GROUP BY tenant_id, business_id, business_item_id, reservation_id
), reservation_evidence AS (
    SELECT
        reservation.tenant_id,
        reservation.saga_id,
        COUNT(*) AS declared_reservation_row_count,
        COUNT(DISTINCT CONCAT(reservation.order_item_id, '|', reservation.reservation_id))
          AS declared_reservation_count,
        COUNT(IF(order_item.order_item_id IS NOT NULL
                  AND order_item.quantity = reservation.quantity, 1, NULL))
          AS matched_order_item_reservation_count,
        COUNT(IF(inventory.reservation_fact_count = 1, 1, NULL)) AS exact_reservation_fact_count,
        COUNT(IF(inventory.release_fact_count = 1, 1, NULL)) AS exact_release_fact_count,
        MIN(inventory.released_at) AS first_released_at,
        MAX(inventory.released_at) AS last_released_at,
        MAX(inventory.released_recorded_at) AS last_release_recorded_at
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
), order_inventory_fact AS (
    SELECT tenant_id, business_id AS order_id,
           COUNT(DISTINCT IF(movement_type = 'RESERVATION',
                             CONCAT(business_item_id, '|', reservation_id), NULL))
             AS order_reservation_fact_count,
           COUNT(DISTINCT IF(movement_type = 'RESERVATION_RELEASE',
                             CONCAT(business_item_id, '|', reservation_id), NULL))
             AS order_release_fact_count
    FROM yshopping_dwd.dwd_canonical_inventory_movement
    WHERE business_type = 'TRADE_ORDER'
      AND movement_type IN ('RESERVATION', 'RESERVATION_RELEASE')
    GROUP BY tenant_id, business_id
), order_cancelled AS (
    SELECT tenant_id, order_id,
           MAX(occurred_at) AS order_cancelled_at,
           MAX(recorded_at) AS order_cancelled_recorded_at,
           COUNT(*) AS order_cancelled_event_count
    FROM yshopping_dwd.dwd_canonical_order_status_event
    WHERE schema_version = 2 AND current_status = 'CANCELLED'
    GROUP BY tenant_id, order_id
), payment_fact AS (
    SELECT tenant_id, order_id, COUNT(DISTINCT payment_id) AS payment_fact_count
    FROM yshopping_dim.dim_canonical_payment_current
    GROUP BY tenant_id, order_id
), fulfillment_fact AS (
    SELECT tenant_id, order_id, COUNT(DISTINCT fulfillment_id) AS fulfillment_fact_count
    FROM yshopping_dim.dim_canonical_fulfillment_current
    GROUP BY tenant_id, order_id
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
    saga.previous_status,
    saga.current_status AS saga_status,
    saga.active_step,
    saga.attempt,
    saga.reason,
    saga.expected_reservation_count,
    saga.released_reservation_count AS reported_released_reservation_count,
    COALESCE(evidence.declared_reservation_row_count, 0) AS declared_reservation_row_count,
    COALESCE(evidence.declared_reservation_count, 0) AS declared_reservation_count,
    COALESCE(evidence.matched_order_item_reservation_count, 0) AS matched_order_item_reservation_count,
    COALESCE(evidence.exact_reservation_fact_count, 0) AS exact_reservation_fact_count,
    COALESCE(evidence.exact_release_fact_count, 0) AS exact_release_fact_count,
    COALESCE(order_inventory.order_reservation_fact_count, 0) AS order_reservation_fact_count,
    COALESCE(order_inventory.order_release_fact_count, 0) AS order_release_fact_count,
    order_current.previous_status AS order_previous_status,
    order_current.pre_cancellation_status AS order_pre_cancellation_status,
    order_current.current_status AS order_status,
    order_current.cancellation_saga_id AS order_cancellation_saga_id,
    order_current.order_event_count,
    cancelled.order_cancelled_at,
    cancelled.order_cancelled_recorded_at,
    evidence.first_released_at,
    evidence.last_released_at,
    evidence.last_release_recorded_at,
    evidence.last_release_recorded_at IS NOT NULL
      AND cancelled.order_cancelled_recorded_at IS NOT NULL
      AND evidence.last_release_recorded_at <= cancelled.order_cancelled_recorded_at
      AS all_releases_before_cancel,
    COALESCE(payment.payment_fact_count, 0) AS payment_fact_count,
    COALESCE(fulfillment.fulfillment_fact_count, 0) AS fulfillment_fact_count,
    saga.error_code,
    saga.error_message,
    saga.next_retry_at,
    saga.first_recovery_at,
    saga.occurred_at AS saga_status_at,
    saga.recorded_at AS saga_recorded_at,
    GREATEST(
        saga.recorded_at,
        COALESCE(order_current.recorded_at, saga.recorded_at),
        COALESCE(evidence.last_released_at, saga.recorded_at),
        COALESCE(cancelled.order_cancelled_at, saga.recorded_at)
    ) AS data_freshness_at
FROM yshopping_dim.dim_canonical_order_cancellation_saga_current saga
LEFT JOIN reservation_evidence evidence
  ON evidence.tenant_id = saga.tenant_id AND evidence.saga_id = saga.saga_id
LEFT JOIN yshopping_dim.dim_canonical_order_current order_current
  ON order_current.tenant_id = saga.tenant_id AND order_current.order_id = saga.order_id
LEFT JOIN order_inventory_fact order_inventory
  ON order_inventory.tenant_id = saga.tenant_id AND order_inventory.order_id = saga.order_id
LEFT JOIN order_cancelled cancelled
  ON cancelled.tenant_id = saga.tenant_id AND cancelled.order_id = saga.order_id
LEFT JOIN payment_fact payment
  ON payment.tenant_id = saga.tenant_id AND payment.order_id = saga.order_id
LEFT JOIN fulfillment_fact fulfillment
  ON fulfillment.tenant_id = saga.tenant_id AND fulfillment.order_id = saga.order_id
WHERE saga.schema_version = 1;
