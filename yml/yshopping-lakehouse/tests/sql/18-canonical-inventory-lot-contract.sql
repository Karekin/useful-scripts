SELECT 'canonical_inventory_lot_event_id_unique' AS check_name, COUNT(*) AS violations
FROM (
  SELECT event_id
  FROM yshopping_dwd.dwd_canonical_inventory_lot_lifecycle_event
  GROUP BY event_id HAVING COUNT(*) > 1
) duplicate_event;

SELECT 'canonical_inventory_lot_version_continuity', COUNT(*)
FROM (
  SELECT tenant_id, lot_id, COUNT(*) event_count, MIN(lot_version) min_version, MAX(lot_version) max_version
  FROM yshopping_dwd.dwd_canonical_inventory_lot_lifecycle_event
  GROUP BY tenant_id, lot_id
  HAVING min_version <> 1 OR event_count <> max_version
) broken_history;

SELECT 'canonical_inventory_lot_payload_identity', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_lot_lifecycle_event
WHERE lot_id <> payload_lot_id
   OR owner_type <> 'MERCHANT'
   OR owner_id IS NULL OR canonical_sku_id IS NULL
   OR lot_code IS NULL OR lot_code = '' OR lot_code IN ('NO_LOT', 'DEFAULT', 'UNKNOWN');

SELECT 'canonical_inventory_lot_lifecycle_transition', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_lot_lifecycle_event
WHERE (lot_version = 1 AND (previous_status IS NOT NULL OR current_status <> 'ACTIVE' OR change_type <> 'CREATED'))
   OR (lot_version > 1 AND (previous_status <> 'ACTIVE'
       OR current_status NOT IN ('RECALLED', 'CLOSED') OR change_type <> current_status))
   OR (current_status = 'RECALLED' AND recall_reference IS NULL)
   OR (expires_on IS NOT NULL AND manufactured_on IS NOT NULL AND expires_on < manufactured_on);

SELECT 'canonical_inventory_lot_mapping_event_id_unique', COUNT(*)
FROM (
  SELECT event_id
  FROM yshopping_dwd.dwd_canonical_inventory_lot_source_mapping_event
  GROUP BY event_id HAVING COUNT(*) > 1
) duplicate_event;

SELECT 'canonical_inventory_lot_mapping_version_continuity', COUNT(*)
FROM (
  SELECT tenant_id, mapping_id, COUNT(*) event_count,
         MIN(mapping_version) min_version, MAX(mapping_version) max_version
  FROM yshopping_dwd.dwd_canonical_inventory_lot_source_mapping_event
  GROUP BY tenant_id, mapping_id
  HAVING min_version <> 1 OR event_count <> max_version
) broken_history;

SELECT 'canonical_inventory_lot_mapping_payload_identity', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_lot_source_mapping_event
WHERE mapping_id <> payload_mapping_id
   OR mapping_id = source_id
   OR lot_id IS NULL OR mapping_source_system IS NULL OR source_type IS NULL OR source_id IS NULL
   OR verification_ref IS NULL;

SELECT 'canonical_inventory_lot_mapping_interval_state', COUNT(*)
FROM yshopping_dim.dim_canonical_inventory_lot_source_mapping_current
WHERE valid_from IS NULL OR (valid_to IS NOT NULL AND valid_to <= valid_from)
   OR (current_status = 'ACTIVE' AND valid_to IS NOT NULL)
   OR (current_status = 'ENDED' AND valid_to IS NULL)
   OR mapping_event_count <> mapping_version OR minimum_mapping_version <> 1;

SELECT 'canonical_inventory_lot_mapping_interval_overlap', COUNT(*)
FROM yshopping_dim.dim_canonical_inventory_lot_source_mapping_current a
JOIN yshopping_dim.dim_canonical_inventory_lot_source_mapping_current b
  ON b.tenant_id = a.tenant_id
 AND b.mapping_source_system = a.mapping_source_system
 AND b.source_type = a.source_type
 AND b.source_id = a.source_id
 AND b.mapping_id > a.mapping_id
 AND a.valid_from < COALESCE(b.valid_to, CAST('9999-12-31 23:59:59' AS DATETIME))
 AND b.valid_from < COALESCE(a.valid_to, CAST('9999-12-31 23:59:59' AS DATETIME));

SELECT 'canonical_inventory_lot_mapping_target_exists', COUNT(*)
FROM yshopping_dim.dim_canonical_inventory_lot_source_mapping_current mapping
LEFT JOIN yshopping_dim.dim_canonical_inventory_lot_current lot
  ON lot.tenant_id = mapping.tenant_id AND lot.lot_id = mapping.lot_id
WHERE lot.lot_id IS NULL;

SELECT 'canonical_inventory_lot_stock_identity', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_movement movement
LEFT JOIN yshopping_dim.dim_canonical_inventory_lot_current lot
  ON lot.tenant_id = movement.tenant_id AND lot.lot_id = movement.lot_id
WHERE movement.schema_version = 3 AND movement.lot_id IS NOT NULL
  AND (lot.lot_id IS NULL OR movement.lot_code <> lot.lot_code
    OR movement.owner_type <> lot.owner_type OR movement.owner_id <> lot.owner_id
    OR movement.canonical_sku_id <> lot.canonical_sku_id);

SELECT 'canonical_inventory_lot_allocation_fence', COUNT(*)
FROM yshopping_dws.dws_canonical_inventory_lot_current
WHERE (lot_status IN ('RECALLED', 'CLOSED') OR allocation_eligibility = 'LOT_EXPIRED')
  AND allocatable_quantity <> 0;

SELECT 'canonical_inventory_lot_readiness_consistency', COUNT(*)
FROM yshopping_ads.ads_canonical_inventory_lot_readiness
WHERE readiness_status = 'INCONSISTENT';

SELECT 'canonical_inventory_lot_pii_isolation', COUNT(*)
FROM yshopping_dwd.dwd_domain_event
WHERE event_type IN ('inventory.lot.lifecycle.changed', 'inventory.lot.source_mapping.changed')
  AND (get_json_string(payload, '$.contact_mobile') IS NOT NULL
    OR get_json_string(payload, '$.contact_name') IS NOT NULL
    OR get_json_string(payload, '$.id_card') IS NOT NULL
    OR get_json_string(payload, '$.address') IS NOT NULL);
