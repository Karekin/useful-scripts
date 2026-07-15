CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_listing_unpublish_saga_current AS
WITH history AS (
    SELECT tenant_id, saga_id,
           COUNT(*) AS saga_event_count,
           SUM(IF(current_status = 'RETRY_SCHEDULED', 1, 0)) AS retry_event_count,
           SUM(IF(current_status = 'MANUAL_REVIEW', 1, 0)) AS manual_review_event_count,
           MAX(attempt) AS max_attempt,
           MIN(IF(current_status IN ('RETRY_SCHEDULED', 'MANUAL_REVIEW'), occurred_at, NULL))
             AS first_recovery_at
    FROM yshopping_dwd.dwd_canonical_listing_unpublish_saga_event
    GROUP BY tenant_id, saga_id
), latest AS (
    SELECT event.*,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, saga_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_listing_unpublish_saga_event event
)
SELECT
    latest.event_id, latest.schema_version, latest.tenant_id, latest.saga_id, latest.payload_saga_id,
    latest.aggregate_version, latest.run_id, latest.source_event_id, latest.source_entity_type,
    latest.source_aggregate_version, latest.merchant_id, latest.shop_id,
    latest.previous_status, latest.current_status, latest.active_step, latest.attempt, latest.reason,
    latest.expected_listing_count, latest.unpublished_listing_count, latest.skipped_listing_count,
    latest.error_code, latest.error_message, latest.next_retry_at,
    latest.correlation_id, latest.causation_id, latest.occurred_at, latest.recorded_at,
    history.saga_event_count, history.retry_event_count, history.manual_review_event_count,
    history.max_attempt, history.first_recovery_at,
    latest.current_status = 'COMPLETED'
      AND (history.retry_event_count > 0 OR history.manual_review_event_count > 0)
      AS recovered_after_failure
FROM latest
JOIN history
  ON history.tenant_id = latest.tenant_id AND history.saga_id = latest.saga_id
WHERE latest.row_num = 1;
