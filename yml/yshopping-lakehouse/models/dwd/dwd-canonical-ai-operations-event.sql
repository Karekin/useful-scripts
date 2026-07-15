-- Canonical AI Operations first slice. Raw prompts, responses, workflow graphs and credentials are intentionally absent.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_ai_application_event AS
SELECT event_id, tenant_id, aggregate_id AS application_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.application_code') AS application_code,
       get_json_string(payload, '$.name') AS application_name,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.operation') AS operation
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'ai.application.status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-ai-operations';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_ai_workflow_version_event AS
SELECT event_id, tenant_id, aggregate_id AS workflow_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.workflow_code') AS workflow_code,
       get_json_string(payload, '$.application_id') AS application_id,
       CAST(get_json_string(payload, '$.workflow_version') AS BIGINT) AS workflow_version,
       get_json_string(payload, '$.definition_sha256') AS definition_sha256,
       CAST(get_json_string(payload, '$.published_at') AS DATETIME) AS published_at,
       get_json_string(payload, '$.operation') AS operation
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'ai.workflow.version.published' AND schema_version = 1
  AND source_system = 'cloudmold-ai-operations';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_ai_workflow_run_event AS
SELECT event_id, tenant_id, aggregate_id AS run_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.application_id') AS application_id,
       get_json_string(payload, '$.workflow_id') AS workflow_id,
       CAST(get_json_string(payload, '$.workflow_version') AS BIGINT) AS workflow_version,
       get_json_string(payload, '$.trigger_type') AS trigger_type,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       CAST(get_json_string(payload, '$.expected_invocation_count') AS BIGINT) AS expected_invocation_count,
       CAST(get_json_string(payload, '$.started_at') AS DATETIME) AS started_at,
       CAST(get_json_string(payload, '$.finished_at') AS DATETIME) AS finished_at,
       get_json_string(payload, '$.error_code') AS error_code,
       get_json_string(payload, '$.operation') AS operation
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'ai.workflow.run.status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-ai-operations';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_ai_model_invocation_event AS
SELECT event_id, tenant_id, aggregate_id AS attempt_id, aggregate_version, occurred_at AS event_occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.run_id') AS run_id,
       get_json_string(payload, '$.application_id') AS application_id,
       get_json_string(payload, '$.workflow_id') AS workflow_id,
       get_json_string(payload, '$.provider_code') AS provider_code,
       get_json_string(payload, '$.model_code') AS model_code,
       CAST(get_json_string(payload, '$.attempt_no') AS BIGINT) AS attempt_no,
       get_json_string(payload, '$.outcome') AS outcome,
       CAST(get_json_string(payload, '$.input_tokens') AS BIGINT) AS input_tokens,
       CAST(get_json_string(payload, '$.cached_input_tokens') AS BIGINT) AS cached_input_tokens,
       CAST(get_json_string(payload, '$.output_tokens') AS BIGINT) AS output_tokens,
       CAST(get_json_string(payload, '$.total_tokens') AS BIGINT) AS total_tokens,
       CAST(get_json_string(payload, '$.latency_millis') AS BIGINT) AS latency_millis,
       CAST(get_json_string(payload, '$.cost_amount_minor') AS BIGINT) AS cost_amount_minor,
       get_json_string(payload, '$.currency_code') AS currency_code,
       get_json_string(payload, '$.pricing_version_ref') AS pricing_version_ref,
       get_json_string(payload, '$.error_code') AS error_code,
       CAST(get_json_string(payload, '$.occurred_at') AS DATETIME) AS occurred_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'ai.model.invocation.recorded' AND schema_version = 1
  AND source_system = 'cloudmold-ai-operations';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_ai_outcome_feedback_event AS
SELECT event_id, tenant_id, aggregate_id AS feedback_id, aggregate_version, occurred_at AS event_occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.run_id') AS run_id,
       get_json_string(payload, '$.feedback_type') AS feedback_type,
       get_json_string(payload, '$.outcome_code') AS outcome_code,
       get_json_string(payload, '$.evaluator_type') AS evaluator_type,
       CAST(get_json_string(payload, '$.occurred_at') AS DATETIME) AS occurred_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'ai.outcome.feedback.recorded' AND schema_version = 1
  AND source_system = 'cloudmold-ai-operations';
