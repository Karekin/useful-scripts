CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_token_principal_usage_1d AS
SELECT tenant_id, principal_id, DATE_FORMAT(occurred_at, '%Y-%m-%d') AS date_id,
       COUNT(*) AS request_count,
       SUM(CASE WHEN result_status = 'SUCCEEDED' THEN 1 ELSE 0 END) AS succeeded_count,
       SUM(CASE WHEN result_status = 'FAILED' THEN 1 ELSE 0 END) AS failed_count,
       SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens, SUM(total_tokens) AS total_tokens,
       SUM(quota_cost_microunits) AS quota_cost_microunits, AVG(duration_millis) AS average_duration_millis
FROM yshopping_dwd.dwd_canonical_token_invocation_usage_event
GROUP BY tenant_id, principal_id, DATE_FORMAT(occurred_at, '%Y-%m-%d');

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_token_model_usage_1h AS
SELECT tenant_id, offering_id, provider_code, model_code, DATE_FORMAT(occurred_at, '%Y-%m-%d %H:00:00') AS hour_id,
       COUNT(*) AS request_count,
       SUM(CASE WHEN result_status = 'SUCCEEDED' THEN 1 ELSE 0 END) AS succeeded_count,
       SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens, SUM(total_tokens) AS total_tokens,
       SUM(quota_cost_microunits) AS quota_cost_microunits, AVG(duration_millis) AS average_duration_millis
FROM yshopping_dwd.dwd_canonical_token_invocation_usage_event
GROUP BY tenant_id, offering_id, provider_code, model_code, DATE_FORMAT(occurred_at, '%Y-%m-%d %H:00:00');
