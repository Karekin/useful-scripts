CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_ai_workflow_run_current AS
SELECT r.tenant_id, r.run_id, r.application_id, r.workflow_id, r.workflow_version, r.trigger_type,
       r.current_status, r.expected_invocation_count, r.started_at, r.finished_at, r.error_code,
       COALESCE(i.invocation_count, 0) AS invocation_count,
       COALESCE(i.succeeded_count, 0) AS succeeded_invocation_count,
       COALESCE(i.failed_count, 0) AS failed_invocation_count,
       COALESCE(i.input_tokens, 0) AS input_tokens,
       COALESCE(i.output_tokens, 0) AS output_tokens,
       COALESCE(i.total_tokens, 0) AS total_tokens,
       COALESCE(i.known_cost_amount_minor, 0) AS known_cost_amount_minor,
       COALESCE(i.unpriced_count, 0) AS unpriced_invocation_count,
       i.currency_code, COALESCE(f.feedback_count, 0) AS feedback_count,
       COALESCE(f.positive_feedback_count, 0) AS positive_feedback_count
FROM yshopping_dim.dim_canonical_ai_workflow_run_current r
LEFT JOIN (
    SELECT tenant_id, run_id, COUNT(*) AS invocation_count,
           SUM(CASE WHEN outcome = 'SUCCEEDED' THEN 1 ELSE 0 END) AS succeeded_count,
           SUM(CASE WHEN outcome = 'FAILED' THEN 1 ELSE 0 END) AS failed_count,
           SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens, SUM(total_tokens) AS total_tokens,
           SUM(COALESCE(cost_amount_minor, 0)) AS known_cost_amount_minor,
           SUM(CASE WHEN cost_amount_minor IS NULL OR currency_code IS NULL THEN 1 ELSE 0 END) AS unpriced_count,
           MIN(currency_code) AS currency_code
    FROM yshopping_dwd.dwd_canonical_ai_model_invocation_event GROUP BY tenant_id, run_id
) i ON i.tenant_id = r.tenant_id AND i.run_id = r.run_id
LEFT JOIN (
    SELECT tenant_id, run_id, COUNT(*) AS feedback_count,
           SUM(CASE WHEN outcome_code = 'POSITIVE' THEN 1 ELSE 0 END) AS positive_feedback_count
    FROM yshopping_dwd.dwd_canonical_ai_outcome_feedback_event GROUP BY tenant_id, run_id
) f ON f.tenant_id = r.tenant_id AND f.run_id = r.run_id;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_ai_application_1d AS
SELECT tenant_id, application_id, DATE_FORMAT(occurred_at, '%Y-%m-%d') AS date_id,
       COUNT(*) AS invocation_count,
       SUM(CASE WHEN outcome = 'SUCCEEDED' THEN 1 ELSE 0 END) AS succeeded_count,
       SUM(CASE WHEN outcome = 'FAILED' THEN 1 ELSE 0 END) AS failed_count,
       SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens, SUM(total_tokens) AS total_tokens,
       AVG(latency_millis) AS average_latency_millis,
       SUM(COALESCE(cost_amount_minor, 0)) AS known_cost_amount_minor,
       SUM(CASE WHEN cost_amount_minor IS NULL OR currency_code IS NULL THEN 1 ELSE 0 END) AS unpriced_count,
       MIN(currency_code) AS currency_code
FROM yshopping_dwd.dwd_canonical_ai_model_invocation_event
GROUP BY tenant_id, application_id, DATE_FORMAT(occurred_at, '%Y-%m-%d');
