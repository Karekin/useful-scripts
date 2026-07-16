-- Governed read models only; the Metadata service remains the write authority.
CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_metadata_dataset_governance_current AS
SELECT d.tenant_id, d.definition_id AS dataset_id, d.definition_version AS dataset_version,
       d.definition_code, d.display_name, d.owner_principal_id, d.dataset_type, d.qualified_name,
       d.layer_code, d.grain_code, d.schema_sha256, d.storage_location_ref, d.retention_days, d.field_count,
       d.data_source_id, d.data_source_version, s.source_type, s.environment,
       s.endpoint_ref, s.credential_ref, s.namespace_ref,
       CASE WHEN s.definition_id IS NULL THEN false ELSE true END AS exact_data_source_version_resolved,
       COALESCE(fields.observed_field_count, 0) AS observed_field_count,
       COALESCE(fields.distinct_field_code_count, 0) AS distinct_field_code_count,
       COALESCE(fields.distinct_ordinal_count, 0) AS distinct_ordinal_count,
       COALESCE(fields.minimum_ordinal, 0) AS minimum_ordinal,
       COALESCE(fields.maximum_ordinal, 0) AS maximum_ordinal,
       CASE WHEN COALESCE(fields.observed_field_count, 0) = d.field_count
                  AND COALESCE(fields.distinct_field_code_count, 0) = d.field_count
                  AND COALESCE(fields.distinct_ordinal_count, 0) = d.field_count
                  AND COALESCE(fields.minimum_ordinal, 0) = 1
                  AND COALESCE(fields.maximum_ordinal, 0) = d.field_count
                  AND COALESCE(fields.exact_detail_count, 0) = d.field_count
            THEN true ELSE false END AS dataset_field_inventory_replayable,
       CASE WHEN COALESCE(fields.classified_field_count, 0) = d.field_count
            THEN true ELSE false END AS field_classification_replayable
FROM yshopping_dim.dim_canonical_metadata_dataset_current d
LEFT JOIN yshopping_dim.dim_canonical_metadata_datasource_version_history s
  ON s.tenant_id = d.tenant_id AND s.definition_id = d.data_source_id
 AND s.definition_version = d.data_source_version
LEFT JOIN (
    SELECT tenant_id, dataset_id, dataset_version, COUNT(*) AS observed_field_count,
           COUNT(DISTINCT field_code) AS distinct_field_code_count,
           COUNT(DISTINCT ordinal_position) AS distinct_ordinal_count,
           MIN(ordinal_position) AS minimum_ordinal, MAX(ordinal_position) AS maximum_ordinal,
           SUM(CASE WHEN aggregate_version = dataset_version AND event_sequence = ordinal_position + 1
                    THEN 1 ELSE 0 END) AS exact_detail_count,
           SUM(CASE WHEN classification IN ('PUBLIC','INTERNAL','CONFIDENTIAL','RESTRICTED')
                    THEN 1 ELSE 0 END) AS classified_field_count
    FROM yshopping_dim.dim_canonical_metadata_dataset_field_current
    GROUP BY tenant_id, dataset_id, dataset_version
) fields ON fields.tenant_id = d.tenant_id AND fields.dataset_id = d.definition_id
        AND fields.dataset_version = d.definition_version;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_metadata_dataset_field_current AS
SELECT field.tenant_id, field.dataset_id, field.dataset_version, field.ordinal_position,
       field.field_code, field.data_type, field.nullable, field.primary_key_part,
       field.semantic_type, field.classification, dataset.qualified_name, dataset.layer_code,
       dataset.grain_code, dataset.field_count AS expected_field_count,
       CASE WHEN dataset.definition_id IS NULL THEN false ELSE true END AS exact_dataset_version_resolved,
       CASE WHEN field.aggregate_version = field.dataset_version
                  AND field.event_sequence = field.ordinal_position + 1 THEN true ELSE false END
         AS exact_detail_sequence
FROM yshopping_dim.dim_canonical_metadata_dataset_field_current field
LEFT JOIN yshopping_dim.dim_canonical_metadata_dataset_version_history dataset
  ON dataset.tenant_id = field.tenant_id AND dataset.definition_id = field.dataset_id
 AND dataset.definition_version = field.dataset_version;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_metadata_task_dependency_edge_current AS
SELECT dependency.tenant_id, dependency.task_id, dependency.task_version,
       dependency.dependency_sequence, dependency.upstream_task_id, dependency.upstream_task_version,
       dependency.dependency_type, dependency.required,
       task.dependency_count AS expected_dependency_count,
       CASE WHEN task.definition_id IS NULL THEN false ELSE true END AS exact_task_version_resolved,
       CASE WHEN upstream.definition_id IS NULL THEN false ELSE true END AS exact_upstream_task_version_resolved,
       CASE WHEN dependency.aggregate_version = dependency.task_version
                  AND dependency.event_sequence = dependency.dependency_sequence + 1 THEN true ELSE false END
         AS exact_detail_sequence
FROM yshopping_dim.dim_canonical_metadata_task_dependency_current dependency
LEFT JOIN yshopping_dim.dim_canonical_metadata_task_version_history task
  ON task.tenant_id = dependency.tenant_id AND task.definition_id = dependency.task_id
 AND task.definition_version = dependency.task_version
LEFT JOIN yshopping_dim.dim_canonical_metadata_task_version_history upstream
  ON upstream.tenant_id = dependency.tenant_id AND upstream.definition_id = dependency.upstream_task_id
 AND upstream.definition_version = dependency.upstream_task_version;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_metadata_lineage_edge_current AS
SELECT l.tenant_id, l.definition_id AS lineage_id, l.definition_version AS lineage_version,
       l.source_dataset_id, l.source_dataset_version, l.target_dataset_id, l.target_dataset_version,
       l.direction, l.transform_sha256, l.transformation_ref,
       CASE WHEN source.definition_id IS NULL THEN false ELSE true END AS exact_source_version_resolved,
       CASE WHEN target.definition_id IS NULL THEN false ELSE true END AS exact_target_version_resolved
FROM yshopping_dim.dim_canonical_metadata_lineage_current l
LEFT JOIN yshopping_dim.dim_canonical_metadata_dataset_version_history source
  ON source.tenant_id = l.tenant_id AND source.definition_id = l.source_dataset_id
 AND source.definition_version = l.source_dataset_version
LEFT JOIN yshopping_dim.dim_canonical_metadata_dataset_version_history target
  ON target.tenant_id = l.tenant_id AND target.definition_id = l.target_dataset_id
 AND target.definition_version = l.target_dataset_version;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_metadata_task_run_current AS
SELECT current_run.tenant_id, current_run.run_id, current_run.task_id, current_run.task_version,
       current_run.attempt, current_run.observation_sequence, current_run.previous_status,
       current_run.current_status, current_run.scheduled_at, current_run.started_at, current_run.finished_at,
       current_run.duration_millis, current_run.compute_cost_minor, current_run.cost_currency,
       current_run.resource_millis, current_run.rows_read, current_run.rows_written,
       current_run.source_checkpoint_ref, current_run.output_snapshot_ref, current_run.error_ref,
       current_run.observed_at, task.task_type, task.service_level_code, task.maximum_duration_millis,
       task.maximum_freshness_millis,
       CASE WHEN task.definition_id IS NULL THEN false ELSE true END AS exact_task_version_resolved,
       observation.observation_count, observation.distinct_sequence_count, observation.maximum_sequence
FROM yshopping_dim.dim_canonical_metadata_task_run_current current_run
LEFT JOIN yshopping_dim.dim_canonical_metadata_task_version_history task
  ON task.tenant_id = current_run.tenant_id AND task.definition_id = current_run.task_id
 AND task.definition_version = current_run.task_version
LEFT JOIN (
    SELECT tenant_id, run_id, COUNT(*) AS observation_count,
           COUNT(DISTINCT observation_sequence) AS distinct_sequence_count,
           MAX(observation_sequence) AS maximum_sequence
    FROM yshopping_dim.dim_canonical_metadata_task_run_observation_history
    GROUP BY tenant_id, run_id
) observation ON observation.tenant_id = current_run.tenant_id AND observation.run_id = current_run.run_id;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_metadata_dqc_evaluation_current AS
SELECT result.tenant_id, result.result_id, result.dqc_rule_id, result.dqc_rule_version,
       result.dataset_id, result.dataset_version, rule.dataset_field, rule.rule_type, rule.severity,
       rule.expression_sha256, rule.threshold_value, rule.threshold_comparator,
       result.task_run_id, result.task_run_observation_sequence, result.result_status,
       result.expected_value, result.actual_value, result.evaluated_rows, result.violation_count,
       result.evidence_ref, result.observed_at,
       CASE WHEN rule.definition_id IS NULL THEN false ELSE true END AS exact_rule_version_resolved,
       CASE WHEN dataset.definition_id IS NULL THEN false ELSE true END AS exact_dataset_version_resolved,
       CASE WHEN result.task_run_id IS NULL OR run.run_id IS NOT NULL THEN true ELSE false END
         AS exact_task_run_observation_resolved,
       CASE WHEN rule.dataset_id = result.dataset_id AND rule.dataset_version = result.dataset_version
            THEN true ELSE false END AS exact_rule_target_match,
       CASE WHEN rule.dataset_field IS NULL OR field.field_code IS NOT NULL THEN true ELSE false END
         AS exact_dataset_field_inventory_replayable
FROM yshopping_dim.dim_canonical_metadata_dqc_result_current result
LEFT JOIN yshopping_dim.dim_canonical_metadata_dqc_rule_version_history rule
  ON rule.tenant_id = result.tenant_id AND rule.definition_id = result.dqc_rule_id
 AND rule.definition_version = result.dqc_rule_version
LEFT JOIN yshopping_dim.dim_canonical_metadata_dataset_version_history dataset
  ON dataset.tenant_id = result.tenant_id AND dataset.definition_id = result.dataset_id
 AND dataset.definition_version = result.dataset_version
LEFT JOIN yshopping_dim.dim_canonical_metadata_dataset_field_version_history field
  ON field.tenant_id = rule.tenant_id AND field.dataset_id = rule.dataset_id
 AND field.dataset_version = rule.dataset_version AND field.field_code = rule.dataset_field
LEFT JOIN yshopping_dim.dim_canonical_metadata_task_run_observation_history run
  ON run.tenant_id = result.tenant_id AND run.run_id = result.task_run_id
 AND run.observation_sequence = result.task_run_observation_sequence;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_metadata_tenant_coverage_current AS
SELECT tenant_id,
       SUM(CASE WHEN definition_kind = 'DATA_SOURCE' THEN definition_count ELSE 0 END) AS data_source_count,
       SUM(CASE WHEN definition_kind = 'DATASET' THEN definition_count ELSE 0 END) AS dataset_count,
       SUM(CASE WHEN definition_kind = 'TASK' THEN definition_count ELSE 0 END) AS task_count,
       SUM(CASE WHEN definition_kind = 'LINEAGE' THEN definition_count ELSE 0 END) AS lineage_count,
       SUM(CASE WHEN definition_kind = 'DQC_RULE' THEN definition_count ELSE 0 END) AS dqc_rule_count,
       SUM(CASE WHEN definition_kind = 'METRIC' THEN definition_count ELSE 0 END) AS metric_count
FROM (
    SELECT tenant_id, 'DATA_SOURCE' AS definition_kind, COUNT(*) AS definition_count
      FROM yshopping_dim.dim_canonical_metadata_datasource_current GROUP BY tenant_id
    UNION ALL
    SELECT tenant_id, 'DATASET', COUNT(*) FROM yshopping_dim.dim_canonical_metadata_dataset_current GROUP BY tenant_id
    UNION ALL
    SELECT tenant_id, 'TASK', COUNT(*) FROM yshopping_dim.dim_canonical_metadata_task_current GROUP BY tenant_id
    UNION ALL
    SELECT tenant_id, 'LINEAGE', COUNT(*) FROM yshopping_dim.dim_canonical_metadata_lineage_current GROUP BY tenant_id
    UNION ALL
    SELECT tenant_id, 'DQC_RULE', COUNT(*) FROM yshopping_dim.dim_canonical_metadata_dqc_rule_current GROUP BY tenant_id
    UNION ALL
    SELECT tenant_id, 'METRIC', COUNT(*) FROM yshopping_dim.dim_canonical_metadata_metric_current GROUP BY tenant_id
) definition_counts
GROUP BY tenant_id;
