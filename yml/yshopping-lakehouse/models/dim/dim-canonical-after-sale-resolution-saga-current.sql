CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_after_sale_resolution_saga_current AS
WITH history AS (
    SELECT tenant_id, saga_id, COUNT(*) AS saga_event_count,
           SUM(IF(current_status = 'RETRY_SCHEDULED', 1, 0)) AS retry_event_count,
           SUM(IF(current_status = 'MANUAL_REVIEW', 1, 0)) AS manual_review_event_count,
           MAX(attempt) AS max_attempt
    FROM yshopping_dwd.dwd_canonical_after_sale_resolution_saga_event
    GROUP BY tenant_id, saga_id
), latest AS (
    SELECT event.*,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, saga_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_after_sale_resolution_saga_event event
)
SELECT latest.* EXCEPT(row_num), history.saga_event_count, history.retry_event_count,
       history.manual_review_event_count, history.max_attempt
FROM latest
JOIN history ON history.tenant_id = latest.tenant_id AND history.saga_id = latest.saga_id
WHERE latest.row_num = 1;
