CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_quality_readiness AS
WITH task_rollup AS (
    SELECT
        tenant_id,
        COUNT(DISTINCT CASE WHEN aggregate_type='inspection_task' THEN aggregate_id END)
            AS inspection_task_count,
        COUNT(DISTINCT CASE WHEN aggregate_type='inspection_task'
                             AND current_status='COMPLETED' THEN aggregate_id END)
            AS completed_inspection_task_count,
        COUNT(DISTINCT CASE WHEN aggregate_type='inspection_task'
                             AND COALESCE(ground_truth_decision,decision)='PASS'
                            THEN aggregate_id END)
            AS passed_inspection_task_count,
        COUNT(DISTINCT CASE WHEN aggregate_type='inspection_task'
                             AND COALESCE(ground_truth_decision,decision)='FAIL'
                            THEN aggregate_id END)
            AS failed_inspection_task_count,
        COUNT(DISTINCT CASE WHEN aggregate_type='inspection_task'
                             AND secondary_decision IS NOT NULL THEN aggregate_id END)
            AS independently_rechecked_task_count,
        COUNT(DISTINCT CASE WHEN aggregate_type='inspection_task'
                             AND secondary_decision=decision THEN aggregate_id END)
            AS reviewer_agreement_task_count,
        COUNT(DISTINCT CASE WHEN aggregate_type='inspection_task'
                             AND adjudicator_principal_id IS NOT NULL THEN aggregate_id END)
            AS adjudicated_task_count,
        COUNT(DISTINCT CASE WHEN aggregate_type='inspection_task'
                             AND ground_truth_decision IS NOT NULL THEN aggregate_id END)
            AS ground_truth_task_count,
        COUNT(DISTINCT CASE WHEN aggregate_type='inspection_task'
                             AND ground_truth_decision=decision THEN aggregate_id END)
            AS correct_primary_decision_task_count,
        COUNT(DISTINCT CASE WHEN aggregate_type='inspection_task'
                             AND ground_truth_decision='FAIL' THEN aggregate_id END)
            AS ground_truth_failed_task_count,
        COUNT(DISTINCT CASE WHEN aggregate_type='inspection_task'
                             AND ground_truth_decision='FAIL'
                             AND decision='FAIL' THEN aggregate_id END)
            AS detected_failed_task_count,
        COUNT(DISTINCT CASE WHEN aggregate_type='inspection_task'
                             AND decision='FAIL'
                             AND ground_truth_decision IS NOT NULL THEN aggregate_id END)
            AS primary_failed_decision_task_count,
        COUNT(DISTINCT CASE WHEN aggregate_type='quality_recall_action'
                             AND current_status IN ('OPEN','ACKNOWLEDGED')
                            THEN aggregate_id END) AS active_recall_action_count,
        MAX(recorded_at) AS data_freshness_at
    FROM yshopping_dws.dws_canonical_quality_current
    GROUP BY tenant_id
), recheck_rollup AS (
    SELECT
        tenant_id,
        COUNT(DISTINCT CASE WHEN current_status='RECHECK_REQUIRED' THEN aggregate_id END)
            AS recheck_task_count
    FROM yshopping_dwd.dwd_canonical_quality_event
    WHERE aggregate_type='inspection_task'
    GROUP BY tenant_id
)
SELECT
    task.tenant_id,
    task.inspection_task_count,
    task.completed_inspection_task_count,
    task.passed_inspection_task_count,
    task.failed_inspection_task_count,
    task.independently_rechecked_task_count,
    task.reviewer_agreement_task_count,
    task.adjudicated_task_count,
    task.ground_truth_task_count,
    task.correct_primary_decision_task_count,
    task.ground_truth_failed_task_count,
    task.detected_failed_task_count,
    task.primary_failed_decision_task_count,
    task.active_recall_action_count,
    COALESCE(recheck.recheck_task_count, 0) AS recheck_task_count,
    CAST(task.passed_inspection_task_count * 100.0
         / NULLIF(task.passed_inspection_task_count + task.failed_inspection_task_count, 0)
         AS DECIMAL(18,6)) AS inspection_pass_rate,
    CAST(COALESCE(recheck.recheck_task_count, 0) * 100.0
         / NULLIF(task.inspection_task_count, 0)
         AS DECIMAL(18,6)) AS recheck_rate,
    CAST(task.reviewer_agreement_task_count * 100.0
         / NULLIF(task.independently_rechecked_task_count, 0)
         AS DECIMAL(18,6)) AS independent_review_agreement_rate,
    CAST(task.correct_primary_decision_task_count * 100.0
         / NULLIF(task.ground_truth_task_count, 0)
         AS DECIMAL(18,6)) AS authentication_accuracy_rate,
    CAST(task.detected_failed_task_count * 100.0
         / NULLIF(task.ground_truth_failed_task_count, 0)
         AS DECIMAL(18,6)) AS authentication_recall_rate,
    CAST(task.detected_failed_task_count * 100.0
         / NULLIF(task.primary_failed_decision_task_count, 0)
         AS DECIMAL(18,6)) AS authentication_precision_rate,
    task.data_freshness_at
FROM task_rollup task
LEFT JOIN recheck_rollup recheck ON recheck.tenant_id=task.tenant_id;
