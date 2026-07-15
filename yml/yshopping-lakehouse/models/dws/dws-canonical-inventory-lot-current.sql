CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_inventory_lot_current AS
WITH mapping_summary AS (
    SELECT tenant_id, lot_id,
           COUNT(*) AS source_mapping_count,
           SUM(is_effective) AS effective_mapping_count,
           SUM(CASE WHEN is_effective = 1 AND effective_source_mapping_count <> 1 THEN 1 ELSE 0 END)
             AS source_identity_conflict_count,
           MAX(recorded_at) AS last_mapping_recorded_at
    FROM yshopping_dim.dim_canonical_inventory_lot_source_mapping_current
    GROUP BY tenant_id, lot_id
)
SELECT
    lot.tenant_id,
    lot.lot_id,
    lot.lot_code,
    lot.lot_version,
    lot.owner_type,
    lot.owner_id,
    lot.canonical_sku_id,
    lot.manufactured_on,
    lot.expires_on,
    lot.received_at,
    lot.current_status AS lot_status,
    lot.recall_reference,
    lot.run_id,
    lot.migration_run_id,
    lot.lifecycle_event_count,
    lot.minimum_lot_version,
    COALESCE(mapping.source_mapping_count, 0) AS source_mapping_count,
    COALESCE(mapping.effective_mapping_count, 0) AS effective_mapping_count,
    COALESCE(mapping.source_identity_conflict_count, 0) AS source_identity_conflict_count,
    balance.balance_id,
    balance.warehouse_id,
    balance.location_id,
    balance.stock_status,
    balance.quality_status,
    balance.base_uom_code,
    balance.aggregate_version AS balance_version,
    balance.on_hand_quantity,
    balance.reserved_quantity,
    balance.in_transit_quantity,
    balance.on_hand_quantity - balance.reserved_quantity AS unreserved_quantity,
    CASE
      WHEN lot.current_status = 'RECALLED' THEN 'LOT_RECALLED'
      WHEN lot.current_status = 'CLOSED' THEN 'LOT_CLOSED'
      WHEN lot.expires_on IS NOT NULL AND lot.expires_on < CAST(UTC_TIMESTAMP() AS DATE) THEN 'LOT_EXPIRED'
      WHEN balance.balance_id IS NULL THEN 'NO_BALANCE'
      WHEN balance.stock_status <> 'SELLABLE' THEN 'STOCK_NOT_SELLABLE'
      WHEN balance.quality_status <> 'QUALIFIED' THEN 'QUALITY_NOT_QUALIFIED'
      ELSE 'ALLOCATABLE'
    END AS allocation_eligibility,
    CASE
      WHEN lot.current_status = 'ACTIVE'
       AND (lot.expires_on IS NULL OR lot.expires_on >= CAST(UTC_TIMESTAMP() AS DATE))
       AND balance.stock_status = 'SELLABLE'
       AND balance.quality_status = 'QUALIFIED'
      THEN GREATEST(balance.on_hand_quantity - balance.reserved_quantity, 0)
      ELSE CAST(0 AS DECIMAL(24,6))
    END AS allocatable_quantity,
    GREATEST(lot.recorded_at, COALESCE(mapping.last_mapping_recorded_at, lot.recorded_at),
             COALESCE(balance.last_recorded_at, lot.recorded_at)) AS data_freshness_at
FROM yshopping_dim.dim_canonical_inventory_lot_current lot
LEFT JOIN mapping_summary mapping
  ON mapping.tenant_id = lot.tenant_id AND mapping.lot_id = lot.lot_id
LEFT JOIN yshopping_dws.dws_canonical_inventory_balance_current balance
  ON balance.tenant_id = lot.tenant_id
 AND balance.lot_id = lot.lot_id
 AND balance.schema_version = 3;
