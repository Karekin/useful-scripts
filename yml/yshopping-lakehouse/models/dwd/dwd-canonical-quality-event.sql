CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_quality_event AS
SELECT
    event_id,
    event_type,
    schema_version,
    tenant_id,
    aggregate_type,
    aggregate_id,
    aggregate_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.standard_id') AS standard_id,
    get_json_string(payload, '$.standard_code') AS standard_code,
    CAST(get_json_string(payload, '$.standard_version') AS BIGINT) AS standard_version,
    get_json_string(payload, '$.standard_version_id') AS standard_version_id,
    get_json_string(payload, '$.category_code') AS category_code,
    get_json_string(payload, '$.brand_code') AS brand_code,
    get_json_string(payload, '$.applicable_sku_id') AS applicable_sku_id,
    get_json_string(payload, '$.content_sha256') AS content_sha256,
    get_json_string(payload, '$.certification_id') AS certification_id,
    get_json_string(payload, '$.authenticator_principal_id')
        AS authenticator_principal_id,
    get_json_string(payload, '$.certification_level') AS certification_level,
    get_json_string(payload, '$.effective_from') AS effective_from,
    get_json_string(payload, '$.effective_to') AS effective_to,
    get_json_string(payload, '$.task_id') AS task_id,
    get_json_string(payload, '$.subject_type') AS subject_type,
    get_json_string(payload, '$.subject_ref') AS subject_ref,
    get_json_string(payload, '$.canonical_sku_id') AS canonical_sku_id,
    get_json_string(payload, '$.lot_id') AS lot_id,
    get_json_string(payload, '$.warehouse_id') AS warehouse_id,
    get_json_string(payload, '$.priority') AS priority,
    get_json_string(payload, '$.decision') AS decision,
    get_json_string(payload, '$.defect_code') AS defect_code,
    get_json_string(payload, '$.evidence_ref') AS evidence_ref,
    get_json_string(payload, '$.recheck_reason_code') AS recheck_reason_code,
    get_json_string(payload, '$.previous_status') AS previous_status,
    COALESCE(
        get_json_string(payload, '$.current_status'),
        CASE event_type
            WHEN 'quality.standard.created' THEN 'DRAFT'
            WHEN 'quality.standard.published' THEN 'PUBLISHED'
            WHEN 'quality.authenticator.certified' THEN 'ACTIVE'
            WHEN 'quality.authenticator.certification.revoked' THEN 'REVOKED'
            WHEN 'quality.capa.opened' THEN 'OPEN'
            WHEN 'quality.capa.verified' THEN 'VERIFIED'
        END
    ) AS current_status,
    get_json_string(payload, '$.capa_id') AS capa_id,
    get_json_string(payload, '$.inspection_task_id') AS inspection_task_id,
    get_json_string(payload, '$.root_cause_code') AS root_cause_code,
    get_json_string(payload, '$.owner_principal_id') AS owner_principal_id,
    get_json_string(payload, '$.due_date') AS due_date,
    get_json_string(payload, '$.effectiveness_evidence_ref')
        AS effectiveness_evidence_ref
    ,get_json_string(payload, '$.secondary_authenticator_principal_id')
        AS secondary_authenticator_principal_id
    ,get_json_string(payload, '$.secondary_decision') AS secondary_decision
    ,get_json_string(payload, '$.secondary_defect_code') AS secondary_defect_code
    ,get_json_string(payload, '$.secondary_evidence_ref') AS secondary_evidence_ref
    ,get_json_string(payload, '$.adjudicator_principal_id') AS adjudicator_principal_id
    ,get_json_string(payload, '$.ground_truth_decision') AS ground_truth_decision
    ,get_json_string(payload, '$.ground_truth_defect_code') AS ground_truth_defect_code
    ,get_json_string(payload, '$.ground_truth_evidence_ref') AS ground_truth_evidence_ref
    ,get_json_string(payload, '$.recall_action_id') AS recall_action_id
    ,get_json_string(payload, '$.reason_code') AS recall_reason_code
    ,get_json_string(payload, '$.resolution_code') AS recall_resolution_code
FROM yshopping_dwd.dwd_domain_event
WHERE source_system = 'cloudmold-quality'
  AND schema_version = 1
  AND event_type LIKE 'quality.%';
