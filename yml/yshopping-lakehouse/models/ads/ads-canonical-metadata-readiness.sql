CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_metadata_readiness AS
SELECT coverage.tenant_id, coverage.data_source_count, coverage.dataset_count, coverage.task_count,
       coverage.lineage_count, coverage.dqc_rule_count, coverage.metric_count,
       COALESCE(run_counts.task_run_count, 0) AS task_run_count,
       COALESCE(run_counts.terminal_task_run_count, 0) AS terminal_task_run_count,
       COALESCE(dqc_counts.dqc_result_count, 0) AS dqc_result_count,
       COALESCE(dqc_counts.failed_dqc_result_count, 0) AS failed_dqc_result_count,
       COALESCE(dataset_counts.unresolved_data_source_version_count, 0) AS unresolved_data_source_version_count,
       COALESCE(dataset_counts.unreplayable_field_inventory_count, 0) AS unreplayable_field_inventory_count,
       COALESCE(dataset_counts.unclassified_field_inventory_count, 0) AS unclassified_field_inventory_count,
       COALESCE(dependency_counts.invalid_direct_dependency_graph_count, 0)
         AS invalid_direct_dependency_graph_count,
       COALESCE(lineage_counts.unresolved_lineage_endpoint_count, 0) AS unresolved_lineage_endpoint_count,
       COALESCE(run_counts.invalid_task_run_count, 0) AS invalid_task_run_count,
       COALESCE(dqc_counts.invalid_dqc_reference_count, 0) AS invalid_dqc_reference_count,
       true AS definition_version_history_preserved,
       true AS task_run_append_only_observation_preserved,
       true AS dqc_exact_task_run_sequence_preserved,
       CASE WHEN coverage.dataset_count > 0
                  AND COALESCE(dataset_counts.unreplayable_field_inventory_count, 0) = 0
            THEN true ELSE false END AS dataset_field_inventory_replayable,
       CASE WHEN coverage.dataset_count > 0
                  AND COALESCE(dataset_counts.unclassified_field_inventory_count, 0) = 0
            THEN true ELSE false END AS field_classification_replayable,
       CASE WHEN coverage.task_count > 0
                  AND COALESCE(dependency_counts.invalid_direct_dependency_graph_count, 0) = 0
            THEN true ELSE false END AS direct_task_dependency_graph_replayable,
       false AS task_dependency_graph_replayable,
       false AS transitive_dag_runtime_verified,
       false AS nonempty_runtime_reconciled,
       'FIRST_SLICE_PARTIAL' AS readiness_status
FROM yshopping_dws.dws_canonical_metadata_tenant_coverage_current coverage
LEFT JOIN (
    SELECT tenant_id, COUNT(*) AS task_run_count,
           SUM(CASE WHEN current_status IN ('SUCCEEDED','FAILED','CANCELLED') THEN 1 ELSE 0 END) AS terminal_task_run_count,
           SUM(CASE WHEN exact_task_version_resolved = false
                      OR observation_count <> distinct_sequence_count
                      OR observation_sequence <> maximum_sequence THEN 1 ELSE 0 END) AS invalid_task_run_count
    FROM yshopping_dws.dws_canonical_metadata_task_run_current GROUP BY tenant_id
) run_counts ON run_counts.tenant_id = coverage.tenant_id
LEFT JOIN (
    SELECT tenant_id, COUNT(*) AS dqc_result_count,
           SUM(CASE WHEN result_status IN ('FAIL','ERROR') THEN 1 ELSE 0 END) AS failed_dqc_result_count,
           SUM(CASE WHEN exact_rule_version_resolved = false OR exact_dataset_version_resolved = false
                      OR exact_task_run_observation_resolved = false OR exact_rule_target_match = false
                      OR exact_dataset_field_inventory_replayable = false
                    THEN 1 ELSE 0 END) AS invalid_dqc_reference_count
    FROM yshopping_dws.dws_canonical_metadata_dqc_evaluation_current GROUP BY tenant_id
) dqc_counts ON dqc_counts.tenant_id = coverage.tenant_id
LEFT JOIN (
    SELECT tenant_id,
           SUM(CASE WHEN exact_data_source_version_resolved = false THEN 1 ELSE 0 END)
             AS unresolved_data_source_version_count,
           SUM(CASE WHEN dataset_field_inventory_replayable = false THEN 1 ELSE 0 END)
             AS unreplayable_field_inventory_count,
           SUM(CASE WHEN field_classification_replayable = false THEN 1 ELSE 0 END)
             AS unclassified_field_inventory_count
    FROM yshopping_dws.dws_canonical_metadata_dataset_governance_current GROUP BY tenant_id
) dataset_counts ON dataset_counts.tenant_id = coverage.tenant_id
LEFT JOIN (
    SELECT task.tenant_id,
           SUM(CASE WHEN COALESCE(edges.observed_dependency_count, 0) <> task.dependency_count
                      OR COALESCE(edges.distinct_dependency_sequence_count, 0) <> task.dependency_count
                      OR COALESCE(edges.distinct_direct_edge_count, 0) <> task.dependency_count
                      OR COALESCE(edges.minimum_dependency_sequence, 1) <> 1
                      OR COALESCE(edges.maximum_dependency_sequence, 0) <> task.dependency_count
                      OR COALESCE(edges.invalid_edge_count, 0) > 0
                    THEN 1 ELSE 0 END) AS invalid_direct_dependency_graph_count
    FROM yshopping_dim.dim_canonical_metadata_task_current task
    LEFT JOIN (
        SELECT tenant_id, task_id, task_version, COUNT(*) AS observed_dependency_count,
               COUNT(DISTINCT dependency_sequence) AS distinct_dependency_sequence_count,
               COUNT(DISTINCT CONCAT(upstream_task_id, '|', dependency_type)) AS distinct_direct_edge_count,
               MIN(dependency_sequence) AS minimum_dependency_sequence,
               MAX(dependency_sequence) AS maximum_dependency_sequence,
               SUM(CASE WHEN exact_task_version_resolved = false
                          OR exact_upstream_task_version_resolved = false
                          OR exact_detail_sequence = false OR task_id = upstream_task_id
                        THEN 1 ELSE 0 END) AS invalid_edge_count
        FROM yshopping_dws.dws_canonical_metadata_task_dependency_edge_current
        GROUP BY tenant_id, task_id, task_version
    ) edges ON edges.tenant_id = task.tenant_id AND edges.task_id = task.definition_id
           AND edges.task_version = task.definition_version
    GROUP BY task.tenant_id
) dependency_counts ON dependency_counts.tenant_id = coverage.tenant_id
LEFT JOIN (
    SELECT tenant_id, SUM(CASE WHEN exact_source_version_resolved = false OR exact_target_version_resolved = false
                              THEN 1 ELSE 0 END) AS unresolved_lineage_endpoint_count
    FROM yshopping_dws.dws_canonical_metadata_lineage_edge_current GROUP BY tenant_id
) lineage_counts ON lineage_counts.tenant_id = coverage.tenant_id;
