CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_listing_unpublish_readiness AS
SELECT
    saga.*,
    CASE
        WHEN source_event_matches <> TRUE
          OR unpublished_listing_count + skipped_listing_count > expected_listing_count
          OR actual_unpublish_event_count <> actual_unpublished_listing_count
          OR actual_unpublished_listing_count > unpublished_listing_count
        THEN 'INCONSISTENT'
        WHEN current_status = 'COMPLETED'
         AND active_step = 'NONE'
         AND unpublished_listing_count + skipped_listing_count = expected_listing_count
         AND actual_unpublished_listing_count = unpublished_listing_count
         AND source_event_recorded_at <= recorded_at
         AND (last_unpublished_recorded_at IS NULL OR last_unpublished_recorded_at <= recorded_at)
        THEN 'RECONCILED'
        WHEN current_status = 'COMPLETED' THEN 'INCONSISTENT'
        WHEN current_status = 'MANUAL_REVIEW' THEN 'RECOVERY_REQUIRED'
        WHEN current_status = 'RETRY_SCHEDULED' THEN 'RECOVERY_PENDING'
        ELSE 'IN_PROGRESS'
    END AS readiness_status,
    CASE
        WHEN current_status = 'COMPLETED' AND recovered_after_failure = TRUE THEN 'RECOVERED'
        WHEN current_status = 'COMPLETED' THEN 'NOT_REQUIRED'
        WHEN current_status = 'MANUAL_REVIEW' THEN 'REQUIRED'
        WHEN current_status = 'RETRY_SCHEDULED' THEN 'PENDING'
        ELSE 'NOT_REQUIRED'
    END AS recovery_status
FROM yshopping_dws.dws_canonical_listing_unpublish_saga_current saga;
