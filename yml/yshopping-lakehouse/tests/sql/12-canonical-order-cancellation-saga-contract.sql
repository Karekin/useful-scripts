SELECT 'canonical_cancellation_saga_version_continuity' AS check_name, COUNT(*) AS violations
FROM (
  SELECT tenant_id, saga_id
  FROM (SELECT * FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event WHERE schema_version = 1) cancellation_event
  GROUP BY tenant_id, saga_id
  HAVING MIN(aggregate_version) <> 1 OR MAX(aggregate_version) <> COUNT(*)
) gap
UNION ALL
SELECT 'canonical_cancellation_saga_status_continuity', COUNT(*)
FROM (
  SELECT previous_status,
         LAG(current_status) OVER (PARTITION BY tenant_id, saga_id ORDER BY aggregate_version) AS expected_previous,
         aggregate_version
  FROM (SELECT * FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event WHERE schema_version = 1) cancellation_event
) history
WHERE (aggregate_version = 1 AND previous_status IS NOT NULL)
   OR (aggregate_version > 1 AND NOT previous_status <=> expected_previous)
UNION ALL
SELECT 'canonical_cancellation_saga_allowed_transition', COUNT(*)
FROM (SELECT * FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event WHERE schema_version = 1) cancellation_event
WHERE NOT (
       (previous_status IS NULL AND current_status = 'REQUESTED')
    OR (previous_status = 'REQUESTED' AND current_status = 'RELEASING_RESERVATIONS')
    OR (previous_status = 'RELEASING_RESERVATIONS' AND current_status IN ('RESERVATIONS_RELEASED', 'RETRY_SCHEDULED', 'MANUAL_REVIEW'))
    OR (previous_status = 'RESERVATIONS_RELEASED' AND current_status = 'CANCELLING_ORDER')
    OR (previous_status = 'CANCELLING_ORDER' AND current_status IN ('COMPLETED', 'RETRY_SCHEDULED', 'MANUAL_REVIEW'))
    OR (previous_status = 'RETRY_SCHEDULED' AND current_status IN ('RELEASING_RESERVATIONS', 'CANCELLING_ORDER', 'MANUAL_REVIEW'))
    OR (previous_status = 'MANUAL_REVIEW' AND current_status IN ('RETRY_SCHEDULED', 'RELEASING_RESERVATIONS', 'CANCELLING_ORDER'))
)
UNION ALL
SELECT 'canonical_cancellation_saga_identity_stable', COUNT(*)
FROM (
  SELECT tenant_id, saga_id
  FROM (SELECT * FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event WHERE schema_version = 1) cancellation_event
  GROUP BY tenant_id, saga_id
  HAVING COUNT(DISTINCT run_id) <> 1
      OR COUNT(DISTINCT order_id) <> 1
      OR COUNT(DISTINCT order_no) <> 1
      OR COUNT(DISTINCT expected_reservation_count) <> 1
) drift
UNION ALL
SELECT 'canonical_cancellation_saga_required_identity', COUNT(*)
FROM (SELECT * FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event WHERE schema_version = 1) cancellation_event
WHERE tenant_id <= 0
   OR saga_id IS NULL OR saga_id = ''
   OR payload_saga_id IS NULL OR payload_saga_id <> saga_id
   OR correlation_id IS NULL OR correlation_id = ''
   OR run_id IS NULL OR run_id = ''
   OR order_id IS NULL OR order_id = ''
   OR order_no IS NULL OR order_no = ''
UNION ALL
SELECT 'canonical_cancellation_saga_idempotency_unique', COUNT(*)
FROM (
  SELECT tenant_id, idempotency_key
  FROM (SELECT * FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event WHERE schema_version = 1) cancellation_event
  GROUP BY tenant_id, idempotency_key
  HAVING COUNT(*) > 1
) duplicate_event
UNION ALL
SELECT 'canonical_cancellation_saga_snapshot_count', COUNT(*)
FROM (
  SELECT event.tenant_id, event.saga_id, event.aggregate_version,
         event.expected_reservation_count,
         COUNT(reservation.reservation_id) AS reservation_rows,
         COUNT(DISTINCT CONCAT(reservation.order_item_id, '|', reservation.reservation_id)) AS reservation_count
  FROM (SELECT * FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event WHERE schema_version = 1) event
  LEFT JOIN (SELECT * FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_reservation_event WHERE schema_version = 1) reservation
    ON reservation.tenant_id = event.tenant_id
   AND reservation.saga_id = event.saga_id
   AND reservation.aggregate_version = event.aggregate_version
  GROUP BY event.tenant_id, event.saga_id, event.aggregate_version, event.expected_reservation_count
  HAVING reservation_rows <> event.expected_reservation_count
      OR reservation_count <> event.expected_reservation_count
) invalid_snapshot
UNION ALL
SELECT 'canonical_cancellation_saga_snapshot_set_stable', COUNT(*)
FROM (
  SELECT reservation.tenant_id, reservation.saga_id,
         reservation.order_item_id, reservation.reservation_id,
         COUNT(DISTINCT reservation.aggregate_version) AS observed_versions,
         MAX(saga.saga_event_count) AS expected_versions,
         COUNT(DISTINCT reservation.quantity) AS quantity_versions
  FROM (SELECT * FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_reservation_event WHERE schema_version = 1) reservation
  JOIN yshopping_dim.dim_canonical_order_cancellation_saga_current saga
    ON saga.tenant_id = reservation.tenant_id AND saga.saga_id = reservation.saga_id
  GROUP BY reservation.tenant_id, reservation.saga_id,
           reservation.order_item_id, reservation.reservation_id
  HAVING observed_versions <> expected_versions OR quantity_versions <> 1
) drift
UNION ALL
SELECT 'canonical_cancellation_saga_release_progress', COUNT(*)
FROM (
  SELECT released_reservation_count,
         expected_reservation_count,
         LAG(released_reservation_count) OVER (
           PARTITION BY tenant_id, saga_id ORDER BY aggregate_version
         ) AS previous_released
  FROM (SELECT * FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event WHERE schema_version = 1) cancellation_event
) progress
WHERE released_reservation_count < 0
   OR released_reservation_count > expected_reservation_count
   OR (previous_released IS NOT NULL AND released_reservation_count < previous_released)
UNION ALL
SELECT 'canonical_cancellation_saga_recovery_shape', COUNT(*)
FROM (SELECT * FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event WHERE schema_version = 1) cancellation_event
WHERE (current_status = 'RETRY_SCHEDULED'
       AND (active_step = 'NONE' OR error_code IS NULL OR error_code = ''
            OR error_message IS NULL OR error_message = '' OR next_retry_at IS NULL))
   OR (current_status = 'MANUAL_REVIEW'
       AND (active_step = 'NONE' OR error_code IS NULL OR error_code = ''
            OR error_message IS NULL OR error_message = '' OR next_retry_at IS NOT NULL))
UNION ALL
SELECT 'canonical_cancellation_saga_state_shape', COUNT(*)
FROM (SELECT * FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event WHERE schema_version = 1) cancellation_event
WHERE (current_status = 'REQUESTED'
       AND (active_step <> 'RELEASE_RESERVATIONS' OR attempt <> 0 OR released_reservation_count <> 0))
   OR (current_status = 'RELEASING_RESERVATIONS' AND active_step <> 'RELEASE_RESERVATIONS')
   OR (current_status = 'RESERVATIONS_RELEASED'
       AND (active_step <> 'CANCEL_ORDER' OR released_reservation_count <> expected_reservation_count))
   OR (current_status = 'CANCELLING_ORDER'
       AND (active_step <> 'CANCEL_ORDER' OR released_reservation_count <> expected_reservation_count))
   OR (current_status = 'COMPLETED'
       AND (active_step <> 'NONE' OR released_reservation_count <> expected_reservation_count
            OR error_code IS NOT NULL OR error_message IS NOT NULL OR next_retry_at IS NOT NULL))
UNION ALL
SELECT 'canonical_cancellation_saga_exact_order_item_link', COUNT(*)
FROM (
  SELECT reservation.tenant_id, reservation.saga_id, reservation.order_item_id, reservation.reservation_id
  FROM (SELECT * FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_reservation_event WHERE schema_version = 1) reservation
  JOIN yshopping_dim.dim_canonical_order_cancellation_saga_current saga
    ON saga.tenant_id = reservation.tenant_id
   AND saga.saga_id = reservation.saga_id
   AND saga.aggregate_version = reservation.aggregate_version
  LEFT JOIN yshopping_dws.dws_canonical_order_item_current item
    ON item.tenant_id = reservation.tenant_id
   AND item.order_id = reservation.order_id
   AND item.order_item_id = reservation.order_item_id
   AND item.reservation_id = reservation.reservation_id
   AND item.quantity = reservation.quantity
  WHERE item.order_item_id IS NULL
) missing_link
UNION ALL
SELECT 'canonical_cancellation_saga_exact_inventory_link', COUNT(*)
FROM yshopping_dws.dws_canonical_order_cancellation_saga_current
WHERE exact_reservation_fact_count <> expected_reservation_count
   OR order_reservation_fact_count <> expected_reservation_count
   OR (saga_status IN ('RESERVATIONS_RELEASED', 'CANCELLING_ORDER', 'COMPLETED')
       AND exact_release_fact_count <> expected_reservation_count)
   OR order_release_fact_count > expected_reservation_count
UNION ALL
SELECT 'canonical_cancellation_saga_release_before_cancel', COUNT(*)
FROM yshopping_dws.dws_canonical_order_cancellation_saga_current
WHERE order_status = 'CANCELLED'
  AND (exact_release_fact_count <> expected_reservation_count OR all_releases_before_cancel <> TRUE)
UNION ALL
SELECT 'canonical_cancellation_saga_order_terminal_shape', COUNT(*)
FROM yshopping_dws.dws_canonical_order_cancellation_saga_current
WHERE saga_status = 'COMPLETED'
  AND (order_previous_status <> 'CANCELLATION_PENDING'
       OR order_pre_cancellation_status <> 'INVENTORY_RESERVED'
       OR order_status <> 'CANCELLED'
       OR order_cancellation_saga_id IS NULL OR order_cancellation_saga_id <> saga_id
       OR order_cancelled_recorded_at IS NULL
       OR order_cancelled_recorded_at > saga_recorded_at)
UNION ALL
SELECT 'canonical_cancellation_saga_no_money_or_fulfillment', COUNT(*)
FROM yshopping_dws.dws_canonical_order_cancellation_saga_current
WHERE payment_fact_count <> 0 OR fulfillment_fact_count <> 0
UNION ALL
SELECT 'canonical_cancellation_saga_completed_reconciled', COUNT(*)
FROM yshopping_ads.ads_canonical_order_cancellation_saga_readiness
WHERE saga_status = 'COMPLETED' AND readiness_status <> 'RECONCILED'
UNION ALL
SELECT 'canonical_cancellation_saga_recovery_not_reconciled', COUNT(*)
FROM yshopping_ads.ads_canonical_order_cancellation_saga_readiness
WHERE saga_status IN ('RETRY_SCHEDULED', 'MANUAL_REVIEW') AND readiness_status = 'RECONCILED';
