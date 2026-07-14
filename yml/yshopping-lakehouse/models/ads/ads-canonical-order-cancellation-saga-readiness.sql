CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_order_cancellation_saga_readiness AS
SELECT
    saga.*,
    CASE
        WHEN payment_fact_count <> 0 OR fulfillment_fact_count <> 0
          OR (order_status IN ('CANCELLATION_PENDING', 'CANCELLED')
              AND (order_cancellation_saga_id IS NULL OR order_cancellation_saga_id <> saga_id))
          OR declared_reservation_row_count <> declared_reservation_count
          OR declared_reservation_count <> expected_reservation_count
          OR matched_order_item_reservation_count <> expected_reservation_count
          OR exact_reservation_fact_count <> expected_reservation_count
          OR order_reservation_fact_count <> expected_reservation_count
          OR order_release_fact_count > expected_reservation_count
          OR (order_status = 'CANCELLED'
              AND (exact_release_fact_count <> expected_reservation_count
                   OR all_releases_before_cancel <> TRUE))
        THEN 'INCONSISTENT'
        WHEN saga_status = 'COMPLETED'
         AND order_status = 'CANCELLED'
         AND order_previous_status = 'CANCELLATION_PENDING'
         AND order_pre_cancellation_status = 'INVENTORY_RESERVED'
         AND order_cancellation_saga_id = saga_id
         AND reported_released_reservation_count = expected_reservation_count
         AND order_reservation_fact_count = expected_reservation_count
         AND exact_release_fact_count = expected_reservation_count
         AND order_release_fact_count = expected_reservation_count
         AND all_releases_before_cancel = TRUE
         AND order_cancelled_recorded_at <= saga_recorded_at
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
FROM yshopping_dws.dws_canonical_order_cancellation_saga_current saga;
