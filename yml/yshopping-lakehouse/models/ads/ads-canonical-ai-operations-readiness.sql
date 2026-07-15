CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_ai_operations_readiness AS
SELECT tenant_id,
       COUNT(*) AS run_count,
       SUM(CASE WHEN current_status IN ('SUCCEEDED', 'FAILED', 'CANCELLED') THEN 1 ELSE 0 END) AS terminal_run_count,
       SUM(CASE WHEN current_status IN ('SUCCEEDED', 'FAILED', 'CANCELLED') AND expected_invocation_count <> invocation_count THEN 1 ELSE 0 END) AS invocation_count_mismatch_count,
       SUM(total_tokens) AS total_tokens,
       SUM(known_cost_amount_minor) AS known_cost_amount_minor,
       SUM(unpriced_invocation_count) AS unpriced_invocation_count,
       SUM(feedback_count) AS feedback_count,
       CASE
         WHEN SUM(CASE WHEN current_status IN ('SUCCEEDED', 'FAILED', 'CANCELLED') AND expected_invocation_count <> invocation_count THEN 1 ELSE 0 END) > 0 THEN 'INCONSISTENT'
         WHEN COUNT(*) = 0 THEN 'NO_EVIDENCE'
         ELSE 'FIRST_SLICE_RECONCILED'
       END AS readiness_status
FROM yshopping_dws.dws_canonical_ai_workflow_run_current
GROUP BY tenant_id;
