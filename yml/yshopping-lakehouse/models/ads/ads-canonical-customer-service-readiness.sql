CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_customer_service_readiness AS
SELECT tenant_id,
       COUNT(*) AS ticket_count,
       SUM(CASE WHEN current_status IN ('OPEN','IN_PROGRESS') THEN 1 ELSE 0 END) AS open_ticket_count,
       SUM(message_count) AS message_count,
       SUM(attachment_count) AS attachment_count,
       SUM(unsafe_attachment_count) AS unsafe_attachment_count,
       SUM(review_count) AS review_count,
       SUM(claim_count) AS claim_count,
       SUM(open_claim_count) AS open_claim_count,
       SUM(requested_amount_minor) AS requested_amount_minor,
       SUM(paid_amount_minor) AS paid_amount_minor,
       SUM(CASE WHEN declared_attachment_count <> attachment_count THEN 1 ELSE 0 END)
           AS attachment_count_mismatch_ticket_count,
       SUM(CASE WHEN current_status IN ('RESOLVED','CLOSED') AND review_count = 0 THEN 1 ELSE 0 END)
           AS resolved_without_review_ticket_count,
       CASE
         WHEN SUM(unsafe_attachment_count) > 0 THEN 'ATTACHMENT_NOT_CLEAN'
         WHEN SUM(CASE WHEN declared_attachment_count <> attachment_count THEN 1 ELSE 0 END) > 0
           THEN 'ATTACHMENT_COUNT_MISMATCH'
         ELSE 'READY'
       END AS readiness_status,
       MAX(data_freshness_at) AS data_freshness_at,
       'CANONICAL_CUSTOMER_SERVICE_PII_SAFE_FIRST_SLICE' AS model_semantics
FROM yshopping_dws.dws_canonical_customer_service_ticket_current GROUP BY tenant_id;
