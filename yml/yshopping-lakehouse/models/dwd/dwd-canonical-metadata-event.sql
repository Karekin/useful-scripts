-- Canonical Metadata control-plane facts. Raw SQL, connection strings and credentials are intentionally absent.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_metadata_datasource_version_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at, correlation_id,
       causation_id, idempotency_key,
       get_json_string(payload, '$.definition_id') AS definition_id,
       get_json_string(payload, '$.definition_code') AS definition_code,
       CAST(get_json_string(payload, '$.definition_version') AS BIGINT) AS definition_version,
       get_json_string(payload, '$.display_name') AS display_name,
       get_json_string(payload, '$.owner_principal_id') AS owner_principal_id,
       get_json_string(payload, '$.specification_sha256') AS specification_sha256,
       get_json_string(payload, '$.artifact_ref') AS artifact_ref,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.source_type') AS source_type,
       get_json_string(payload, '$.environment') AS environment,
       get_json_string(payload, '$.endpoint_ref') AS endpoint_ref,
       get_json_string(payload, '$.credential_ref') AS credential_ref,
       get_json_string(payload, '$.namespace_ref') AS namespace_ref
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'metadata.datasource.version_published' AND schema_version = 1
  AND source_system = 'cloudmold-metadata';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_metadata_dataset_version_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at, correlation_id,
       causation_id, idempotency_key,
       get_json_string(payload, '$.definition_id') AS definition_id,
       get_json_string(payload, '$.definition_code') AS definition_code,
       CAST(get_json_string(payload, '$.definition_version') AS BIGINT) AS definition_version,
       get_json_string(payload, '$.display_name') AS display_name,
       get_json_string(payload, '$.owner_principal_id') AS owner_principal_id,
       get_json_string(payload, '$.specification_sha256') AS specification_sha256,
       get_json_string(payload, '$.artifact_ref') AS artifact_ref,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.data_source_id') AS data_source_id,
       CAST(get_json_string(payload, '$.data_source_version') AS BIGINT) AS data_source_version,
       get_json_string(payload, '$.dataset_type') AS dataset_type,
       get_json_string(payload, '$.qualified_name') AS qualified_name,
       get_json_string(payload, '$.layer_code') AS layer_code,
       get_json_string(payload, '$.grain_code') AS grain_code,
       get_json_string(payload, '$.schema_sha256') AS schema_sha256,
       get_json_string(payload, '$.storage_location_ref') AS storage_location_ref,
       CAST(get_json_string(payload, '$.retention_days') AS BIGINT) AS retention_days,
       CAST(get_json_string(payload, '$.field_count') AS BIGINT) AS field_count
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'metadata.dataset.version_published' AND schema_version = 1
  AND source_system = 'cloudmold-metadata';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_metadata_dataset_field_version_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, event_sequence, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.dataset_id') AS dataset_id,
       CAST(get_json_string(payload, '$.dataset_version') AS BIGINT) AS dataset_version,
       CAST(get_json_string(payload, '$.ordinal_position') AS BIGINT) AS ordinal_position,
       get_json_string(payload, '$.field_code') AS field_code,
       get_json_string(payload, '$.data_type') AS data_type,
       CAST(get_json_string(payload, '$.nullable') AS BOOLEAN) AS nullable,
       CAST(get_json_string(payload, '$.primary_key_part') AS BOOLEAN) AS primary_key_part,
       get_json_string(payload, '$.semantic_type') AS semantic_type,
       get_json_string(payload, '$.classification') AS classification
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'metadata.dataset_field.version_published' AND schema_version = 1
  AND source_system = 'cloudmold-metadata';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_metadata_task_version_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at, correlation_id,
       causation_id, idempotency_key,
       get_json_string(payload, '$.definition_id') AS definition_id,
       get_json_string(payload, '$.definition_code') AS definition_code,
       CAST(get_json_string(payload, '$.definition_version') AS BIGINT) AS definition_version,
       get_json_string(payload, '$.display_name') AS display_name,
       get_json_string(payload, '$.owner_principal_id') AS owner_principal_id,
       get_json_string(payload, '$.specification_sha256') AS specification_sha256,
       get_json_string(payload, '$.artifact_ref') AS artifact_ref,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.task_type') AS task_type,
       get_json_string(payload, '$.executable_artifact_ref') AS executable_artifact_ref,
       get_json_string(payload, '$.code_sha256') AS code_sha256,
       get_json_string(payload, '$.schedule_sha256') AS schedule_sha256,
       get_json_string(payload, '$.resource_group_ref') AS resource_group_ref,
       CAST(get_json_string(payload, '$.dependency_count') AS BIGINT) AS dependency_count,
       get_json_string(payload, '$.service_level_code') AS service_level_code,
       CAST(get_json_string(payload, '$.deadline_minute_utc') AS BIGINT) AS deadline_minute_utc,
       CAST(get_json_string(payload, '$.maximum_duration_millis') AS BIGINT) AS maximum_duration_millis,
       CAST(get_json_string(payload, '$.maximum_freshness_millis') AS BIGINT) AS maximum_freshness_millis,
       get_json_string(payload, '$.sla_approved_by_principal_id') AS sla_approved_by_principal_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'metadata.task.version_published' AND schema_version = 1
  AND source_system = 'cloudmold-metadata';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_metadata_task_dependency_version_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, event_sequence, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.task_id') AS task_id,
       CAST(get_json_string(payload, '$.task_version') AS BIGINT) AS task_version,
       CAST(get_json_string(payload, '$.dependency_sequence') AS BIGINT) AS dependency_sequence,
       get_json_string(payload, '$.upstream_task_id') AS upstream_task_id,
       CAST(get_json_string(payload, '$.upstream_task_version') AS BIGINT) AS upstream_task_version,
       get_json_string(payload, '$.dependency_type') AS dependency_type,
       CAST(get_json_string(payload, '$.required') AS BOOLEAN) AS required
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'metadata.task_dependency.version_published' AND schema_version = 1
  AND source_system = 'cloudmold-metadata';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_metadata_task_run_observation_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at AS observed_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.run_id') AS run_id,
       get_json_string(payload, '$.task_id') AS task_id,
       CAST(get_json_string(payload, '$.task_version') AS BIGINT) AS task_version,
       CAST(get_json_string(payload, '$.attempt') AS BIGINT) AS attempt,
       CAST(get_json_string(payload, '$.observation_sequence') AS BIGINT) AS observation_sequence,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       CAST(get_json_string(payload, '$.scheduled_at') AS DATETIME) AS scheduled_at,
       CAST(get_json_string(payload, '$.started_at') AS DATETIME) AS started_at,
       CAST(get_json_string(payload, '$.finished_at') AS DATETIME) AS finished_at,
       CAST(get_json_string(payload, '$.duration_millis') AS BIGINT) AS duration_millis,
       CAST(get_json_string(payload, '$.compute_cost_minor') AS BIGINT) AS compute_cost_minor,
       get_json_string(payload, '$.cost_currency') AS cost_currency,
       CAST(get_json_string(payload, '$.resource_millis') AS BIGINT) AS resource_millis,
       CAST(get_json_string(payload, '$.rows_read') AS BIGINT) AS rows_read,
       CAST(get_json_string(payload, '$.rows_written') AS BIGINT) AS rows_written,
       get_json_string(payload, '$.source_checkpoint_ref') AS source_checkpoint_ref,
       get_json_string(payload, '$.output_snapshot_ref') AS output_snapshot_ref,
       get_json_string(payload, '$.error_ref') AS error_ref
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'metadata.task_run.observed' AND schema_version = 1
  AND source_system = 'cloudmold-metadata';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_metadata_lineage_version_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at, correlation_id,
       causation_id, idempotency_key,
       get_json_string(payload, '$.definition_id') AS definition_id,
       get_json_string(payload, '$.definition_code') AS definition_code,
       CAST(get_json_string(payload, '$.definition_version') AS BIGINT) AS definition_version,
       get_json_string(payload, '$.display_name') AS display_name,
       get_json_string(payload, '$.owner_principal_id') AS owner_principal_id,
       get_json_string(payload, '$.specification_sha256') AS specification_sha256,
       get_json_string(payload, '$.artifact_ref') AS artifact_ref,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.source_dataset_id') AS source_dataset_id,
       CAST(get_json_string(payload, '$.source_dataset_version') AS BIGINT) AS source_dataset_version,
       get_json_string(payload, '$.target_dataset_id') AS target_dataset_id,
       CAST(get_json_string(payload, '$.target_dataset_version') AS BIGINT) AS target_dataset_version,
       get_json_string(payload, '$.direction') AS direction,
       get_json_string(payload, '$.transform_sha256') AS transform_sha256,
       get_json_string(payload, '$.transformation_ref') AS transformation_ref
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'metadata.lineage.version_published' AND schema_version = 1
  AND source_system = 'cloudmold-metadata';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_metadata_dqc_rule_version_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at, correlation_id,
       causation_id, idempotency_key,
       get_json_string(payload, '$.definition_id') AS definition_id,
       get_json_string(payload, '$.definition_code') AS definition_code,
       CAST(get_json_string(payload, '$.definition_version') AS BIGINT) AS definition_version,
       get_json_string(payload, '$.display_name') AS display_name,
       get_json_string(payload, '$.owner_principal_id') AS owner_principal_id,
       get_json_string(payload, '$.specification_sha256') AS specification_sha256,
       get_json_string(payload, '$.artifact_ref') AS artifact_ref,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.dataset_id') AS dataset_id,
       CAST(get_json_string(payload, '$.dataset_version') AS BIGINT) AS dataset_version,
       get_json_string(payload, '$.dataset_field') AS dataset_field,
       get_json_string(payload, '$.rule_type') AS rule_type,
       get_json_string(payload, '$.severity') AS severity,
       get_json_string(payload, '$.expression_sha256') AS expression_sha256,
       CAST(get_json_string(payload, '$.threshold_value') AS DECIMAL(38,9)) AS threshold_value,
       get_json_string(payload, '$.threshold_comparator') AS threshold_comparator
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'metadata.dqc_rule.version_published' AND schema_version = 1
  AND source_system = 'cloudmold-metadata';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_metadata_dqc_result_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at, correlation_id,
       causation_id, idempotency_key,
       get_json_string(payload, '$.result_id') AS result_id,
       get_json_string(payload, '$.dqc_rule_id') AS dqc_rule_id,
       CAST(get_json_string(payload, '$.dqc_rule_version') AS BIGINT) AS dqc_rule_version,
       get_json_string(payload, '$.dataset_id') AS dataset_id,
       CAST(get_json_string(payload, '$.dataset_version') AS BIGINT) AS dataset_version,
       get_json_string(payload, '$.task_run_id') AS task_run_id,
       CAST(get_json_string(payload, '$.task_run_observation_sequence') AS BIGINT) AS task_run_observation_sequence,
       get_json_string(payload, '$.result_status') AS result_status,
       CAST(get_json_string(payload, '$.expected_value') AS DECIMAL(38,9)) AS expected_value,
       CAST(get_json_string(payload, '$.actual_value') AS DECIMAL(38,9)) AS actual_value,
       CAST(get_json_string(payload, '$.evaluated_rows') AS BIGINT) AS evaluated_rows,
       CAST(get_json_string(payload, '$.violation_count') AS BIGINT) AS violation_count,
       get_json_string(payload, '$.evidence_ref') AS evidence_ref,
       CAST(get_json_string(payload, '$.observed_at') AS DATETIME) AS observed_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'metadata.dqc_result.recorded' AND schema_version = 1
  AND source_system = 'cloudmold-metadata';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_metadata_metric_version_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at, correlation_id,
       causation_id, idempotency_key,
       get_json_string(payload, '$.definition_id') AS definition_id,
       get_json_string(payload, '$.definition_code') AS definition_code,
       CAST(get_json_string(payload, '$.definition_version') AS BIGINT) AS definition_version,
       get_json_string(payload, '$.display_name') AS display_name,
       get_json_string(payload, '$.owner_principal_id') AS owner_principal_id,
       get_json_string(payload, '$.specification_sha256') AS specification_sha256,
       get_json_string(payload, '$.artifact_ref') AS artifact_ref,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.grain_code') AS grain_code,
       get_json_string(payload, '$.metric_unit') AS metric_unit,
       get_json_string(payload, '$.aggregation_type') AS aggregation_type,
       get_json_string(payload, '$.expression_sha256') AS expression_sha256,
       get_json_string(payload, '$.filter_sha256') AS filter_sha256,
       get_json_string(payload, '$.dimensions_sha256') AS dimensions_sha256,
       get_json_string(payload, '$.semantic_version') AS semantic_version
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'metadata.metric.version_published' AND schema_version = 1
  AND source_system = 'cloudmold-metadata';
