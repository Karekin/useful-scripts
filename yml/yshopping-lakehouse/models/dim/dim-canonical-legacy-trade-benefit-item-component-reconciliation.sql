CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_legacy_trade_benefit_item_component_reconciliation AS
WITH item_component_raw AS (
    SELECT tenant_id, migration_run_id, candidate_id, legacy_order_id, legacy_order_no,
           order_assessment_status, is_deleted, 'GENERIC_DISCOUNT' AS component_type,
           generic_discount_amount_minor AS amount_minor
    FROM yshopping_dim.dim_canonical_legacy_trade_benefit_item_assessment
    UNION ALL
    SELECT tenant_id, migration_run_id, candidate_id, legacy_order_id, legacy_order_no,
           order_assessment_status, is_deleted, 'COUPON', coupon_amount_minor
    FROM yshopping_dim.dim_canonical_legacy_trade_benefit_item_assessment
    UNION ALL
    SELECT tenant_id, migration_run_id, candidate_id, legacy_order_id, legacy_order_no,
           order_assessment_status, is_deleted, 'POINT', point_amount_minor
    FROM yshopping_dim.dim_canonical_legacy_trade_benefit_item_assessment
    UNION ALL
    SELECT tenant_id, migration_run_id, candidate_id, legacy_order_id, legacy_order_no,
           order_assessment_status, is_deleted, 'VIP', vip_amount_minor
    FROM yshopping_dim.dim_canonical_legacy_trade_benefit_item_assessment
), eligible_run AS (
    SELECT DISTINCT tenant_id, migration_run_id
    FROM yshopping_dim.dim_canonical_legacy_trade_benefit_item_assessment
), item_rollup AS (
    SELECT tenant_id, migration_run_id, candidate_id, legacy_order_id, MAX(legacy_order_no) AS legacy_order_no,
           MAX(order_assessment_status) AS order_assessment_status, component_type,
           SUM(CASE WHEN amount_minor <> 0 THEN 1 ELSE 0 END)
               AS source_item_component_row_count,
           SUM(amount_minor) AS source_item_component_amount_minor,
           SUM(CASE WHEN is_deleted = FALSE AND amount_minor <> 0 THEN 1 ELSE 0 END)
               AS item_component_row_count,
           SUM(CASE WHEN is_deleted = FALSE THEN amount_minor ELSE 0 END) AS item_component_amount_minor,
           SUM(CASE WHEN is_deleted = TRUE AND amount_minor <> 0 THEN 1 ELSE 0 END)
               AS excluded_item_component_row_count,
           SUM(CASE WHEN is_deleted = TRUE THEN amount_minor ELSE 0 END)
               AS excluded_item_component_amount_minor
    FROM item_component_raw
    GROUP BY tenant_id, migration_run_id, candidate_id, legacy_order_id, component_type
    HAVING source_item_component_row_count > 0 OR source_item_component_amount_minor <> 0
), header_rollup AS (
    SELECT component.tenant_id, component.migration_run_id, component.candidate_id,
           component.legacy_order_id, MAX(component.legacy_order_no) AS legacy_order_no,
           MAX(component.order_assessment_status) AS order_assessment_status, component.component_type,
           COUNT(*) AS header_component_count,
           SUM(component.component_amount_minor) AS header_component_amount_minor
    FROM yshopping_dim.dim_canonical_legacy_trade_benefit_component_assessment component
    JOIN eligible_run
      ON eligible_run.tenant_id = component.tenant_id
     AND eligible_run.migration_run_id = component.migration_run_id
    GROUP BY component.tenant_id, component.migration_run_id, component.candidate_id,
             component.legacy_order_id, component.component_type
), component_keys AS (
    SELECT tenant_id, migration_run_id, candidate_id, legacy_order_id, component_type FROM item_rollup
    UNION
    SELECT tenant_id, migration_run_id, candidate_id, legacy_order_id, component_type FROM header_rollup
), reconciled AS (
  SELECT
    component_keys.tenant_id,
    component_keys.migration_run_id,
    component_keys.candidate_id,
    component_keys.legacy_order_id,
    COALESCE(item.legacy_order_no, header.legacy_order_no) AS legacy_order_no,
    component_keys.component_type,
    COALESCE(item.source_item_component_row_count, 0) AS source_item_component_row_count,
    COALESCE(item.source_item_component_amount_minor, 0) AS source_item_component_amount_minor,
    COALESCE(item.item_component_row_count, 0) AS item_component_row_count,
    COALESCE(item.item_component_amount_minor, 0) AS item_component_amount_minor,
    COALESCE(item.excluded_item_component_row_count, 0) AS excluded_item_component_row_count,
    COALESCE(item.excluded_item_component_amount_minor, 0) AS excluded_item_component_amount_minor,
    COALESCE(header.header_component_count, 0) AS header_component_count,
    COALESCE(header.header_component_amount_minor, 0) AS header_component_amount_minor,
    COALESCE(item.item_component_amount_minor, 0)
        - COALESCE(header.header_component_amount_minor, 0) AS amount_gap_minor,
    COALESCE(item.order_assessment_status, header.order_assessment_status) AS order_assessment_status,
    CASE
      WHEN COALESCE(item.order_assessment_status, header.order_assessment_status) = 'DELETED_EXCLUDED'
        THEN 'EXCLUDED_SOURCE_ORDER_DELETED'
      WHEN COALESCE(item.item_component_row_count, 0) = 0
       AND COALESCE(item.excluded_item_component_row_count, 0) > 0
       AND COALESCE(header.header_component_count, 0) = 0
        THEN 'EXCLUDED_SOURCE_ITEM_DELETED'
      WHEN COALESCE(item.item_component_row_count, 0) = 0 THEN 'MISSING_ITEM_COMPONENT'
      WHEN COALESCE(header.header_component_count, 0) = 0 THEN 'MISSING_HEADER_COMPONENT'
      WHEN item.item_component_amount_minor = header.header_component_amount_minor THEN 'MATCHED'
      ELSE 'AMOUNT_MISMATCH'
    END AS reconciliation_status
  FROM component_keys
  LEFT JOIN item_rollup item
  ON item.tenant_id = component_keys.tenant_id
 AND item.migration_run_id = component_keys.migration_run_id
 AND item.candidate_id = component_keys.candidate_id
 AND item.legacy_order_id = component_keys.legacy_order_id
 AND item.component_type = component_keys.component_type
  LEFT JOIN header_rollup header
  ON header.tenant_id = component_keys.tenant_id
 AND header.migration_run_id = component_keys.migration_run_id
 AND header.candidate_id = component_keys.candidate_id
   AND header.legacy_order_id = component_keys.legacy_order_id
   AND header.component_type = component_keys.component_type
)
SELECT
    SHA2(CONCAT_WS('|', CAST(tenant_id AS STRING), migration_run_id, candidate_id, component_type), 256)
        AS reconciliation_id,
    reconciled.*,
    SHA2(CONCAT_WS('|', candidate_id, component_type,
        CAST(source_item_component_row_count AS STRING),
        CAST(source_item_component_amount_minor AS STRING),
        CAST(item_component_row_count AS STRING), CAST(item_component_amount_minor AS STRING),
        CAST(excluded_item_component_row_count AS STRING),
        CAST(excluded_item_component_amount_minor AS STRING),
        CAST(header_component_count AS STRING), CAST(header_component_amount_minor AS STRING),
        order_assessment_status), 256) AS reconciliation_hash,
    FALSE AS canonical_import_allowed
FROM reconciled;
