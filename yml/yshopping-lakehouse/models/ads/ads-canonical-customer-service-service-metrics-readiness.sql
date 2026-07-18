CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_customer_service_service_metrics_readiness AS
SELECT tenant_id,
       COUNT(*) AS ticket_count,
       SUM(CASE WHEN first_resolved_at IS NOT NULL THEN 1 ELSE 0 END) AS resolved_ticket_count,
       SUM(valid_feedback_count) AS valid_feedback_count,
       SUM(satisfied_feedback_count) AS satisfied_feedback_count,
       SUM(CASE WHEN resolution_sla_eligible_flag = 1 THEN 1 ELSE 0 END) AS resolution_sla_eligible_ticket_count,
       SUM(CASE WHEN resolution_sla_met_flag = 1 THEN 1 ELSE 0 END) AS resolution_sla_met_ticket_count,
       SUM(CASE WHEN fcr_eligible_flag = 1 THEN 1 ELSE 0 END) AS fcr_eligible_ticket_count,
       SUM(CASE WHEN fcr_success_flag = 1 THEN 1 ELSE 0 END) AS fcr_success_ticket_count,
       SUM(CASE WHEN order_defect_case_flag = 1 THEN 1 ELSE 0 END) AS order_defect_case_count,
       CASE
           WHEN SUM(valid_feedback_count) = 0 THEN NULL
           ELSE CAST(100.0 * SUM(satisfied_feedback_count) / SUM(valid_feedback_count) AS DECIMAL(18,6))
       END AS csat_rate_percent,
       CASE
           WHEN SUM(CASE WHEN resolution_sla_eligible_flag = 1 THEN 1 ELSE 0 END) = 0 THEN NULL
           ELSE CAST(
               100.0 * SUM(CASE WHEN resolution_sla_met_flag = 1 THEN 1 ELSE 0 END)
               / SUM(CASE WHEN resolution_sla_eligible_flag = 1 THEN 1 ELSE 0 END)
               AS DECIMAL(18,6)
           )
       END AS resolution_sla_rate_percent,
       CASE
           WHEN SUM(CASE WHEN fcr_eligible_flag = 1 THEN 1 ELSE 0 END) = 0 THEN NULL
           ELSE CAST(
               100.0 * SUM(CASE WHEN fcr_success_flag = 1 THEN 1 ELSE 0 END)
               / SUM(CASE WHEN fcr_eligible_flag = 1 THEN 1 ELSE 0 END)
               AS DECIMAL(18,6)
           )
       END AS first_contact_resolution_rate_percent,
       CASE
           WHEN SUM(CASE WHEN primary_order_ref IS NOT NULL THEN 1 ELSE 0 END) = 0 THEN NULL
           ELSE CAST(
               100.0 * SUM(CASE WHEN order_defect_case_flag = 1 THEN 1 ELSE 0 END)
               / SUM(CASE WHEN primary_order_ref IS NOT NULL THEN 1 ELSE 0 END)
               AS DECIMAL(18,6)
           )
       END AS order_defect_case_rate_percent,
       MAX(data_freshness_at) AS data_freshness_at,
       'CANONICAL_CUSTOMER_SERVICE_EXPERIENCE_FIRST_SLICE' AS model_semantics,
       CASE
           WHEN SUM(CASE WHEN primary_order_ref IS NOT NULL THEN 1 ELSE 0 END) = 0
             THEN 'PARTIAL_REQUIRES_ORDER_DENOMINATOR'
           ELSE 'READY_FOR_ORDER_LINKED_PROXY'
       END AS readiness_status
FROM yshopping_dws.dws_canonical_customer_service_service_metrics_current
GROUP BY tenant_id;
