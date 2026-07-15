-- Current-state enrichment for legacy coupons only. Template joins remain source-qualified.
-- No canonical allocation, refund, identity, event, or SCD2 semantics are implied.
CREATE OR REPLACE VIEW yshopping_dim.dim_legacy_coupon_current AS
SELECT
    coupon.*,
    template.name AS legacy_template_name,
    template.status AS legacy_template_status_code,
    template.total_count AS legacy_template_total_count,
    template.take_count AS legacy_template_take_count,
    template.use_count AS legacy_template_use_count,
    template.deleted AS legacy_template_is_deleted,
    template.id IS NULL AS missing_template_flag,
    CASE
        WHEN template.id IS NULL THEN 'MISSING_TEMPLATE'
        WHEN template.deleted = TRUE THEN 'DELETED_TEMPLATE'
        ELSE 'MATCHED_CURRENT_TEMPLATE'
    END AS template_match_status,
    'LEGACY_CURRENT_STATE_ENRICHMENT' AS dimension_semantics
FROM yshopping_dwd.dwd_legacy_coupon_current coupon
LEFT JOIN yshopping_ods.promotion_coupon_template template
  ON template.tenant_id = coupon.tenant_id
 AND template.id = coupon.legacy_coupon_template_id;
