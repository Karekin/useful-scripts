-- Tenant/user aggregate of legacy coupon current rows; not allocation or redemption history.
CREATE OR REPLACE VIEW yshopping_dws.dws_legacy_coupon_current AS
SELECT
    tenant_id,
    legacy_user_id,
    COUNT(*) AS current_coupon_row_count,
    SUM(CASE WHEN is_deleted = FALSE THEN 1 ELSE 0 END) AS non_deleted_coupon_row_count,
    SUM(CASE WHEN is_deleted = FALSE AND coupon_status_code = 1 THEN 1 ELSE 0 END) AS unused_coupon_row_count,
    SUM(CASE WHEN is_deleted = FALSE AND coupon_status_code = 2 THEN 1 ELSE 0 END) AS used_coupon_row_count,
    SUM(CASE WHEN is_deleted = FALSE AND coupon_status_code = 3 THEN 1 ELSE 0 END) AS expired_coupon_row_count,
    COUNT(DISTINCT legacy_coupon_template_id) AS legacy_template_count,
    SUM(CASE WHEN invalid_time_window_flag THEN 1 ELSE 0 END) AS invalid_time_window_count,
    SUM(CASE WHEN invalid_status_flag THEN 1 ELSE 0 END) AS invalid_status_count,
    SUM(CASE WHEN invalid_discount_rule_flag THEN 1 ELSE 0 END) AS invalid_discount_rule_count,
    SUM(CASE WHEN incomplete_used_state_flag THEN 1 ELSE 0 END) AS incomplete_used_state_count,
    SUM(CASE WHEN missing_template_flag THEN 1 ELSE 0 END) AS missing_template_count,
    MAX(source_updated_at) AS latest_source_updated_at,
    'LEGACY_CURRENT_STATE_AGGREGATE' AS model_semantics
FROM yshopping_dim.dim_legacy_coupon_current
GROUP BY tenant_id, legacy_user_id;
