CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_customer_service_buyer_feedback_current AS
SELECT event_id,
       tenant_id,
       feedback_id,
       aggregate_version,
       event_occurred_at,
       recorded_at,
       correlation_id,
       causation_id,
       idempotency_key,
       run_id,
       ticket_id,
       customer_principal_id,
       touchpoint_code,
       sentiment_code,
       score_basis_points,
       reason_code,
       comment_token,
       occurred_at
FROM (
    SELECT event.*,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, feedback_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_customer_service_buyer_feedback_event event
) ranked
WHERE row_num = 1;
