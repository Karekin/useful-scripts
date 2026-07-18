CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_buyer_csat_readiness AS
SELECT tenant_id,
       touchpoint_code,
       COUNT(*) AS feedback_ticket_count,
       SUM(valid_feedback_count) AS valid_feedback_count,
       SUM(satisfied_feedback_count) AS satisfied_feedback_count,
       SUM(neutral_feedback_count) AS neutral_feedback_count,
       SUM(dissatisfied_feedback_count) AS dissatisfied_feedback_count,
       CASE
           WHEN SUM(valid_feedback_count) = 0 THEN NULL
           ELSE CAST(100.0 * SUM(satisfied_feedback_count) / SUM(valid_feedback_count) AS DECIMAL(18,6))
       END AS csat_rate_percent,
       MAX(data_freshness_at) AS data_freshness_at,
       'CANONICAL_BUYER_FEEDBACK_FIRST_SLICE' AS model_semantics
FROM yshopping_dws.dws_canonical_customer_service_buyer_csat_current
GROUP BY tenant_id, touchpoint_code;
