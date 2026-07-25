-- Every result column must be zero.

SELECT 'forecast_accuracy_metric_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_supply_planning_current
WHERE aggregate_type='forecast_evaluation'
  AND (absolute_error<0 OR mae<0
       OR (actual_quantity=0
           AND (wape_basis_points IS NOT NULL OR bias_basis_points IS NOT NULL)));

SELECT 'supply_scenario_result_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_supply_planning_current
WHERE aggregate_type='supply_plan_scenario'
  AND (projected_shortage_quantity<0
       OR projected_service_level_basis_points NOT BETWEEN 0 AND 10000
       OR projected_cost_minor<0);

SELECT 'quality_review_independence_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_quality_current
WHERE aggregate_type='inspection_task'
  AND (secondary_authenticator_principal_id=authenticator_principal_id
       OR adjudicator_principal_id=authenticator_principal_id
       OR adjudicator_principal_id=secondary_authenticator_principal_id);

SELECT 'quality_ground_truth_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_quality_current
WHERE aggregate_type='inspection_task'
  AND ground_truth_decision IS NOT NULL
  AND (ground_truth_evidence_ref IS NULL
       OR (ground_truth_decision='FAIL' AND ground_truth_defect_code IS NULL));

SELECT 'quality_recall_without_lot_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_quality_current
WHERE aggregate_type='quality_recall_action'
  AND (lot_id IS NULL OR inspection_task_id IS NULL);
