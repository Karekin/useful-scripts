SELECT 'inventory' AS report_source, COUNT(*) AS row_count,
       COUNT(DISTINCT tenant_id) AS tenant_count, MAX(data_freshness_at) AS latest_evidence_at
  FROM yshopping_ads.ads_canonical_inventory_health
UNION ALL
SELECT 'procurement', COUNT(*), COUNT(DISTINCT tenant_id), MAX(updated_at)
  FROM yshopping_ads.ads_purchase_fulfillment
UNION ALL
SELECT 'commerce', COUNT(*), COUNT(DISTINCT tenant_id), MAX(data_freshness_at)
  FROM yshopping_ads.ads_canonical_commerce_v2_readiness
UNION ALL
SELECT 'aftersales', COUNT(*), COUNT(DISTINCT tenant_id), MAX(data_freshness_at)
  FROM yshopping_ads.ads_canonical_after_sale_readiness
UNION ALL
SELECT 'metadata', COUNT(*), COUNT(DISTINCT tenant_id), NULL
  FROM yshopping_ads.ads_canonical_metadata_readiness
UNION ALL
SELECT 'ai_governance', COUNT(*), COUNT(DISTINCT tenant_id), NULL
  FROM yshopping_ads.ads_canonical_ai_intelligence_readiness;
