-- Canonical risk first slice. Relationship media are tenant-scoped keyed tokens; raw phone/IP/address/device never enter the event layer.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_risk_policy_event AS
SELECT event_id, tenant_id, aggregate_id AS policy_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.policy_code') AS policy_code,
       CAST(get_json_string(payload, '$.policy_version') AS BIGINT) AS policy_version,
       get_json_string(payload, '$.rules_sha256') AS rules_sha256,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.approved_by_principal_id') AS approved_by_principal_id,
       CAST(get_json_string(payload, '$.effective_from') AS DATETIME) AS effective_from,
       get_json_string(payload, '$.operation') AS operation
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'risk.policy.version_published' AND schema_version = 1 AND source_system = 'cloudmold-risk';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_risk_signal_event AS
SELECT event_id, tenant_id, aggregate_id AS signal_id, aggregate_version, occurred_at AS event_occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.subject_principal_id') AS subject_principal_id,
       get_json_string(payload, '$.policy_id') AS policy_id,
       CAST(get_json_string(payload, '$.policy_version') AS BIGINT) AS policy_version,
       get_json_string(payload, '$.signal_type') AS signal_type,
       get_json_string(payload, '$.severity') AS severity,
       get_json_string(payload, '$.evidence_ref') AS evidence_ref,
       CAST(get_json_string(payload, '$.occurred_at') AS DATETIME) AS occurred_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'risk.signal.detected' AND schema_version = 1 AND source_system = 'cloudmold-risk';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_risk_relationship_event AS
SELECT event_id, tenant_id, aggregate_id AS relation_id, aggregate_version, occurred_at AS event_occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.subject_principal_id') AS subject_principal_id,
       get_json_string(payload, '$.related_principal_id') AS related_principal_id,
       get_json_string(payload, '$.medium_type') AS medium_type,
       get_json_string(payload, '$.medium_token') AS medium_token,
       CAST(get_json_string(payload, '$.key_version') AS BIGINT) AS key_version,
       CAST(get_json_string(payload, '$.first_seen_at') AS DATETIME) AS first_seen_at,
       CAST(get_json_string(payload, '$.last_seen_at') AS DATETIME) AS last_seen_at,
       CAST(get_json_string(payload, '$.confidence_basis_points') AS BIGINT) AS confidence_basis_points
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'risk.relationship.observed' AND schema_version = 1 AND source_system = 'cloudmold-risk';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_risk_cluster_event AS
SELECT event_id, tenant_id, aggregate_id AS cluster_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.cluster_code') AS cluster_code,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.risk_level') AS risk_level,
       CAST(get_json_string(payload, '$.member_count') AS BIGINT) AS member_count,
       CAST(get_json_string(payload, '$.edge_count') AS BIGINT) AS edge_count,
       get_json_string(payload, '$.operation') AS operation
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'risk.cluster.status_changed' AND schema_version = 1 AND source_system = 'cloudmold-risk';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_risk_review_event AS
SELECT event_id, tenant_id, aggregate_id AS case_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.cluster_id') AS cluster_id,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.reviewer_principal_id') AS reviewer_principal_id,
       get_json_string(payload, '$.operation') AS operation
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'risk.review.status_changed' AND schema_version = 1 AND source_system = 'cloudmold-risk';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_risk_decision_event AS
SELECT event_id, tenant_id, aggregate_id AS decision_id, aggregate_version, occurred_at AS event_occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.case_id') AS case_id,
       get_json_string(payload, '$.cluster_id') AS cluster_id,
       get_json_string(payload, '$.decision_type') AS decision_type,
       get_json_string(payload, '$.reason_code') AS reason_code,
       get_json_string(payload, '$.decided_by_principal_id') AS decided_by_principal_id,
       CAST(get_json_string(payload, '$.occurred_at') AS DATETIME) AS occurred_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'risk.decision.recorded' AND schema_version = 1 AND source_system = 'cloudmold-risk';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_risk_feedback_event AS
SELECT event_id, tenant_id, aggregate_id AS feedback_id, aggregate_version, occurred_at AS event_occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.decision_id') AS decision_id,
       get_json_string(payload, '$.case_id') AS case_id,
       get_json_string(payload, '$.feedback_type') AS feedback_type,
       get_json_string(payload, '$.reason_code') AS reason_code,
       get_json_string(payload, '$.recorded_by_principal_id') AS recorded_by_principal_id,
       CAST(get_json_string(payload, '$.occurred_at') AS DATETIME) AS occurred_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'risk.feedback.recorded' AND schema_version = 1 AND source_system = 'cloudmold-risk';
