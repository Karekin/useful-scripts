CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_listing_unpublish_saga_current AS
WITH physical_unpublish AS (
    SELECT tenant_id, causation_id AS source_event_id,
           COUNT(*) AS actual_unpublish_event_count,
           COUNT(DISTINCT listing_id) AS actual_unpublished_listing_count,
           MIN(recorded_at) AS first_unpublished_recorded_at,
           MAX(recorded_at) AS last_unpublished_recorded_at
    FROM yshopping_dwd.dwd_canonical_listing_status_event
    WHERE current_status = 'UNPUBLISHED' AND causation_id IS NOT NULL
    GROUP BY tenant_id, causation_id
)
SELECT
    saga.*,
    source.entity_type AS source_event_entity_type,
    source.merchant_id AS source_event_merchant_id,
    source.shop_id AS source_event_shop_id,
    source.current_status AS source_event_status,
    source.aggregate_version AS source_event_aggregate_version,
    source.recorded_at AS source_event_recorded_at,
    COALESCE(physical.actual_unpublish_event_count, 0) AS actual_unpublish_event_count,
    COALESCE(physical.actual_unpublished_listing_count, 0) AS actual_unpublished_listing_count,
    physical.first_unpublished_recorded_at,
    physical.last_unpublished_recorded_at,
    source.event_id IS NOT NULL
      AND source.entity_type = saga.source_entity_type
      AND source.merchant_id = saga.merchant_id
      AND ((saga.source_entity_type = 'MERCHANT' AND saga.shop_id IS NULL
            AND source.current_status = 'SUSPENDED')
        OR (saga.source_entity_type = 'SHOP' AND source.shop_id = saga.shop_id
            AND source.current_status = 'PAUSED'))
      AND source.aggregate_version = saga.source_aggregate_version
      AS source_event_matches,
    GREATEST(
        saga.recorded_at,
        COALESCE(source.recorded_at, saga.recorded_at),
        COALESCE(physical.last_unpublished_recorded_at, saga.recorded_at)
    ) AS data_freshness_at
FROM yshopping_dim.dim_canonical_listing_unpublish_saga_current saga
LEFT JOIN yshopping_dwd.dwd_canonical_merchant_entity_status_event source
  ON source.tenant_id = saga.tenant_id AND source.event_id = saga.source_event_id
LEFT JOIN physical_unpublish physical
  ON physical.tenant_id = saga.tenant_id AND physical.source_event_id = saga.source_event_id
WHERE saga.schema_version = 1;
