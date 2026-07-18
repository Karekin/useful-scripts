SELECT 'customer_service_buyer_feedback_orphan_ticket' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_customer_service_buyer_feedback_event feedback
LEFT JOIN yshopping_dim.dim_canonical_customer_service_ticket_current ticket
  ON ticket.tenant_id = feedback.tenant_id
 AND ticket.ticket_id = feedback.ticket_id
WHERE ticket.ticket_id IS NULL;

SELECT 'customer_service_buyer_feedback_identity_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_customer_service_buyer_feedback_event feedback
JOIN yshopping_dim.dim_canonical_customer_service_ticket_current ticket
  ON ticket.tenant_id = feedback.tenant_id
 AND ticket.ticket_id = feedback.ticket_id
WHERE feedback.customer_principal_id <> ticket.customer_principal_id;

SELECT 'customer_service_buyer_feedback_score_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_customer_service_buyer_feedback_event
WHERE (sentiment_code = 'SATISFIED' AND score_basis_points <> 10000)
   OR (sentiment_code = 'NEUTRAL' AND score_basis_points <> 5000)
   OR (sentiment_code = 'DISSATISFIED' AND score_basis_points <> 0);

SELECT 'customer_service_service_metrics_fcr_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_customer_service_service_metrics_current
WHERE fcr_success_flag = 1 AND fcr_eligible_flag <> 1;

SELECT 'customer_service_service_metrics_sla_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_customer_service_service_metrics_current
WHERE resolution_sla_met_flag = 1 AND resolution_sla_eligible_flag <> 1;

SELECT 'customer_service_buyer_csat_semantics_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_buyer_csat_readiness
WHERE model_semantics <> 'CANONICAL_BUYER_FEEDBACK_FIRST_SLICE';

SELECT 'customer_service_service_metrics_semantics_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_customer_service_service_metrics_readiness
WHERE model_semantics <> 'CANONICAL_CUSTOMER_SERVICE_EXPERIENCE_FIRST_SLICE';
