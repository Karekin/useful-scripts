CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_customer_service_buyer_csat_current AS
SELECT latest.tenant_id,
       latest.ticket_id,
       ticket.ticket_no,
       latest.customer_principal_id,
       latest.touchpoint_code,
       ticket.channel_code,
       ticket.priority,
       ticket.category_code,
       ticket.current_status,
       ticket.primary_order_ref,
       ticket.primary_after_sale_ref,
       aggregate.feedback_count,
       aggregate.valid_feedback_count,
       aggregate.satisfied_feedback_count,
       aggregate.neutral_feedback_count,
       aggregate.dissatisfied_feedback_count,
       latest.feedback_id AS latest_feedback_id,
       latest.sentiment_code AS latest_sentiment_code,
       latest.score_basis_points AS latest_score_basis_points,
       latest.reason_code AS latest_reason_code,
       latest.occurred_at AS latest_feedback_at,
       GREATEST(aggregate.data_freshness_at, ticket.recorded_at) AS data_freshness_at
FROM (
    SELECT tenant_id,
           ticket_id,
           touchpoint_code,
           customer_principal_id,
           COUNT(*) AS feedback_count,
           COUNT(*) AS valid_feedback_count,
           SUM(CASE WHEN sentiment_code = 'SATISFIED' THEN 1 ELSE 0 END) AS satisfied_feedback_count,
           SUM(CASE WHEN sentiment_code = 'NEUTRAL' THEN 1 ELSE 0 END) AS neutral_feedback_count,
           SUM(CASE WHEN sentiment_code = 'DISSATISFIED' THEN 1 ELSE 0 END) AS dissatisfied_feedback_count,
           MAX(recorded_at) AS data_freshness_at
    FROM yshopping_dim.dim_canonical_customer_service_buyer_feedback_current
    GROUP BY tenant_id, ticket_id, touchpoint_code, customer_principal_id
) aggregate
JOIN (
    SELECT *
    FROM (
        SELECT feedback.*,
               ROW_NUMBER() OVER (
                   PARTITION BY tenant_id, ticket_id, touchpoint_code, customer_principal_id
                   ORDER BY occurred_at DESC, recorded_at DESC, feedback_id DESC
               ) AS row_num
        FROM yshopping_dim.dim_canonical_customer_service_buyer_feedback_current feedback
    ) ranked
    WHERE row_num = 1
) latest
  ON latest.tenant_id = aggregate.tenant_id
 AND latest.ticket_id = aggregate.ticket_id
 AND latest.touchpoint_code = aggregate.touchpoint_code
 AND latest.customer_principal_id = aggregate.customer_principal_id
JOIN yshopping_dim.dim_canonical_customer_service_ticket_current ticket
  ON ticket.tenant_id = latest.tenant_id
 AND ticket.ticket_id = latest.ticket_id;
