CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_supply_planning_event AS
SELECT
    event_id,
    event_type,
    schema_version,
    tenant_id,
    aggregate_type,
    aggregate_id,
    aggregate_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.forecast_id') AS forecast_id,
    get_json_string(payload, '$.forecast_code') AS forecast_code,
    get_json_string(payload, '$.plan_id') AS plan_id,
    get_json_string(payload, '$.plan_code') AS plan_code,
    get_json_string(payload, '$.demand_forecast_id') AS demand_forecast_id,
    get_json_string(payload, '$.recommendation_id') AS recommendation_id,
    get_json_string(payload, '$.issue_id') AS issue_id,
    get_json_string(payload, '$.canonical_sku_id') AS canonical_sku_id,
    get_json_string(payload, '$.warehouse_id') AS warehouse_id,
    get_json_string(payload, '$.source_balance_id') AS source_balance_id,
    get_json_string(payload, '$.issue_type') AS issue_type,
    get_json_string(payload, '$.severity') AS severity,
    get_json_string(payload, '$.previous_status') AS previous_status,
    COALESCE(
        get_json_string(payload, '$.current_status'),
        CASE event_type
            WHEN 'supply_planning.forecast.created' THEN 'DRAFT'
            WHEN 'supply_planning.forecast.published' THEN 'PUBLISHED'
            WHEN 'supply_planning.plan.created' THEN 'DRAFT'
            WHEN 'supply_planning.plan.approved' THEN 'APPROVED'
            WHEN 'supply_planning.replenishment.created' THEN 'PROPOSED'
            WHEN 'supply_planning.inventory_issue.opened' THEN 'OPEN'
        END
    ) AS current_status,
    CAST(get_json_string(payload, '$.suggested_quantity') AS DECIMAL(24,6))
        AS suggested_quantity,
    get_json_string(payload, '$.uom_code') AS uom_code,
    get_json_string(payload, '$.need_by_date') AS need_by_date,
    get_json_string(payload, '$.reason_code') AS reason_code,
    get_json_string(payload, '$.decision') AS decision,
    get_json_string(payload, '$.decision_principal_id') AS decision_principal_id,
    get_json_string(payload, '$.owner_principal_id') AS owner_principal_id,
    get_json_string(payload, '$.resolution_code') AS resolution_code,
    CAST(get_json_string(payload, '$.point_count') AS BIGINT) AS point_count,
    get_json_string(payload, '$.horizon_start') AS horizon_start,
    get_json_string(payload, '$.horizon_end') AS horizon_end,
    get_json_string(payload, '$.bucket_type') AS bucket_type,
    get_json_string(payload, '$.model_ref') AS model_ref,
    get_json_string(payload, '$.baseline_sha256') AS baseline_sha256,
    CAST(get_json_string(payload, '$.target_service_level_basis_points') AS INT)
        AS target_service_level_basis_points,
    CAST(get_json_string(payload, '$.budget_amount_minor') AS BIGINT)
        AS budget_amount_minor,
    get_json_string(payload, '$.currency_code') AS currency_code,
    get_json_string(payload, '$.constraints_sha256') AS constraints_sha256
    ,get_json_string(payload, '$.evaluation_id') AS evaluation_id
    ,get_json_string(payload, '$.actuals_sha256') AS actuals_sha256
    ,CAST(get_json_string(payload, '$.forecast_quantity') AS DECIMAL(24,6))
        AS evaluation_forecast_quantity
    ,CAST(get_json_string(payload, '$.actual_quantity') AS DECIMAL(24,6))
        AS actual_quantity
    ,CAST(get_json_string(payload, '$.absolute_error') AS DECIMAL(24,6))
        AS absolute_error
    ,CAST(get_json_string(payload, '$.signed_error') AS DECIMAL(24,6))
        AS signed_error
    ,CAST(get_json_string(payload, '$.wape_basis_points') AS INT) AS wape_basis_points
    ,CAST(get_json_string(payload, '$.bias_basis_points') AS INT) AS bias_basis_points
    ,CAST(get_json_string(payload, '$.mae') AS DECIMAL(24,6)) AS mae
    ,get_json_string(payload, '$.scenario_id') AS scenario_id
    ,get_json_string(payload, '$.scenario_code') AS scenario_code
    ,get_json_string(payload, '$.selected_scenario_id') AS selected_scenario_id
    ,get_json_string(payload, '$.selected_by_principal_id') AS selected_by_principal_id
    ,get_json_string(payload, '$.release_principal_id') AS release_principal_id
    ,CAST(get_json_string(payload, '$.constrained_order_quantity') AS DECIMAL(24,6))
        AS constrained_order_quantity
    ,CAST(get_json_string(payload, '$.projected_shortage_quantity') AS DECIMAL(24,6))
        AS projected_shortage_quantity
    ,CAST(get_json_string(payload, '$.projected_service_level_basis_points') AS INT)
        AS projected_service_level_basis_points
    ,CAST(get_json_string(payload, '$.projected_cost_minor') AS BIGINT)
        AS projected_cost_minor
    ,get_json_string(payload, '$.solver_type') AS solver_type
    ,get_json_string(payload, '$.parameters_sha256') AS parameters_sha256
    ,get_json_string(payload, '$.conversion_id') AS conversion_id
    ,get_json_string(payload, '$.target_type') AS target_type
    ,get_json_string(payload, '$.target_reference') AS target_reference
    ,get_json_string(payload, '$.scan_id') AS scan_id
    ,get_json_string(payload, '$.detection_source') AS detection_source
    ,get_json_string(payload, '$.policy_code') AS policy_code
    ,get_json_string(payload, '$.policy_sha256') AS policy_sha256
    ,CAST(get_json_string(payload, '$.observation_count') AS BIGINT) AS observation_count
    ,CAST(get_json_string(payload, '$.issue_count') AS BIGINT) AS scan_issue_count
    ,CAST(get_json_string(payload, '$.skipped_active_count') AS BIGINT)
        AS skipped_active_count
FROM yshopping_dwd.dwd_domain_event
WHERE source_system = 'cloudmold-supply-planning'
  AND schema_version = 1
  AND event_type LIKE 'supply_planning.%';
