CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_inventory_lot_readiness AS
SELECT
    lot.*,
    CASE
      WHEN lot.minimum_lot_version <> 1
        OR lot.lifecycle_event_count <> lot.lot_version
        OR lot.source_identity_conflict_count <> 0
        OR (lot.balance_id IS NOT NULL AND (
             lot.warehouse_id IS NULL OR lot.location_id IS NULL OR lot.base_uom_code IS NULL
          OR lot.on_hand_quantity < 0 OR lot.reserved_quantity < 0 OR lot.in_transit_quantity < 0
          OR lot.reserved_quantity > lot.on_hand_quantity))
        OR (lot.allocation_eligibility <> 'ALLOCATABLE' AND lot.allocatable_quantity <> 0)
      THEN 'INCONSISTENT'
      WHEN lot.source_mapping_count = 0 OR lot.effective_mapping_count = 0 THEN 'SOURCE_UNMAPPED'
      WHEN lot.lot_status = 'RECALLED' THEN 'RECALLED_FENCED'
      WHEN lot.lot_status = 'CLOSED' THEN 'CLOSED_FENCED'
      WHEN lot.allocation_eligibility = 'LOT_EXPIRED' THEN 'EXPIRED_FENCED'
      WHEN lot.balance_id IS NULL THEN 'NO_BALANCE'
      WHEN lot.allocation_eligibility IN ('STOCK_NOT_SELLABLE', 'QUALITY_NOT_QUALIFIED') THEN 'NON_SELLABLE'
      WHEN lot.allocatable_quantity > 0 THEN 'ALLOCATABLE'
      ELSE 'OUT_OF_STOCK'
    END AS readiness_status
FROM yshopping_dws.dws_canonical_inventory_lot_current lot;
