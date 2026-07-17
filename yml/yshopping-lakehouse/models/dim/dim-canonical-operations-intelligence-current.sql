CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_intelligence_observation_current AS
SELECT event_id, tenant_id, observation_id, aggregate_version, event_occurred_at, recorded_at, source_system,
       source_event_id, observation_type, subject_type, subject_ref, evidence_ref, content_sha256, observed_at
FROM (
    SELECT e.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, observation_id
           ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_intelligence_observation_event e
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_intelligence_model_result_current AS
SELECT event_id, tenant_id, model_result_id, aggregate_version, occurred_at, recorded_at, observation_id,
       invocation_attempt_ref, model_version_ref, outcome_code, score_basis_points, retry_no, evidence_ref, result_sha256
FROM (
    SELECT e.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, model_result_id
           ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_intelligence_model_result_event e
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_intelligence_clue_current AS
SELECT clue.event_id, clue.tenant_id, clue.clue_id,
       COALESCE(review.aggregate_version, clue.aggregate_version) AS aggregate_version,
       clue.observation_id, clue.model_result_id, clue.clue_type, clue.source_code, clue.source_published_at,
       clue.evidence_ref, clue.evidence_sha256, COALESCE(review.current_status, clue.current_status) AS current_status,
       review.review_id, review.decision, review.reason_code, review.reviewer_principal_id,
       clue.recorded_at AS observed_recorded_at, review.recorded_at AS reviewed_recorded_at
FROM (
    SELECT e.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, clue_id ORDER BY recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_intelligence_clue_event e
) clue
LEFT JOIN (
    SELECT e.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, clue_id
           ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_intelligence_clue_review_event e
) review ON review.tenant_id = clue.tenant_id AND review.clue_id = clue.clue_id AND review.rn = 1
WHERE clue.rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_operations_alert_current AS
SELECT event_id, tenant_id, alert_id, aggregate_version, occurred_at, recorded_at, alert_code, source_type,
       source_ref, severity, category, subcategory, evidence_ref, title_sha256, previous_status, current_status,
       actor_principal_id, reason_code, operation, alert_event_count
FROM (
    SELECT e.*, COUNT(*) OVER (PARTITION BY tenant_id, alert_id) AS alert_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, alert_id
             ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_operations_alert_event e
) ranked WHERE rn = 1;
