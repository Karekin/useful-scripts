SELECT 'procurement_promise_current_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, promise_id
    FROM yshopping_dim.dim_canonical_procurement_purchase_promise_current
    GROUP BY tenant_id, promise_id
    HAVING COUNT(*) <> 1
) duplicates;

SELECT 'procurement_promise_invalid_current_fields', COUNT(*)
FROM yshopping_dim.dim_canonical_procurement_purchase_promise_current
WHERE promise_id IS NULL
   OR purchase_order_id IS NULL
   OR purchase_order_line_id IS NULL
   OR promised_receipt_at IS NULL
   OR promise_timezone IS NULL
   OR grace_minutes < 0
   OR pause_minutes < 0
   OR current_status NOT IN ('ACTIVE', 'CANCELLED');

SELECT 'procurement_otif_status_mismatch', COUNT(*)
FROM yshopping_dws.dws_canonical_procurement_otif_current
WHERE (otif_status = 'DUE_ON_TIME_IN_FULL' AND (comparable_otif <> TRUE OR on_time_in_full <> TRUE))
   OR (otif_status = 'PROMISE_PENDING_NOT_DUE' AND comparable_otif = TRUE)
   OR (promise_status = 'CANCELLED' AND otif_status <> 'PROMISE_CANCELLED');

SELECT 'procurement_otif_in_full_mismatch', COUNT(*)
FROM yshopping_dws.dws_canonical_procurement_otif_current
WHERE on_time_in_full = TRUE
  AND (on_time_received_quantity < ordered_quantity OR comparable_otif <> TRUE);

SELECT 'procurement_otif_metric_rate_mismatch', COUNT(*)
FROM yshopping_ads.ads_canonical_procurement_otif_metrics
WHERE due_purchase_order_count <= 0
   OR on_time_in_full_purchase_order_count > due_purchase_order_count
   OR on_time_in_full_promise_line_count > due_promise_line_count
   OR ABS(procurement_otif_rate
          - (on_time_in_full_purchase_order_count * 100.0 / due_purchase_order_count)) > 0.000001
   OR ABS(procurement_otif_line_rate
          - (on_time_in_full_promise_line_count * 100.0 / due_promise_line_count)) > 0.000001;
