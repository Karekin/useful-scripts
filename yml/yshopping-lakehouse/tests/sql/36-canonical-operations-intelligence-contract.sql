-- Canonical Operations Intelligence DQC. Every query must return zero.
SELECT 'operations_intelligence_event_id_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, event_id FROM yshopping_dwd.dwd_domain_event
    WHERE source_system = 'cloudmold-operations-intelligence'
    GROUP BY tenant_id, event_id HAVING COUNT(*) <> 1
) duplicates;

SELECT 'operations_intelligence_observation_source_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, source_system, source_event_id
    FROM yshopping_dim.dim_canonical_intelligence_observation_current
    GROUP BY tenant_id, source_system, source_event_id HAVING COUNT(*) <> 1
) duplicates;

SELECT 'operations_intelligence_model_result_orphan_observation' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_intelligence_model_result_current model_result
LEFT JOIN yshopping_dim.dim_canonical_intelligence_observation_current observation
  ON observation.tenant_id = model_result.tenant_id
 AND observation.observation_id = model_result.observation_id
WHERE observation.observation_id IS NULL;

SELECT 'operations_intelligence_clue_orphan_model_result' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_intelligence_clue_current clue
LEFT JOIN yshopping_dim.dim_canonical_intelligence_model_result_current model_result
  ON model_result.tenant_id = clue.tenant_id AND model_result.model_result_id = clue.model_result_id
WHERE clue.model_result_id IS NOT NULL
  AND (model_result.model_result_id IS NULL OR model_result.observation_id <> clue.observation_id);

SELECT 'operations_intelligence_clue_review_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_intelligence_clue_current
WHERE (current_status = 'OBSERVED' AND review_id IS NOT NULL)
   OR (current_status = 'ACCEPTED' AND (review_id IS NULL OR decision <> 'ACCEPT'))
   OR (current_status = 'REJECTED' AND (review_id IS NULL OR decision <> 'REJECT'));

SELECT 'operations_intelligence_sensitive_raw_content_leak' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_domain_event
WHERE source_system = 'cloudmold-operations-intelligence'
  AND (LOWER(payload) REGEXP '"(title|description|content|prompt|response|phone|email|address|ip|device)"[[:space:]]*:'
       OR LOWER(headers) NOT LIKE '%"raw_content_stored":false%');

SELECT 'operations_intelligence_alert_version_sequence_gap' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, alert_id, MIN(aggregate_version) AS minimum_version,
           MAX(aggregate_version) AS maximum_version, COUNT(*) AS event_count
    FROM yshopping_dwd.dwd_canonical_operations_alert_event
    GROUP BY tenant_id, alert_id
) history
WHERE minimum_version <> 1 OR maximum_version <> event_count;

SELECT 'operations_intelligence_alert_transition_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_operations_alert_event
WHERE (aggregate_version = 1 AND (previous_status IS NOT NULL OR current_status <> 'OPEN'))
   OR (aggregate_version > 1 AND NOT (
          (previous_status = 'OPEN' AND current_status IN ('NOTIFIED','CLAIMED','INVALID','CLOSED_NO_ACTION'))
       OR (previous_status = 'NOTIFIED' AND current_status IN ('CLAIMED','INVALID','CLOSED_NO_ACTION'))
       OR (previous_status = 'CLAIMED' AND current_status IN ('RESOLVED','INVALID'))));

SELECT 'operations_intelligence_alert_source_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_operations_alert_current
WHERE invalid_source_count <> 0;

SELECT 'operations_intelligence_automatic_enforcement_enabled' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_operations_alert_readiness
WHERE automatic_enforcement_enabled <> false;
