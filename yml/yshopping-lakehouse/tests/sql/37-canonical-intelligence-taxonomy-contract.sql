-- Versioned Y-Shopping intelligence taxonomy and classified-observation DQC. Every query must return zero.
SELECT 'intelligence_taxonomy_definition_identity_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, taxonomy_id, definition_version
    FROM yshopping_dim.dim_canonical_intelligence_taxonomy_version
    GROUP BY tenant_id, taxonomy_id, definition_version HAVING COUNT(*) <> 1
) duplicate_versions;

SELECT 'intelligence_taxonomy_source_version_identity_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, taxonomy_source_system, source_table, source_record_key, source_version
    FROM yshopping_dim.dim_canonical_intelligence_taxonomy_version
    GROUP BY tenant_id, taxonomy_source_system, source_table, source_record_key, source_version
    HAVING COUNT(*) <> 1
) duplicate_source_versions;

SELECT 'intelligence_taxonomy_definition_version_gap' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, taxonomy_id, MIN(definition_version) AS min_version,
           MAX(definition_version) AS max_version, COUNT(*) AS version_count
    FROM yshopping_dim.dim_canonical_intelligence_taxonomy_version
    GROUP BY tenant_id, taxonomy_id
) history
WHERE min_version <> 1 OR max_version <> version_count;

SELECT 'intelligence_taxonomy_effective_time_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_intelligence_taxonomy_version
WHERE effective_from IS NULL OR (next_effective_from IS NOT NULL AND next_effective_from <= effective_from);

SELECT 'intelligence_taxonomy_level_set_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_intelligence_taxonomy_version
WHERE level_codes_json IS NULL OR JSON_LENGTH(PARSE_JSON(level_codes_json)) < 1
   OR JSON_LENGTH(PARSE_JSON(level_codes_json)) > 32
   OR levels_sha256 NOT REGEXP '^[0-9a-f]{64}$';

SELECT 'intelligence_taxonomy_head_version_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_intelligence_taxonomy_current
WHERE definition_version <> version_event_count
   OR lifecycle_event_count <> aggregate_version - 1
   OR current_status NOT IN ('PUBLISHED','RETIRED')
   OR (current_status = 'PUBLISHED' AND retired_at IS NOT NULL)
   OR (current_status = 'RETIRED' AND retired_at IS NULL);

SELECT 'intelligence_taxonomy_source_lineage_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_intelligence_taxonomy_current
WHERE taxonomy_source_system <> 'YSHOPPING'
   OR source_table <> 'ods_intelligence_event_code_level_df'
   OR source_record_key IS NULL OR source_version IS NULL OR source_observed_at IS NULL
   OR source_evidence_ref IS NULL OR source_evidence_sha256 NOT REGEXP '^[0-9a-f]{64}$';

SELECT 'classified_observation_reference_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_intelligence_observation_current
WHERE classification_contract_version = 2 AND taxonomy_reference_valid = false;

SELECT 'classified_observation_contract_snapshot_missing' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_intelligence_observation_current
WHERE classification_contract_version = 2
  AND (schema_version <> 2 OR taxonomy_id IS NULL OR taxonomy_version_id IS NULL
       OR taxonomy_definition_version IS NULL OR event_code IS NULL OR intelligence_level_code IS NULL);

SELECT 'legacy_observation_classification_leak' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_intelligence_observation_current
WHERE classification_contract_version = 1
  AND (taxonomy_id IS NOT NULL OR taxonomy_version_id IS NOT NULL
       OR taxonomy_definition_version IS NOT NULL OR event_code IS NOT NULL
       OR intelligence_level_code IS NOT NULL);

SELECT 'classified_observation_post_retirement' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_intelligence_observation_current observation
JOIN yshopping_dim.dim_canonical_intelligence_taxonomy_current taxonomy
  ON taxonomy.tenant_id = observation.tenant_id AND taxonomy.taxonomy_id = observation.taxonomy_id
WHERE observation.classification_contract_version = 2
  AND taxonomy.retired_at IS NOT NULL AND observation.observed_at >= taxonomy.retired_at;

SELECT 'intelligence_taxonomy_readiness_inconsistent' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_intelligence_taxonomy_readiness
WHERE readiness_status <> 'GOVERNED_SEMANTICS_READY' OR missing_source_lineage_count <> 0;

SELECT 'classified_observation_readiness_inconsistent' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_classified_intelligence_observation_readiness
WHERE readiness_status <> 'GOVERNED_SEMANTICS_READY' OR taxonomy_reference_valid = false;

SELECT 'intelligence_taxonomy_automatic_enforcement_enabled' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_intelligence_taxonomy_readiness
WHERE automatic_enforcement_enabled <> false;

SELECT 'classified_observation_automatic_enforcement_enabled' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_classified_intelligence_observation_readiness
WHERE automatic_enforcement_enabled <> false;
