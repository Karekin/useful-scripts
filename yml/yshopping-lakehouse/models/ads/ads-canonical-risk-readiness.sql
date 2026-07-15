CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_risk_readiness AS
SELECT tenant_id,
       COUNT(*) AS review_case_count,
       SUM(CASE WHEN cluster_id IS NULL OR cluster_code IS NULL THEN 1 ELSE 0 END) AS orphan_review_count,
       SUM(CASE WHEN review_status IN ('DECIDED', 'CLOSED') AND decision_count = 0 THEN 1 ELSE 0 END) AS terminal_without_decision_count,
       SUM(decision_count) AS decision_count,
       SUM(feedback_count) AS feedback_count,
       SUM(corrective_feedback_count) AS corrective_feedback_count,
       CASE
         WHEN SUM(CASE WHEN cluster_id IS NULL OR cluster_code IS NULL OR (review_status IN ('DECIDED', 'CLOSED') AND decision_count = 0) THEN 1 ELSE 0 END) > 0 THEN 'INCONSISTENT'
         ELSE 'HUMAN_REVIEW_FIRST_SLICE_READY'
       END AS readiness_status,
       false AS automatic_enforcement_enabled
FROM yshopping_dws.dws_canonical_risk_review_current
GROUP BY tenant_id;
