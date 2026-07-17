-- Governed operations-intelligence events. Raw source content is excluded by contract.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_intelligence_observation_event AS
SELECT event_id, tenant_id, aggregate_id AS observation_id, aggregate_version, occurred_at AS event_occurred_at,
       recorded_at, correlation_id, causation_id, idempotency_key, schema_version,
       get_json_string(payload, '$.source_system') AS source_system,
       get_json_string(payload, '$.source_event_id') AS source_event_id,
       get_json_string(payload, '$.observation_type') AS observation_type,
       CAST(COALESCE(get_json_string(payload, '$.classification_contract_version'), '1') AS BIGINT)
           AS classification_contract_version,
       get_json_string(payload, '$.taxonomy_id') AS taxonomy_id,
       get_json_string(payload, '$.taxonomy_version_id') AS taxonomy_version_id,
       CAST(get_json_string(payload, '$.taxonomy_definition_version') AS BIGINT) AS taxonomy_definition_version,
       get_json_string(payload, '$.event_code') AS event_code,
       get_json_string(payload, '$.intelligence_level_code') AS intelligence_level_code,
       get_json_string(payload, '$.subject_type') AS subject_type,
       get_json_string(payload, '$.subject_ref') AS subject_ref,
       get_json_string(payload, '$.evidence_ref') AS evidence_ref,
       get_json_string(payload, '$.content_sha256') AS content_sha256,
       CAST(get_json_string(payload, '$.observed_at') AS DATETIME) AS observed_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'operations_intelligence.observation.recorded' AND schema_version IN (1, 2)
  AND source_system = 'cloudmold-operations-intelligence';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_intelligence_model_result_event AS
SELECT event_id, tenant_id, aggregate_id AS model_result_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.observation_id') AS observation_id,
       get_json_string(payload, '$.invocation_attempt_ref') AS invocation_attempt_ref,
       get_json_string(payload, '$.model_version_ref') AS model_version_ref,
       get_json_string(payload, '$.outcome_code') AS outcome_code,
       CAST(get_json_string(payload, '$.score_basis_points') AS BIGINT) AS score_basis_points,
       CAST(get_json_string(payload, '$.retry_no') AS BIGINT) AS retry_no,
       get_json_string(payload, '$.evidence_ref') AS evidence_ref,
       get_json_string(payload, '$.result_sha256') AS result_sha256
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'operations_intelligence.model_result.recorded' AND schema_version = 1
  AND source_system = 'cloudmold-operations-intelligence';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_intelligence_clue_event AS
SELECT event_id, tenant_id, aggregate_id AS clue_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.observation_id') AS observation_id,
       get_json_string(payload, '$.model_result_id') AS model_result_id,
       get_json_string(payload, '$.clue_type') AS clue_type,
       get_json_string(payload, '$.source_code') AS source_code,
       CAST(get_json_string(payload, '$.source_published_at') AS DATETIME) AS source_published_at,
       get_json_string(payload, '$.evidence_ref') AS evidence_ref,
       get_json_string(payload, '$.evidence_sha256') AS evidence_sha256,
       get_json_string(payload, '$.current_status') AS current_status
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'operations_intelligence.clue.recorded' AND schema_version = 1
  AND source_system = 'cloudmold-operations-intelligence';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_intelligence_clue_review_event AS
SELECT event_id, tenant_id, aggregate_id AS clue_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.review_id') AS review_id,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.decision') AS decision,
       get_json_string(payload, '$.reason_code') AS reason_code,
       get_json_string(payload, '$.reviewer_principal_id') AS reviewer_principal_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'operations_intelligence.clue.reviewed' AND schema_version = 1
  AND source_system = 'cloudmold-operations-intelligence';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_operations_alert_event AS
SELECT event_id, tenant_id, aggregate_id AS alert_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.alert_code') AS alert_code,
       get_json_string(payload, '$.source_type') AS source_type,
       get_json_string(payload, '$.source_ref') AS source_ref,
       get_json_string(payload, '$.severity') AS severity,
       get_json_string(payload, '$.category') AS category,
       get_json_string(payload, '$.subcategory') AS subcategory,
       get_json_string(payload, '$.evidence_ref') AS evidence_ref,
       get_json_string(payload, '$.title_sha256') AS title_sha256,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.actor_principal_id') AS actor_principal_id,
       get_json_string(payload, '$.reason_code') AS reason_code,
       get_json_string(payload, '$.operation') AS operation
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'operations_intelligence.alert.status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-operations-intelligence';
