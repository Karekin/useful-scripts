CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_merchant_shop_current AS
SELECT
    merchant.tenant_id,
    merchant.merchant_id,
    merchant.legal_entity_id,
    legal_entity.current_status AS legal_entity_status,
    merchant.current_status AS merchant_status,
    shop.shop_id,
    shop.channel_code,
    shop.external_shop_id,
    shop.current_status AS shop_status,
    onboarding.application_id,
    onboarding.owner_principal_id,
    onboarding.current_status AS onboarding_status,
    COALESCE(assignment.active_operator_count, 0) AS active_operator_count,
    COALESCE(assignment.active_owner_count, 0) AS active_owner_count,
    GREATEST(
        merchant.recorded_at,
        shop.recorded_at,
        legal_entity.recorded_at,
        onboarding.recorded_at,
        COALESCE(assignment.assignment_freshness_at, merchant.recorded_at)
    ) AS data_freshness_at
FROM yshopping_dim.dim_canonical_merchant_current merchant
JOIN yshopping_dim.dim_canonical_shop_current shop
  ON shop.tenant_id=merchant.tenant_id AND shop.merchant_id=merchant.merchant_id
JOIN yshopping_dim.dim_canonical_merchant_legal_entity_current legal_entity
  ON legal_entity.tenant_id=merchant.tenant_id
 AND legal_entity.legal_entity_id=merchant.legal_entity_id
JOIN yshopping_dim.dim_canonical_merchant_onboarding_current onboarding
  ON onboarding.tenant_id=merchant.tenant_id
 AND onboarding.merchant_id=merchant.merchant_id
 AND onboarding.shop_id=shop.shop_id
LEFT JOIN (
    SELECT tenant_id, merchant_id, shop_id,
           COUNT(IF(current_status='ACTIVE', 1, NULL)) AS active_operator_count,
           COUNT(IF(current_status='ACTIVE' AND role_code='OWNER', 1, NULL)) AS active_owner_count,
           MAX(recorded_at) AS assignment_freshness_at
    FROM yshopping_dim.dim_canonical_merchant_operator_assignment_current
    GROUP BY tenant_id, merchant_id, shop_id
) assignment ON assignment.tenant_id=merchant.tenant_id
            AND assignment.merchant_id=merchant.merchant_id
            AND assignment.shop_id=shop.shop_id;
