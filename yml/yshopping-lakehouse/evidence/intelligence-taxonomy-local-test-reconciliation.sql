-- Local TEST evidence only. This proves non-empty source-backed taxonomy correction, observation-time binding,
-- retirement, API -> transactional Outbox -> Flink CDC -> StarRocks projection and governed readiness.
-- It is intentionally not admissible as Y-Shopping production-source reconciliation.

SELECT 'relay_confirmed_event_count' AS layer_metric, COUNT(*) AS actual_count, 5 AS expected_count
FROM yshopping_dwd.dwd_domain_event
WHERE tenant_id=1 AND aggregate_id IN (
    '5b2ed8ad-2e89-461d-88e4-6c4271976115',
    'int-tax-final-observation-v1','int-tax-final-observation-v2')
UNION ALL
SELECT 'dwd_taxonomy_definition_versions', COUNT(*), 2
FROM yshopping_dwd.dwd_canonical_intelligence_taxonomy_version_event
WHERE tenant_id=1 AND taxonomy_id='5b2ed8ad-2e89-461d-88e4-6c4271976115'
UNION ALL
SELECT 'dwd_taxonomy_retirement', COUNT(*), 1
FROM yshopping_dwd.dwd_canonical_intelligence_taxonomy_retirement_event
WHERE tenant_id=1 AND taxonomy_id='5b2ed8ad-2e89-461d-88e4-6c4271976115'
UNION ALL
SELECT 'dwd_classified_observations_v2', COUNT(*), 2
FROM yshopping_dwd.dwd_canonical_intelligence_observation_event
WHERE tenant_id=1 AND observation_id IN ('int-tax-final-observation-v1','int-tax-final-observation-v2')
  AND schema_version=2 AND classification_contract_version=2
UNION ALL
SELECT 'dim_immutable_definition_history', COUNT(*), 2
FROM yshopping_dim.dim_canonical_intelligence_taxonomy_version
WHERE tenant_id=1 AND taxonomy_id='5b2ed8ad-2e89-461d-88e4-6c4271976115'
  AND ((definition_version=1 AND JSON_CONTAINS(PARSE_JSON(level_codes_json),PARSE_JSON('\"B\"'))
        AND next_effective_from IS NOT NULL)
    OR (definition_version=2 AND JSON_CONTAINS(PARSE_JSON(level_codes_json),PARSE_JSON('\"D\"'))
        AND next_effective_from IS NULL))
UNION ALL
SELECT 'dim_retired_taxonomy_head', COUNT(*), 1
FROM yshopping_dim.dim_canonical_intelligence_taxonomy_current
WHERE tenant_id=1 AND taxonomy_id='5b2ed8ad-2e89-461d-88e4-6c4271976115'
  AND current_status='RETIRED' AND definition_version=2 AND version_event_count=2
  AND lifecycle_event_count=3 AND retired_at IS NOT NULL
  AND taxonomy_source_system='YSHOPPING' AND source_table='ods_intelligence_event_code_level_df'
  AND source_record_key='19' AND source_version='source-v3'
UNION ALL
SELECT 'dws_observation_v1_bound_to_definition_v1', COUNT(*), 1
FROM yshopping_dws.dws_canonical_intelligence_observation_current
WHERE tenant_id=1 AND observation_id='int-tax-final-observation-v1'
  AND taxonomy_definition_version=1 AND intelligence_level_code='B'
  AND classification_status='GOVERNED' AND taxonomy_reference_valid=true
UNION ALL
SELECT 'dws_observation_v2_bound_to_definition_v2', COUNT(*), 1
FROM yshopping_dws.dws_canonical_intelligence_observation_current
WHERE tenant_id=1 AND observation_id='int-tax-final-observation-v2'
  AND taxonomy_definition_version=2 AND intelligence_level_code='D'
  AND classification_status='GOVERNED' AND taxonomy_reference_valid=true
UNION ALL
SELECT 'ads_taxonomy_readiness', COUNT(*), 1
FROM yshopping_ads.ads_canonical_intelligence_taxonomy_readiness
WHERE tenant_id=1 AND taxonomy_id='5b2ed8ad-2e89-461d-88e4-6c4271976115'
  AND missing_source_lineage_count=0 AND readiness_status='GOVERNED_SEMANTICS_READY'
  AND automatic_enforcement_enabled=false
UNION ALL
SELECT 'ads_classified_observation_readiness', COUNT(*), 2
FROM yshopping_ads.ads_canonical_classified_intelligence_observation_readiness
WHERE tenant_id=1 AND observation_id IN ('int-tax-final-observation-v1','int-tax-final-observation-v2')
  AND taxonomy_reference_valid=true AND readiness_status='GOVERNED_SEMANTICS_READY'
  AND automatic_enforcement_enabled=false;
