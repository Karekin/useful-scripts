CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_merchant_readiness AS
SELECT
    tenant_id, merchant_id, legal_entity_id, shop_id, channel_code, external_shop_id,
    legal_entity_status, merchant_status, shop_status, onboarding_status,
    owner_principal_id, active_operator_count, active_owner_count,
    CASE
        WHEN legal_entity_status='VERIFIED'
         AND merchant_status='ACTIVE'
         AND shop_status='ACTIVE'
         AND onboarding_status='APPROVED'
         AND active_owner_count=1
        THEN 'MERCHANT_SHOP_READY'
        ELSE 'IN_PROGRESS'
    END AS readiness_status,
    data_freshness_at
FROM yshopping_dws.dws_canonical_merchant_shop_current;
