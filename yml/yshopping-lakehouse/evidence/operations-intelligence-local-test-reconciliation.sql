-- Local TEST evidence only. This proves executable non-empty API -> Outbox -> Flink CDC -> StarRocks semantics.
-- It is intentionally not admissible as Y-Shopping production-source reconciliation.

SELECT 'dwd_observation_event' AS layer_metric, COUNT(*) AS actual_count, 1 AS expected_count
FROM yshopping_dwd.dwd_canonical_intelligence_observation_event
WHERE tenant_id=1 AND observation_id='ops-int-rt-observation-01'
UNION ALL
SELECT 'dwd_model_result_event', COUNT(*), 1
FROM yshopping_dwd.dwd_canonical_intelligence_model_result_event
WHERE tenant_id=1 AND model_result_id='ops-int-rt-model-result-01'
UNION ALL
SELECT 'dwd_clue_recorded_event', COUNT(*), 1
FROM yshopping_dwd.dwd_canonical_intelligence_clue_event
WHERE tenant_id=1 AND clue_id='ops-int-rt-clue-01'
UNION ALL
SELECT 'dwd_clue_review_event', COUNT(*), 1
FROM yshopping_dwd.dwd_canonical_intelligence_clue_review_event
WHERE tenant_id=1 AND clue_id='ops-int-rt-clue-01'
UNION ALL
SELECT 'dwd_alert_history_event', COUNT(*), 4
FROM yshopping_dwd.dwd_canonical_operations_alert_event
WHERE tenant_id=1 AND alert_id='ops-int-rt-alert-01'
UNION ALL
SELECT 'dim_observation_current', COUNT(*), 1
FROM yshopping_dim.dim_canonical_intelligence_observation_current
WHERE tenant_id=1 AND observation_id='ops-int-rt-observation-01'
UNION ALL
SELECT 'dim_model_result_current', COUNT(*), 1
FROM yshopping_dim.dim_canonical_intelligence_model_result_current
WHERE tenant_id=1 AND model_result_id='ops-int-rt-model-result-01' AND outcome_code='SUCCEEDED'
UNION ALL
SELECT 'dim_human_accepted_clue_current', COUNT(*), 1
FROM yshopping_dim.dim_canonical_intelligence_clue_current
WHERE tenant_id=1 AND clue_id='ops-int-rt-clue-01' AND current_status='ACCEPTED'
  AND decision='ACCEPT' AND reviewer_principal_id='principal-admin-01'
UNION ALL
SELECT 'dim_resolved_alert_current', COUNT(*), 1
FROM yshopping_dim.dim_canonical_operations_alert_current
WHERE tenant_id=1 AND alert_id='ops-int-rt-alert-01' AND aggregate_version=4
  AND current_status='RESOLVED' AND alert_event_count=4
UNION ALL
SELECT 'dws_observation_current', COUNT(*), 1
FROM yshopping_dws.dws_canonical_intelligence_observation_current
WHERE tenant_id=1 AND observation_id='ops-int-rt-observation-01'
  AND model_result_count=1 AND succeeded_model_result_count=1
  AND clue_count=1 AND accepted_clue_count=1 AND rejected_clue_count=0 AND pending_clue_count=0
UNION ALL
SELECT 'dws_alert_current', COUNT(*), 1
FROM yshopping_dws.dws_canonical_operations_alert_current
WHERE tenant_id=1 AND alert_id='ops-int-rt-alert-01' AND current_status='RESOLVED'
  AND invalid_source_count=0 AND automatic_enforcement_enabled=false
UNION ALL
SELECT 'ads_ai_intelligence_readiness', COUNT(*), 1
FROM yshopping_ads.ads_canonical_ai_intelligence_readiness
WHERE tenant_id=1 AND readiness_status='HUMAN_REVIEW_GOVERNED'
  AND raw_content_stored=false AND automatic_enforcement_enabled=false
UNION ALL
SELECT 'ads_operations_alert_readiness', COUNT(*), 1
FROM yshopping_ads.ads_canonical_operations_alert_readiness
WHERE tenant_id=1 AND readiness_status='GOVERNED_ALERT_LIFECYCLE_READY'
  AND invalid_source_count=0 AND history_sequence_gap_count=0 AND automatic_enforcement_enabled=false;
