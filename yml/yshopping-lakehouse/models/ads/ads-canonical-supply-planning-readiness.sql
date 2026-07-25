CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_supply_planning_readiness AS
SELECT
    tenant_id,
    COUNT(DISTINCT CASE WHEN aggregate_type='demand_forecast' THEN aggregate_id END)
        AS forecast_count,
    COUNT(DISTINCT CASE WHEN aggregate_type='demand_forecast'
                         AND current_status='PUBLISHED' THEN aggregate_id END)
        AS published_forecast_count,
    COUNT(DISTINCT CASE WHEN aggregate_type='supply_plan' THEN aggregate_id END)
        AS supply_plan_count,
    COUNT(DISTINCT CASE WHEN aggregate_type='supply_plan'
                         AND current_status='APPROVED' THEN aggregate_id END)
        AS approved_supply_plan_count,
    COUNT(DISTINCT CASE WHEN aggregate_type='supply_plan'
                         AND current_status='RELEASED' THEN aggregate_id END)
        AS released_supply_plan_count,
    COUNT(DISTINCT CASE WHEN aggregate_type='supply_plan_scenario'
                         AND current_status='SELECTED' THEN aggregate_id END)
        AS selected_scenario_count,
    COUNT(DISTINCT CASE WHEN aggregate_type='replenishment_recommendation'
                         THEN aggregate_id END) AS replenishment_count,
    COUNT(DISTINCT CASE WHEN aggregate_type='replenishment_recommendation'
                         AND current_status='APPROVED' THEN aggregate_id END)
        AS approved_replenishment_count,
    COUNT(DISTINCT CASE WHEN aggregate_type='replenishment_recommendation'
                         AND current_status='CONVERTED' THEN aggregate_id END)
        AS converted_replenishment_count,
    COUNT(DISTINCT CASE WHEN aggregate_type='forecast_evaluation' THEN aggregate_id END)
        AS forecast_evaluation_count,
    CAST(AVG(CASE WHEN aggregate_type='forecast_evaluation'
                  THEN wape_basis_points END) AS DECIMAL(18,6))
        AS average_wape_basis_points,
    CAST(AVG(CASE WHEN aggregate_type='forecast_evaluation'
                  THEN bias_basis_points END) AS DECIMAL(18,6))
        AS average_bias_basis_points,
    CAST(AVG(CASE WHEN aggregate_type='forecast_evaluation'
                  THEN mae END) AS DECIMAL(24,6)) AS average_mae,
    COUNT(DISTINCT CASE WHEN aggregate_type='supply_plan_scenario' THEN aggregate_id END)
        AS evaluated_scenario_count,
    CAST(AVG(CASE WHEN aggregate_type='supply_plan_scenario'
                  THEN projected_service_level_basis_points END) AS DECIMAL(18,6))
        AS average_projected_service_level_basis_points,
    COUNT(DISTINCT CASE WHEN aggregate_type='inventory_health_scan' THEN aggregate_id END)
        AS inventory_health_scan_count,
    SUM(CASE WHEN aggregate_type='inventory_health_scan'
             THEN COALESCE(scan_issue_count,0) ELSE 0 END) AS scan_created_issue_count,
    COUNT(DISTINCT CASE WHEN aggregate_type='inventory_health_issue'
                         AND current_status IN ('OPEN','ACKNOWLEDGED') THEN aggregate_id END)
        AS active_inventory_issue_count,
    MAX(recorded_at) AS data_freshness_at
FROM yshopping_dws.dws_canonical_supply_planning_current
GROUP BY tenant_id;
