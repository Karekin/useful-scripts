SELECT 'inventory_cost_v5_total_mismatch' AS check_name,
       COUNT(*) AS violation_count
FROM yshopping_dwd.dwd_canonical_inventory_movement
WHERE schema_version = 5
  AND CAST(delta_on_hand_quantity * unit_cost_amount_minor AS DECIMAL(38,6))
      <> CAST(CASE WHEN delta_on_hand_quantity < 0
                   THEN -movement_cost_amount_minor ELSE movement_cost_amount_minor END AS DECIMAL(38,6))
UNION ALL
SELECT 'inventory_cost_v5_missing_authority', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_movement
WHERE schema_version = 5
  AND (unit_cost_amount_minor IS NULL OR movement_cost_amount_minor IS NULL
       OR currency_code IS NULL OR cost_source_system IS NULL
       OR cost_source_ref IS NULL OR cost_policy_version IS NULL)
UNION ALL
SELECT 'inventory_cost_layer_negative_remaining', COUNT(*)
FROM yshopping_dws.dws_canonical_inventory_cost_layer_current
WHERE remaining_quantity <= 0 OR remaining_quantity > received_quantity
UNION ALL
SELECT 'inventory_cost_layer_value_mismatch', COUNT(*)
FROM yshopping_dws.dws_canonical_inventory_cost_layer_current
WHERE remaining_cost_amount_minor
      <> CAST(remaining_quantity * unit_cost_amount_minor AS DECIMAL(38,6))
UNION ALL
SELECT 'inventory_aged_value_exceeds_inventory_value', COUNT(*)
FROM yshopping_ads.ads_canonical_inventory_cost_aging_metrics
WHERE aged_stock_value_amount_minor < 0
   OR aged_stock_value_amount_minor > inventory_value_amount_minor
UNION ALL
SELECT 'inventory_turnover_days_formula_mismatch', COUNT(*)
FROM yshopping_ads.ads_canonical_inventory_cost_aging_metrics
WHERE readiness_status = 'READY_COSTED_FIFO_V1'
  AND ABS(inventory_turnover_days
          - CAST(inventory_value_amount_minor * 90.0 / cost_of_goods_sold_amount_minor AS DECIMAL(18,4))) > 0.0001
UNION ALL
SELECT 'inventory_cost_readiness_false_positive', COUNT(*)
FROM yshopping_ads.ads_canonical_inventory_cost_aging_metrics
WHERE readiness_status = 'READY_COSTED_FIFO_V1'
  AND (valued_balance_count <> cost_complete_balance_count
       OR cost_of_goods_sold_amount_minor <= 0
       OR costed_shipment_count <= 0);
