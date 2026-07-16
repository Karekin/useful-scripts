-- Canonical Metadata first-slice DQC. Empty results are contract safety, never runtime completion.
SELECT 'metadata_event_id_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, event_id FROM yshopping_dwd.dwd_domain_event
    WHERE source_system = 'cloudmold-metadata'
    GROUP BY tenant_id, event_id HAVING COUNT(*) <> 1
) duplicates;

SELECT 'metadata_event_payload_sensitive_material_leak' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_domain_event
WHERE source_system = 'cloudmold-metadata'
  AND (LOWER(payload) REGEXP '"(url|username|password|credential|raw_sql|sql_content|raw_error)"[ ]*:'
       OR LOWER(payload) LIKE '%jdbc:mysql://%' OR LOWER(payload) LIKE '%://%@%');

SELECT 'metadata_definition_version_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT definition_kind, tenant_id, definition_id, definition_version
    FROM (
        SELECT 'DATA_SOURCE' AS definition_kind, tenant_id, definition_id, definition_version
          FROM yshopping_dim.dim_canonical_metadata_datasource_version_history
        UNION ALL SELECT 'DATASET', tenant_id, definition_id, definition_version
          FROM yshopping_dim.dim_canonical_metadata_dataset_version_history
        UNION ALL SELECT 'TASK', tenant_id, definition_id, definition_version
          FROM yshopping_dim.dim_canonical_metadata_task_version_history
        UNION ALL SELECT 'LINEAGE', tenant_id, definition_id, definition_version
          FROM yshopping_dim.dim_canonical_metadata_lineage_version_history
        UNION ALL SELECT 'DQC_RULE', tenant_id, definition_id, definition_version
          FROM yshopping_dim.dim_canonical_metadata_dqc_rule_version_history
        UNION ALL SELECT 'METRIC', tenant_id, definition_id, definition_version
          FROM yshopping_dim.dim_canonical_metadata_metric_version_history
    ) versions
    GROUP BY definition_kind, tenant_id, definition_id, definition_version HAVING COUNT(*) <> 1
) duplicates;

SELECT 'metadata_definition_version_sequence_gap' AS check_name, COUNT(*) AS violations
FROM (
    SELECT definition_kind, tenant_id, definition_id, COUNT(*) AS version_count,
           COUNT(DISTINCT definition_version) AS distinct_version_count,
           MIN(definition_version) AS minimum_version, MAX(definition_version) AS maximum_version
    FROM (
        SELECT 'DATA_SOURCE' AS definition_kind, tenant_id, definition_id, definition_version
          FROM yshopping_dim.dim_canonical_metadata_datasource_version_history
        UNION ALL SELECT 'DATASET', tenant_id, definition_id, definition_version
          FROM yshopping_dim.dim_canonical_metadata_dataset_version_history
        UNION ALL SELECT 'TASK', tenant_id, definition_id, definition_version
          FROM yshopping_dim.dim_canonical_metadata_task_version_history
        UNION ALL SELECT 'LINEAGE', tenant_id, definition_id, definition_version
          FROM yshopping_dim.dim_canonical_metadata_lineage_version_history
        UNION ALL SELECT 'DQC_RULE', tenant_id, definition_id, definition_version
          FROM yshopping_dim.dim_canonical_metadata_dqc_rule_version_history
        UNION ALL SELECT 'METRIC', tenant_id, definition_id, definition_version
          FROM yshopping_dim.dim_canonical_metadata_metric_version_history
    ) versions GROUP BY definition_kind, tenant_id, definition_id
) sequences
WHERE minimum_version <> 1 OR version_count <> distinct_version_count OR maximum_version <> version_count;

SELECT 'metadata_definition_aggregate_version_mismatch' AS check_name, COUNT(*) AS violations
FROM (
    SELECT aggregate_version, definition_version FROM yshopping_dim.dim_canonical_metadata_datasource_version_history
    UNION ALL SELECT aggregate_version, definition_version FROM yshopping_dim.dim_canonical_metadata_dataset_version_history
    UNION ALL SELECT aggregate_version, definition_version FROM yshopping_dim.dim_canonical_metadata_task_version_history
    UNION ALL SELECT aggregate_version, definition_version FROM yshopping_dim.dim_canonical_metadata_lineage_version_history
    UNION ALL SELECT aggregate_version, definition_version FROM yshopping_dim.dim_canonical_metadata_dqc_rule_version_history
    UNION ALL SELECT aggregate_version, definition_version FROM yshopping_dim.dim_canonical_metadata_metric_version_history
) definitions WHERE aggregate_version <> definition_version;

SELECT 'metadata_opaque_reference_invalid' AS check_name, COUNT(*) AS violations
FROM (
    SELECT artifact_ref AS ref_value FROM yshopping_dim.dim_canonical_metadata_datasource_version_history
    UNION ALL SELECT endpoint_ref FROM yshopping_dim.dim_canonical_metadata_datasource_version_history
    UNION ALL SELECT credential_ref FROM yshopping_dim.dim_canonical_metadata_datasource_version_history
    UNION ALL SELECT namespace_ref FROM yshopping_dim.dim_canonical_metadata_datasource_version_history
    UNION ALL SELECT artifact_ref FROM yshopping_dim.dim_canonical_metadata_dataset_version_history
    UNION ALL SELECT storage_location_ref FROM yshopping_dim.dim_canonical_metadata_dataset_version_history
    UNION ALL SELECT executable_artifact_ref FROM yshopping_dim.dim_canonical_metadata_task_version_history
    UNION ALL SELECT resource_group_ref FROM yshopping_dim.dim_canonical_metadata_task_version_history
    UNION ALL SELECT transformation_ref FROM yshopping_dim.dim_canonical_metadata_lineage_version_history
    UNION ALL SELECT evidence_ref FROM yshopping_dim.dim_canonical_metadata_dqc_result_history
) refs
WHERE ref_value IS NULL OR ref_value NOT REGEXP '^(sha256:[0-9a-f]{64}|restricted:[A-Za-z0-9][A-Za-z0-9._/-]{7,159})$';

SELECT 'metadata_dataset_source_or_field_count_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_metadata_dataset_governance_current
WHERE exact_data_source_version_resolved = false OR field_count <= 0 OR retention_days <= 0;

SELECT 'metadata_dataset_field_count_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_metadata_dataset_version_history dataset
LEFT JOIN (
    SELECT tenant_id, dataset_id, dataset_version, COUNT(*) AS observed_count,
           COUNT(DISTINCT field_code) AS distinct_field_count,
           COUNT(DISTINCT ordinal_position) AS distinct_ordinal_count,
           MIN(ordinal_position) AS minimum_ordinal, MAX(ordinal_position) AS maximum_ordinal,
           SUM(CASE WHEN aggregate_version = dataset_version AND event_sequence = ordinal_position + 1
                    THEN 1 ELSE 0 END) AS exact_detail_count
    FROM yshopping_dim.dim_canonical_metadata_dataset_field_version_history
    GROUP BY tenant_id, dataset_id, dataset_version
) fields ON fields.tenant_id = dataset.tenant_id AND fields.dataset_id = dataset.definition_id
        AND fields.dataset_version = dataset.definition_version
WHERE COALESCE(fields.observed_count, 0) <> dataset.field_count
   OR COALESCE(fields.distinct_field_count, 0) <> dataset.field_count
   OR COALESCE(fields.distinct_ordinal_count, 0) <> dataset.field_count
   OR COALESCE(fields.minimum_ordinal, 0) <> 1
   OR COALESCE(fields.maximum_ordinal, 0) <> dataset.field_count
   OR COALESCE(fields.exact_detail_count, 0) <> dataset.field_count;

SELECT 'metadata_dataset_field_ordinal_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_metadata_dataset_field_version_history field
LEFT JOIN yshopping_dim.dim_canonical_metadata_dataset_version_history dataset
  ON dataset.tenant_id = field.tenant_id AND dataset.definition_id = field.dataset_id
 AND dataset.definition_version = field.dataset_version
WHERE dataset.definition_id IS NULL OR field.aggregate_version <> field.dataset_version
   OR field.event_sequence <> field.ordinal_position + 1
   OR field.ordinal_position < 1 OR field.ordinal_position > dataset.field_count;

SELECT 'metadata_dataset_field_code_or_ordinal_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, dataset_id, dataset_version
    FROM yshopping_dim.dim_canonical_metadata_dataset_field_version_history
    GROUP BY tenant_id, dataset_id, dataset_version
    HAVING COUNT(*) <> COUNT(DISTINCT field_code)
        OR COUNT(*) <> COUNT(DISTINCT ordinal_position)
) duplicates;

SELECT 'metadata_task_sla_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_metadata_task_version_history
WHERE deadline_minute_utc < 0 OR deadline_minute_utc >= 1440
   OR maximum_duration_millis <= 0 OR maximum_freshness_millis <= 0
   OR dependency_count < 0 OR dependency_count > 500;

SELECT 'metadata_task_dependency_count_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_metadata_task_version_history task
LEFT JOIN (
    SELECT tenant_id, task_id, task_version, COUNT(*) AS observed_count,
           COUNT(DISTINCT dependency_sequence) AS distinct_sequence_count,
           MIN(dependency_sequence) AS minimum_sequence, MAX(dependency_sequence) AS maximum_sequence
    FROM yshopping_dim.dim_canonical_metadata_task_dependency_version_history
    GROUP BY tenant_id, task_id, task_version
) dependency ON dependency.tenant_id = task.tenant_id AND dependency.task_id = task.definition_id
            AND dependency.task_version = task.definition_version
WHERE COALESCE(dependency.observed_count, 0) <> task.dependency_count
   OR COALESCE(dependency.distinct_sequence_count, 0) <> task.dependency_count
   OR COALESCE(dependency.minimum_sequence, 1) <> 1
   OR COALESCE(dependency.maximum_sequence, 0) <> task.dependency_count;

SELECT 'metadata_task_dependency_endpoint_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_metadata_task_dependency_version_history dependency
LEFT JOIN yshopping_dim.dim_canonical_metadata_task_version_history task
  ON task.tenant_id = dependency.tenant_id AND task.definition_id = dependency.task_id
 AND task.definition_version = dependency.task_version
LEFT JOIN yshopping_dim.dim_canonical_metadata_task_version_history upstream
  ON upstream.tenant_id = dependency.tenant_id AND upstream.definition_id = dependency.upstream_task_id
 AND upstream.definition_version = dependency.upstream_task_version
WHERE task.definition_id IS NULL OR upstream.definition_id IS NULL
   OR dependency.aggregate_version <> dependency.task_version
   OR dependency.event_sequence <> dependency.dependency_sequence + 1;

SELECT 'metadata_task_dependency_direct_edge_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, task_id, task_version, upstream_task_id, dependency_type
    FROM yshopping_dim.dim_canonical_metadata_task_dependency_version_history
    GROUP BY tenant_id, task_id, task_version, upstream_task_id, dependency_type
    HAVING COUNT(*) <> 1
) duplicates;

SELECT 'metadata_task_dependency_self_loop' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_metadata_task_dependency_version_history
WHERE task_id = upstream_task_id;

SELECT 'metadata_task_dependency_two_edge_cycle' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_metadata_task_dependency_version_history first_edge
JOIN yshopping_dim.dim_canonical_metadata_task_dependency_version_history second_edge
  ON second_edge.tenant_id = first_edge.tenant_id
 AND second_edge.task_id = first_edge.upstream_task_id
 AND second_edge.task_version = first_edge.upstream_task_version
 AND second_edge.upstream_task_id = first_edge.task_id
 AND second_edge.upstream_task_version = first_edge.task_version
WHERE CONCAT(first_edge.task_id, ':', first_edge.task_version)
    < CONCAT(second_edge.task_id, ':', second_edge.task_version);

SELECT 'metadata_task_dependency_transitive_dag_overclaim' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_metadata_readiness
WHERE task_dependency_graph_replayable <> false OR transitive_dag_runtime_verified <> false;

SELECT 'metadata_lineage_self_loop_or_direction_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_metadata_lineage_edge_current
WHERE source_dataset_id = target_dataset_id OR direction <> 'SOURCE_TO_TARGET';

SELECT 'metadata_lineage_exact_endpoint_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_metadata_lineage_edge_current
WHERE exact_source_version_resolved = false OR exact_target_version_resolved = false;

SELECT 'metadata_lineage_two_edge_cycle' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_metadata_lineage_edge_current first_edge
JOIN yshopping_dws.dws_canonical_metadata_lineage_edge_current second_edge
  ON second_edge.tenant_id = first_edge.tenant_id
 AND second_edge.source_dataset_id = first_edge.target_dataset_id
 AND second_edge.source_dataset_version = first_edge.target_dataset_version
 AND second_edge.target_dataset_id = first_edge.source_dataset_id
 AND second_edge.target_dataset_version = first_edge.source_dataset_version
WHERE first_edge.lineage_id < second_edge.lineage_id;

SELECT 'metadata_task_run_sequence_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, run_id, observation_sequence
    FROM yshopping_dim.dim_canonical_metadata_task_run_observation_history
    GROUP BY tenant_id, run_id, observation_sequence HAVING COUNT(*) <> 1
) duplicates;

SELECT 'metadata_task_run_sequence_gap_or_task_version_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_metadata_task_run_current
WHERE exact_task_version_resolved = false OR observation_count <> distinct_sequence_count
   OR maximum_sequence <> observation_count OR observation_sequence <> maximum_sequence;

SELECT 'metadata_task_run_transition_invalid' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, run_id, observation_sequence, attempt, previous_status, current_status,
           LAG(current_status) OVER (PARTITION BY tenant_id, run_id ORDER BY observation_sequence) AS prior_current_status,
           LAG(attempt) OVER (PARTITION BY tenant_id, run_id ORDER BY observation_sequence) AS prior_attempt
    FROM yshopping_dim.dim_canonical_metadata_task_run_observation_history
) transitions
WHERE (observation_sequence = 1 AND (previous_status IS NOT NULL OR attempt <> 1
                                    OR current_status NOT IN ('SCHEDULED','RUNNING')))
   OR current_status NOT IN ('SCHEDULED','RUNNING','SUCCEEDED','FAILED','CANCELLED')
   OR (previous_status IS NOT NULL
       AND previous_status NOT IN ('SCHEDULED','RUNNING','SUCCEEDED','FAILED','CANCELLED'))
   OR (observation_sequence > 1 AND previous_status <> prior_current_status)
   OR (observation_sequence > 1 AND ((prior_current_status IN ('SUCCEEDED','FAILED','CANCELLED')
                                      AND (current_status <> 'SCHEDULED' OR attempt <> prior_attempt + 1))
                                  OR (prior_current_status NOT IN ('SUCCEEDED','FAILED','CANCELLED')
                                      AND attempt <> prior_attempt)
                                  OR (prior_current_status = 'SCHEDULED'
                                      AND current_status NOT IN ('RUNNING','CANCELLED'))
                                  OR (prior_current_status = 'RUNNING'
                                      AND current_status NOT IN ('SUCCEEDED','FAILED','CANCELLED'))));

SELECT 'metadata_task_run_measurement_or_iso_currency_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_metadata_task_run_observation_history
WHERE scheduled_at IS NULL OR (started_at IS NOT NULL AND started_at < scheduled_at)
   OR (finished_at IS NOT NULL AND (started_at IS NULL OR finished_at < started_at))
   OR COALESCE(duration_millis, 0) < 0 OR COALESCE(compute_cost_minor, 0) < 0
   OR cost_currency NOT REGEXP '^[A-Z]{3}$' OR COALESCE(resource_millis, 0) < 0
   OR COALESCE(rows_read, 0) < 0 OR COALESCE(rows_written, 0) < 0
   OR (finished_at IS NOT NULL AND duration_millis IS NULL)
   OR (finished_at IS NOT NULL
       AND TIMESTAMPDIFF(MILLISECOND, started_at, finished_at) <> duration_millis)
   OR (current_status IN ('SUCCEEDED','FAILED','CANCELLED') AND finished_at IS NULL)
   OR (current_status = 'SUCCEEDED' AND (output_snapshot_ref IS NULL OR error_ref IS NOT NULL))
   OR (current_status = 'FAILED' AND error_ref IS NULL);

SELECT 'metadata_dqc_exact_reference_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_metadata_dqc_evaluation_current
WHERE exact_rule_version_resolved = false OR exact_dataset_version_resolved = false
   OR exact_task_run_observation_resolved = false OR exact_rule_target_match = false
   OR exact_dataset_field_inventory_replayable = false;

SELECT 'metadata_dqc_dataset_field_reference_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_metadata_dqc_evaluation_current
WHERE exact_dataset_field_inventory_replayable = false;

SELECT 'metadata_dqc_result_measurement_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_metadata_dqc_evaluation_current
WHERE evaluated_rows < 0 OR violation_count < 0 OR violation_count > evaluated_rows
   OR (result_status = 'PASS' AND violation_count <> 0)
   OR (result_status IN ('WARN','FAIL') AND violation_count = 0);

SELECT 'metadata_metric_version_or_hash_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_metadata_metric_version_history
WHERE semantic_version NOT REGEXP '^[1-9][0-9]{0,8}\.[0-9]{1,9}\.[0-9]{1,9}$'
   OR expression_sha256 NOT REGEXP '^[0-9a-f]{64}$'
   OR filter_sha256 NOT REGEXP '^[0-9a-f]{64}$'
   OR dimensions_sha256 NOT REGEXP '^[0-9a-f]{64}$';

SELECT 'metadata_unproven_completion_flag' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_metadata_readiness
WHERE nonempty_runtime_reconciled <> false OR readiness_status <> 'FIRST_SLICE_PARTIAL';
