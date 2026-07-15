WITH listing_order_at_placement AS (
  SELECT DISTINCT item.tenant_id,item.order_item_id,item.recorded_at AS placed_recorded_at,
         offer.merchant_id,item.shop_id
  FROM yshopping_dwd.dwd_canonical_order_item_event item
  JOIN yshopping_dwd.dwd_canonical_listing_offer_event offer
    ON offer.tenant_id=item.tenant_id
   AND offer.listing_id=item.listing_id
   AND offer.listing_offer_id=item.listing_offer_id
   AND offer.listing_revision=item.listing_revision
   AND offer.listing_version=item.listing_version
  WHERE item.schema_version IN (2,3) AND item.aggregate_version=1
), merchant_status_at_placement AS (
  SELECT placed.tenant_id,placed.order_item_id,status.current_status,
         ROW_NUMBER() OVER (
           PARTITION BY placed.tenant_id,placed.order_item_id
           ORDER BY status.aggregate_version DESC,status.recorded_at DESC
         ) AS status_rank
  FROM listing_order_at_placement placed
  JOIN yshopping_dwd.dwd_canonical_merchant_entity_status_event status
    ON status.tenant_id=placed.tenant_id AND status.entity_type='MERCHANT'
   AND status.merchant_id=placed.merchant_id AND status.recorded_at<=placed.placed_recorded_at
), shop_status_at_placement AS (
  SELECT placed.tenant_id,placed.order_item_id,status.current_status,
         ROW_NUMBER() OVER (
           PARTITION BY placed.tenant_id,placed.order_item_id
           ORDER BY status.aggregate_version DESC,status.recorded_at DESC
         ) AS status_rank
  FROM listing_order_at_placement placed
  JOIN yshopping_dwd.dwd_canonical_merchant_entity_status_event status
    ON status.tenant_id=placed.tenant_id AND status.entity_type='SHOP'
   AND status.shop_id=placed.shop_id AND status.recorded_at<=placed.placed_recorded_at
), merchant_source_mapping_ranked AS (
  SELECT mapping.*,
         ROW_NUMBER() OVER (
           PARTITION BY tenant_id,mapping_id
           ORDER BY aggregate_version DESC,recorded_at DESC,event_id DESC
         ) AS mapping_version_rank
  FROM yshopping_dwd.dwd_canonical_merchant_source_mapping_event mapping
), merchant_source_mapping_latest AS (
  SELECT *
  FROM merchant_source_mapping_ranked
  WHERE mapping_version_rank=1
), merchant_source_mapping_effective AS (
  SELECT *
  FROM merchant_source_mapping_latest
  WHERE current_status='ACTIVE'
    AND valid_from<=UTC_TIMESTAMP()
    AND (valid_to IS NULL OR valid_to>UTC_TIMESTAMP())
)
SELECT 'canonical_master_event_version_continuity' AS check_name, COUNT(*) AS violations
FROM (
  SELECT event_type, tenant_id, aggregate_type, aggregate_id
  FROM yshopping_dwd.dwd_domain_event
  WHERE event_type IN (
    'identity.source.linked',
    'merchant.onboarding.status_changed',
    'merchant.entity.status_changed',
    'merchant.operator_assignment.changed',
    'merchant.source_mapping.changed',
    'warehouse.entity.status_changed',
    'warehouse.source_mapping.changed',
    'warehouse.operator_assignment.changed'
  )
  GROUP BY event_type, tenant_id, aggregate_type, aggregate_id
  HAVING MIN(aggregate_version)<>1 OR MAX(aggregate_version)<>COUNT(*)
) gap
UNION ALL
SELECT 'canonical_master_event_id_unique', COUNT(*)
FROM (
  SELECT event_id
  FROM yshopping_dwd.dwd_domain_event
  WHERE event_type IN (
    'identity.source.linked',
    'merchant.onboarding.status_changed',
    'merchant.entity.status_changed',
    'merchant.operator_assignment.changed',
    'merchant.source_mapping.changed',
    'warehouse.entity.status_changed',
    'warehouse.source_mapping.changed',
    'warehouse.operator_assignment.changed'
  )
  GROUP BY event_id HAVING COUNT(*)>1
) duplicate_event
UNION ALL
SELECT 'canonical_identity_source_distinct', COUNT(*)
FROM yshopping_dim.dim_canonical_identity_source_current
WHERE principal_id IS NULL OR principal_id='' OR source_id IS NULL OR source_id=''
   OR principal_id=source_id OR source_status<>'ACTIVE'
UNION ALL
SELECT 'canonical_merchant_entity_distinct', COUNT(*)
FROM yshopping_dws.dws_canonical_merchant_shop_current
WHERE merchant_id=shop_id OR merchant_id=legal_entity_id OR shop_id=legal_entity_id
UNION ALL
SELECT 'canonical_merchant_activation_hierarchy', COUNT(*)
FROM yshopping_dws.dws_canonical_merchant_shop_current
WHERE shop_status='ACTIVE' AND merchant_status<>'ACTIVE'
UNION ALL
SELECT 'canonical_merchant_ready_shape', COUNT(*)
FROM yshopping_ads.ads_canonical_merchant_readiness
WHERE readiness_status='MERCHANT_SHOP_READY'
  AND (legal_entity_status<>'VERIFIED' OR merchant_status<>'ACTIVE'
    OR shop_status<>'ACTIVE' OR onboarding_status<>'APPROVED' OR active_owner_count<>1)
UNION ALL
SELECT 'canonical_listing_sellability_requires_active_merchant_shop', COUNT(*)
FROM yshopping_ads.ads_canonical_listing_readiness
WHERE sellability_status='LISTING_SELLABLE'
  AND (offer_count<=0 OR active_merchant_shop_offer_count<>offer_count)
UNION ALL
SELECT 'canonical_listing_blocks_inactive_merchant_shop', COUNT(*)
FROM yshopping_ads.ads_canonical_listing_readiness
WHERE listing_status='PUBLISHED'
  AND active_merchant_shop_offer_count<>offer_count
  AND sellability_status<>'SELLING_BLOCKED_MERCHANT_SHOP'
UNION ALL
SELECT 'canonical_order_placed_after_merchant_inactive', COUNT(*)
FROM merchant_status_at_placement
WHERE status_rank=1 AND current_status<>'ACTIVE'
UNION ALL
SELECT 'canonical_order_placed_after_shop_inactive', COUNT(*)
FROM shop_status_at_placement
WHERE status_rank=1 AND current_status<>'ACTIVE'
UNION ALL
SELECT 'canonical_merchant_pii_isolation', COUNT(*)
FROM yshopping_dwd.dwd_domain_event
WHERE (event_type LIKE 'merchant.%' OR event_type LIKE 'identity.%')
  AND (LOWER(CAST(payload AS STRING)) LIKE '%registration_number%'
    OR LOWER(CAST(payload AS STRING)) LIKE '%license_no%'
    OR LOWER(CAST(payload AS STRING)) LIKE '%contact_mobile%'
    OR LOWER(CAST(payload AS STRING)) LIKE '%bank_account%')
UNION ALL
SELECT 'canonical_merchant_source_distinct', COUNT(*)
FROM merchant_source_mapping_latest
WHERE source_id IS NULL OR source_id='' OR target_id IS NULL OR target_id=''
   OR source_id=target_id
UNION ALL
SELECT 'canonical_merchant_source_normalized', COUNT(*)
FROM merchant_source_mapping_latest
WHERE mapping_source_system<>UPPER(TRIM(mapping_source_system))
   OR source_type<>UPPER(TRIM(source_type))
   OR source_id<>TRIM(source_id)
   OR mapping_source_system='' OR source_type='' OR source_id=''
UNION ALL
SELECT 'canonical_merchant_source_target_shape', COUNT(*)
FROM merchant_source_mapping_latest
WHERE target_type NOT IN ('LEGAL_ENTITY','MERCHANT','SHOP')
   OR target_id IS NULL OR target_id=''
UNION ALL
SELECT 'canonical_merchant_source_target_exists', COUNT(*)
FROM merchant_source_mapping_latest mapping
LEFT JOIN yshopping_dim.dim_canonical_merchant_legal_entity_current legal
  ON legal.tenant_id=mapping.tenant_id AND legal.legal_entity_id=mapping.target_id
LEFT JOIN yshopping_dim.dim_canonical_merchant_current merchant
  ON merchant.tenant_id=mapping.tenant_id AND merchant.merchant_id=mapping.target_id
LEFT JOIN yshopping_dim.dim_canonical_shop_current shop
  ON shop.tenant_id=mapping.tenant_id AND shop.shop_id=mapping.target_id
WHERE (mapping.target_type='LEGAL_ENTITY' AND legal.legal_entity_id IS NULL)
   OR (mapping.target_type='MERCHANT' AND merchant.merchant_id IS NULL)
   OR (mapping.target_type='SHOP' AND shop.shop_id IS NULL)
UNION ALL
SELECT 'canonical_merchant_source_validity', COUNT(*)
FROM merchant_source_mapping_latest
WHERE valid_from IS NULL OR (valid_to IS NOT NULL AND valid_to<=valid_from)
   OR current_status NOT IN ('ACTIVE','REVOKED')
   OR verification_ref IS NULL OR verification_ref=''
   OR migration_run_id IS NULL OR migration_run_id=''
UNION ALL
SELECT 'canonical_merchant_source_active_unique', COUNT(*)
FROM (
  SELECT tenant_id,mapping_source_system,source_type,source_id,COUNT(*) AS mapping_count
  FROM merchant_source_mapping_effective
  GROUP BY tenant_id,mapping_source_system,source_type,source_id
  HAVING COUNT(*)>1
) ambiguous
UNION ALL
SELECT 'canonical_merchant_source_current_fail_closed', COUNT(*)
FROM yshopping_dim.dim_canonical_merchant_source_mapping_current
WHERE current_status<>'ACTIVE' OR active_mapping_count<>1
   OR valid_from>UTC_TIMESTAMP() OR (valid_to IS NOT NULL AND valid_to<=UTC_TIMESTAMP())
   OR verification_ref IS NULL OR verification_ref=''
   OR migration_run_id IS NULL OR migration_run_id=''
UNION ALL
SELECT 'canonical_warehouse_location_hierarchy', COUNT(*)
FROM yshopping_dim.dim_canonical_warehouse_location_current location
LEFT JOIN yshopping_dim.dim_canonical_warehouse_zone_current zone
  ON zone.tenant_id=location.tenant_id AND zone.zone_id=location.zone_id
LEFT JOIN yshopping_dim.dim_canonical_warehouse_current warehouse
  ON warehouse.tenant_id=location.tenant_id AND warehouse.warehouse_id=location.warehouse_id
WHERE zone.zone_id IS NULL OR warehouse.warehouse_id IS NULL
   OR zone.warehouse_id<>location.warehouse_id
UNION ALL
SELECT 'canonical_warehouse_source_id_distinct', COUNT(*)
FROM yshopping_dwd.dwd_canonical_warehouse_source_mapping_event
WHERE canonical_id IS NULL OR canonical_id='' OR source_id IS NULL OR source_id=''
   OR canonical_id=source_id
UNION ALL
SELECT 'canonical_warehouse_ready_shape', COUNT(*)
FROM yshopping_ads.ads_canonical_warehouse_network_readiness
WHERE readiness_status='WAREHOUSE_NETWORK_READY'
  AND (warehouse_status<>'ACTIVE' OR zone_count<=0 OR active_zone_count<>zone_count
    OR location_count<=0 OR active_location_count<>location_count
    OR active_mapping_count<=0 OR active_operator_count<=0);
