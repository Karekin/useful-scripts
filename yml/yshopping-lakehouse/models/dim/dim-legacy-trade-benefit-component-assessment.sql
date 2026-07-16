-- One explicit legacy benefit component per non-zero header amount.
-- Missing source version and named-funder evidence remain blocking facts.
CREATE OR REPLACE VIEW yshopping_dim.dim_legacy_trade_benefit_component_assessment AS
SELECT
    source_system, tenant_id, legacy_order_id, legacy_order_no, legacy_order_key,
    'GENERIC_DISCOUNT' AS legacy_component_type,
    header_generic_discount_amount_minor AS component_amount_minor,
    CASE
      WHEN (CASE WHEN legacy_seckill_activity_id IS NULL THEN 0 ELSE 1 END
          + CASE WHEN legacy_bargain_activity_id IS NULL THEN 0 ELSE 1 END
          + CASE WHEN legacy_combination_activity_id IS NULL THEN 0 ELSE 1 END
          + CASE WHEN legacy_point_activity_id IS NULL THEN 0 ELSE 1 END) = 1
        THEN 'SOURCE_REFERENCE_WITHOUT_VERSION'
      WHEN (CASE WHEN legacy_seckill_activity_id IS NULL THEN 0 ELSE 1 END
          + CASE WHEN legacy_bargain_activity_id IS NULL THEN 0 ELSE 1 END
          + CASE WHEN legacy_combination_activity_id IS NULL THEN 0 ELSE 1 END
          + CASE WHEN legacy_point_activity_id IS NULL THEN 0 ELSE 1 END) > 1
        THEN 'AMBIGUOUS_SOURCE_REFERENCE'
      ELSE 'MISSING_SOURCE_REFERENCE'
    END AS identity_resolution_status,
    'MISSING_NAMED_FUNDER_BREAKDOWN' AS funding_resolution_status,
    assessment_status AS order_assessment_status,
    FALSE AS canonical_import_allowed,
    'LEGACY_TRADE_BENEFIT_COMPONENT_ASSESSMENT' AS model_semantics
FROM yshopping_dwd.dwd_legacy_trade_benefit_assessment
WHERE is_deleted = FALSE AND header_generic_discount_amount_minor <> 0
UNION ALL
SELECT
    source_system, tenant_id, legacy_order_id, legacy_order_no, legacy_order_key,
    'COUPON' AS legacy_component_type,
    header_coupon_amount_minor AS component_amount_minor,
    CASE WHEN legacy_coupon_id IS NULL OR legacy_coupon_id = 0
         THEN 'MISSING_SOURCE_REFERENCE' ELSE 'SOURCE_REFERENCE_WITHOUT_VERSION' END,
    'MISSING_NAMED_FUNDER_BREAKDOWN', assessment_status, FALSE,
    'LEGACY_TRADE_BENEFIT_COMPONENT_ASSESSMENT'
FROM yshopping_dwd.dwd_legacy_trade_benefit_assessment
WHERE is_deleted = FALSE AND header_coupon_amount_minor <> 0
UNION ALL
SELECT
    source_system, tenant_id, legacy_order_id, legacy_order_no, legacy_order_key,
    'POINT' AS legacy_component_type,
    header_point_amount_minor AS component_amount_minor,
    CASE WHEN legacy_used_point_quantity <= 0
         THEN 'MISSING_SOURCE_REFERENCE' ELSE 'MISSING_ENTITLEMENT_VERSION' END,
    'MISSING_NAMED_FUNDER_BREAKDOWN', assessment_status, FALSE,
    'LEGACY_TRADE_BENEFIT_COMPONENT_ASSESSMENT'
FROM yshopping_dwd.dwd_legacy_trade_benefit_assessment
WHERE is_deleted = FALSE AND header_point_amount_minor <> 0
UNION ALL
SELECT
    source_system, tenant_id, legacy_order_id, legacy_order_no, legacy_order_key,
    'VIP' AS legacy_component_type,
    header_vip_amount_minor AS component_amount_minor,
    'MISSING_BENEFIT_VERSION' AS identity_resolution_status,
    'MISSING_NAMED_FUNDER_BREAKDOWN' AS funding_resolution_status,
    assessment_status AS order_assessment_status,
    FALSE AS canonical_import_allowed,
    'LEGACY_TRADE_BENEFIT_COMPONENT_ASSESSMENT' AS model_semantics
FROM yshopping_dwd.dwd_legacy_trade_benefit_assessment
WHERE is_deleted = FALSE AND header_vip_amount_minor <> 0;
