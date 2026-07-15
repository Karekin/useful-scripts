SELECT 'canonical_listing_unpublish_saga_event_id_unique' AS check_name, COUNT(*) AS violations
FROM (
  SELECT event_id
  FROM yshopping_dwd.dwd_canonical_listing_unpublish_saga_event
  GROUP BY event_id HAVING COUNT(*) > 1
) duplicate_event;

SELECT 'canonical_listing_unpublish_saga_version_continuity', COUNT(*)
FROM (
  SELECT tenant_id, saga_id, COUNT(*) AS event_count,
         MIN(aggregate_version) AS min_version, MAX(aggregate_version) AS max_version
  FROM yshopping_dwd.dwd_canonical_listing_unpublish_saga_event
  GROUP BY tenant_id, saga_id
  HAVING min_version <> 1 OR event_count <> max_version
) broken_history;

SELECT 'canonical_listing_unpublish_saga_payload_identity', COUNT(*)
FROM yshopping_dwd.dwd_canonical_listing_unpublish_saga_event
WHERE saga_id <> payload_saga_id
   OR source_event_id <> causation_id
   OR source_entity_type NOT IN ('MERCHANT', 'SHOP')
   OR (source_entity_type = 'MERCHANT' AND shop_id IS NOT NULL)
   OR (source_entity_type = 'SHOP' AND shop_id IS NULL);

SELECT 'canonical_listing_unpublish_saga_reported_counts', COUNT(*)
FROM yshopping_dim.dim_canonical_listing_unpublish_saga_current
WHERE unpublished_listing_count + skipped_listing_count > expected_listing_count
   OR (current_status = 'COMPLETED'
       AND (unpublished_listing_count + skipped_listing_count <> expected_listing_count
            OR active_step <> 'NONE'));

SELECT 'canonical_listing_unpublish_saga_source_lineage', COUNT(*)
FROM yshopping_dws.dws_canonical_listing_unpublish_saga_current
WHERE source_event_matches <> TRUE;

SELECT 'canonical_listing_unpublish_saga_physical_effects', COUNT(*)
FROM yshopping_dws.dws_canonical_listing_unpublish_saga_current
WHERE actual_unpublish_event_count <> actual_unpublished_listing_count
   OR actual_unpublished_listing_count > unpublished_listing_count
   OR (current_status = 'COMPLETED'
       AND actual_unpublished_listing_count <> unpublished_listing_count);

SELECT 'canonical_listing_unpublish_saga_terminal_readiness', COUNT(*)
FROM yshopping_ads.ads_canonical_listing_unpublish_readiness
WHERE current_status = 'COMPLETED' AND readiness_status <> 'RECONCILED';
