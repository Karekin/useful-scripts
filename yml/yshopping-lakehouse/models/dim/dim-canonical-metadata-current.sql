-- Immutable definition-version histories and deterministic current projections.
CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_datasource_version_history AS
SELECT * FROM yshopping_dwd.dwd_canonical_metadata_datasource_version_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_datasource_current AS
SELECT * FROM (
    SELECT h.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, definition_id
        ORDER BY definition_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dim.dim_canonical_metadata_datasource_version_history h
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_dataset_version_history AS
SELECT * FROM yshopping_dwd.dwd_canonical_metadata_dataset_version_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_dataset_current AS
SELECT * FROM (
    SELECT h.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, definition_id
        ORDER BY definition_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dim.dim_canonical_metadata_dataset_version_history h
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_dataset_field_version_history AS
SELECT * FROM yshopping_dwd.dwd_canonical_metadata_dataset_field_version_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_dataset_field_current AS
SELECT field.*
FROM yshopping_dim.dim_canonical_metadata_dataset_field_version_history field
JOIN yshopping_dim.dim_canonical_metadata_dataset_current dataset
  ON dataset.tenant_id = field.tenant_id AND dataset.definition_id = field.dataset_id
 AND dataset.definition_version = field.dataset_version;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_task_version_history AS
SELECT * FROM yshopping_dwd.dwd_canonical_metadata_task_version_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_task_current AS
SELECT * FROM (
    SELECT h.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, definition_id
        ORDER BY definition_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dim.dim_canonical_metadata_task_version_history h
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_task_dependency_version_history AS
SELECT * FROM yshopping_dwd.dwd_canonical_metadata_task_dependency_version_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_task_dependency_current AS
SELECT dependency.*
FROM yshopping_dim.dim_canonical_metadata_task_dependency_version_history dependency
JOIN yshopping_dim.dim_canonical_metadata_task_current task
  ON task.tenant_id = dependency.tenant_id AND task.definition_id = dependency.task_id
 AND task.definition_version = dependency.task_version;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_lineage_version_history AS
SELECT * FROM yshopping_dwd.dwd_canonical_metadata_lineage_version_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_lineage_current AS
SELECT * FROM (
    SELECT h.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, definition_id
        ORDER BY definition_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dim.dim_canonical_metadata_lineage_version_history h
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_dqc_rule_version_history AS
SELECT * FROM yshopping_dwd.dwd_canonical_metadata_dqc_rule_version_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_dqc_rule_current AS
SELECT * FROM (
    SELECT h.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, definition_id
        ORDER BY definition_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dim.dim_canonical_metadata_dqc_rule_version_history h
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_metric_version_history AS
SELECT * FROM yshopping_dwd.dwd_canonical_metadata_metric_version_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_metric_current AS
SELECT * FROM (
    SELECT h.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, definition_id
        ORDER BY definition_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dim.dim_canonical_metadata_metric_version_history h
) ranked WHERE rn = 1;

-- Task-run observations and DQC results are append-only facts; current means the greatest exact sequence/time.
CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_task_run_observation_history AS
SELECT * FROM yshopping_dwd.dwd_canonical_metadata_task_run_observation_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_task_run_current AS
SELECT * FROM (
    SELECT h.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, run_id
        ORDER BY observation_sequence DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dim.dim_canonical_metadata_task_run_observation_history h
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_dqc_result_history AS
SELECT * FROM yshopping_dwd.dwd_canonical_metadata_dqc_result_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_metadata_dqc_result_current AS
SELECT * FROM (
    SELECT h.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, result_id
        ORDER BY observed_at DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dim.dim_canonical_metadata_dqc_result_history h
) ranked WHERE rn = 1;
