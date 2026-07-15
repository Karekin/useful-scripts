-- Legacy coupon current-row preservation and downstream exposure.
SELECT 'legacy_coupon_source_to_dwd_count_mismatch' AS check_name,
       ABS((SELECT COUNT(*) FROM yshopping_ods.promotion_coupon)
         - (SELECT COUNT(*) FROM yshopping_dwd.dwd_legacy_coupon_current)) AS violations;

SELECT 'legacy_coupon_key_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, legacy_coupon_id
    FROM yshopping_dwd.dwd_legacy_coupon_current
    GROUP BY tenant_id, legacy_coupon_id
    HAVING COUNT(*) <> 1
) duplicate_keys;

SELECT 'legacy_coupon_dwd_to_dim_count_mismatch' AS check_name,
       ABS((SELECT COUNT(*) FROM yshopping_dwd.dwd_legacy_coupon_current)
         - (SELECT COUNT(*) FROM yshopping_dim.dim_legacy_coupon_current)) AS violations;

SELECT 'legacy_coupon_dim_to_dws_count_mismatch' AS check_name,
       ABS((SELECT COUNT(*) FROM yshopping_dim.dim_legacy_coupon_current)
         - (SELECT COALESCE(SUM(current_coupon_row_count), 0) FROM yshopping_dws.dws_legacy_coupon_current)) AS violations;

SELECT 'legacy_coupon_anomaly_not_exposed' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_legacy_coupon_current
WHERE unexposed_source_anomaly_row_count <> 0
   OR source_current_row_count <> exposed_current_row_count;

SELECT 'legacy_coupon_boundary_claim_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_legacy_coupon_current
WHERE canonical_coupon_identity_available <> FALSE
   OR allocation_event_history_available <> FALSE
   OR refund_semantics_available <> FALSE
   OR model_semantics <> 'LEGACY_CURRENT_STATE_READINESS';

-- Six legacy activity tables are preserved; point activity intentionally has no time window.
SELECT 'legacy_activity_source_to_dwd_count_mismatch' AS check_name,
       ABS(((SELECT COUNT(*) FROM yshopping_ods.promotion_bargain_activity)
          + (SELECT COUNT(*) FROM yshopping_ods.promotion_combination_activity)
          + (SELECT COUNT(*) FROM yshopping_ods.promotion_discount_activity)
          + (SELECT COUNT(*) FROM yshopping_ods.promotion_point_activity)
          + (SELECT COUNT(*) FROM yshopping_ods.promotion_reward_activity)
          + (SELECT COUNT(*) FROM yshopping_ods.promotion_seckill_activity))
         - (SELECT COUNT(*) FROM yshopping_dwd.dwd_legacy_activity_current)) AS violations;

SELECT 'legacy_activity_key_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT legacy_activity_key
    FROM yshopping_dwd.dwd_legacy_activity_current
    GROUP BY legacy_activity_key
    HAVING COUNT(*) <> 1
) duplicate_keys;

SELECT 'legacy_point_activity_time_contract_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_legacy_activity_current
WHERE source_table = 'promotion_point_activity'
  AND (time_window_applicable <> FALSE OR invalid_time_window_flag <> FALSE);

SELECT 'legacy_activity_dwd_to_dim_count_mismatch' AS check_name,
       ABS((SELECT COUNT(*) FROM yshopping_dwd.dwd_legacy_activity_current)
         - (SELECT COUNT(*) FROM yshopping_dim.dim_legacy_activity_current)) AS violations;

SELECT 'legacy_activity_dim_to_dws_count_mismatch' AS check_name,
       ABS((SELECT COUNT(*) FROM yshopping_dim.dim_legacy_activity_current)
         - (SELECT COALESCE(SUM(current_activity_row_count), 0) FROM yshopping_dws.dws_legacy_activity_current)) AS violations;

-- A source invalid time window is expected evidence. Failure means ADS failed to expose it.
SELECT 'legacy_activity_invalid_time_window_not_exposed' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_legacy_activity_current
WHERE unexposed_invalid_time_window_count <> 0
   OR source_current_row_count <> exposed_current_row_count;

SELECT 'legacy_activity_boundary_claim_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_legacy_activity_current
WHERE canonical_activity_identity_available <> FALSE
   OR activity_event_history_available <> FALSE
   OR model_semantics <> 'LEGACY_CURRENT_STATE_READINESS';

-- Legacy favorite current-row preservation and downstream exposure.
SELECT 'legacy_collect_source_to_dwd_count_mismatch' AS check_name,
       ABS((SELECT COUNT(*) FROM yshopping_ods.product_favorite)
         - (SELECT COUNT(*) FROM yshopping_dwd.dwd_legacy_collect_current)) AS violations;

SELECT 'legacy_collect_key_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, legacy_favorite_id
    FROM yshopping_dwd.dwd_legacy_collect_current
    GROUP BY tenant_id, legacy_favorite_id
    HAVING COUNT(*) <> 1
) duplicate_keys;

SELECT 'legacy_collect_dwd_to_dim_count_mismatch' AS check_name,
       ABS((SELECT COUNT(*) FROM yshopping_dwd.dwd_legacy_collect_current)
         - (SELECT COUNT(*) FROM yshopping_dim.dim_legacy_collect_current)) AS violations;

SELECT 'legacy_collect_dim_to_dws_count_mismatch' AS check_name,
       ABS((SELECT COUNT(*) FROM yshopping_dim.dim_legacy_collect_current)
         - (SELECT COALESCE(SUM(current_favorite_row_count), 0) FROM yshopping_dws.dws_legacy_collect_current)) AS violations;

SELECT 'legacy_collect_invalid_reference_not_exposed' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_legacy_collect_current
WHERE unexposed_invalid_reference_row_count <> 0
   OR source_current_row_count <> exposed_current_row_count;

SELECT 'legacy_collect_boundary_claim_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_legacy_collect_current
WHERE canonical_member_identity_available <> FALSE
   OR favorite_event_history_available <> FALSE
   OR preference_score_available <> FALSE
   OR reminder_effect_available <> FALSE
   OR model_semantics <> 'LEGACY_CURRENT_STATE_READINESS';
