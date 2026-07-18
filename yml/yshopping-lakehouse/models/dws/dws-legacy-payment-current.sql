-- Tenant-level observability rollup for local legacy payment and refund current-state rows.
-- This measures linkability and runtime usefulness only; it is not a production money mart.
CREATE OR REPLACE VIEW yshopping_dws.dws_legacy_payment_current AS
WITH pay_trade_join AS (
    SELECT
        pay.tenant_id,
        pay.legacy_pay_order_id,
        pay.merchant_order_id,
        pay.legacy_user_id,
        pay.payable_amount_minor,
        pay.refunded_amount_minor,
        pay.source_updated_at,
        pay.success_time,
        pay.is_deleted,
        pay.refund_exceeds_payable_flag,
        pay.invalid_expire_window_flag,
        pay.success_before_create_flag,
        pay.missing_business_reference_flag,
        trade.id AS trade_order_id,
        trade.user_id AS trade_user_id,
        trade.pay_price AS trade_pay_amount_minor,
        trade.refund_price AS trade_refund_amount_minor,
        trade.deleted AS trade_is_deleted,
        trade.update_time AS trade_updated_at
    FROM yshopping_dwd.dwd_legacy_pay_order_current pay
    LEFT JOIN yshopping_ods.trade_order trade
      ON trade.tenant_id = pay.tenant_id
     AND CAST(trade.id AS VARCHAR) = pay.merchant_order_id
), pay_order_link AS (
    SELECT
        tenant_id,
        legacy_pay_order_id,
        MAX(CASE WHEN trade_order_id IS NOT NULL THEN 1 ELSE 0 END) AS trade_order_linked_flag,
        SUM(CASE WHEN trade_order_id IS NOT NULL THEN 1 ELSE 0 END) AS trade_order_match_count,
        MAX(CASE WHEN trade_order_id IS NOT NULL AND trade_is_deleted = FALSE THEN 1 ELSE 0 END)
            AS active_trade_order_linked_flag,
        MAX(CASE WHEN trade_order_id IS NOT NULL AND trade_user_id <> legacy_user_id THEN 1 ELSE 0 END)
            AS trade_user_mismatch_flag,
        MAX(CASE WHEN trade_order_id IS NOT NULL
                  AND ABS(COALESCE(trade_pay_amount_minor, 0) - payable_amount_minor) > 0
            THEN 1 ELSE 0 END) AS trade_pay_amount_mismatch_flag,
        MAX(CASE WHEN trade_order_id IS NOT NULL
                  AND ABS(COALESCE(trade_refund_amount_minor, 0) - refunded_amount_minor) > 0
            THEN 1 ELSE 0 END) AS trade_refund_amount_mismatch_flag,
        MAX(source_updated_at) AS pay_order_freshness_at,
        MAX(COALESCE(trade_updated_at, source_updated_at)) AS trade_order_freshness_at
    FROM pay_trade_join
    GROUP BY tenant_id, legacy_pay_order_id
), refund_enriched AS (
    SELECT
        refund.tenant_id,
        refund.legacy_pay_refund_id,
        refund.legacy_pay_order_id,
        refund.legacy_user_id,
        refund.refund_amount_minor,
        refund.pay_amount_minor,
        refund.source_created_at,
        refund.source_updated_at,
        refund.success_time,
        refund.is_deleted,
        refund.refund_exceeds_pay_amount_flag,
        refund.success_before_create_flag,
        refund.provider_reference_without_success_time_flag,
        refund.missing_business_reference_flag,
        pay.legacy_pay_order_id AS linked_pay_order_id,
        pay.legacy_user_id AS pay_order_user_id,
        pay.payable_amount_minor,
        pay.source_created_at AS pay_order_created_at,
        pay.source_updated_at AS pay_order_updated_at,
        trade.id AS trade_order_id,
        CASE
            WHEN refund.success_time IS NOT NULL
             AND refund.success_time >= refund.source_created_at
            THEN TIMESTAMPDIFF(SECOND, refund.source_created_at, refund.success_time) / 3600.0
            ELSE NULL
        END AS refund_cycle_hours
    FROM yshopping_dwd.dwd_legacy_pay_refund_current refund
    LEFT JOIN yshopping_dwd.dwd_legacy_pay_order_current pay
      ON pay.tenant_id = refund.tenant_id
     AND pay.legacy_pay_order_id = refund.legacy_pay_order_id
    LEFT JOIN yshopping_ods.trade_order trade
      ON trade.tenant_id = pay.tenant_id
     AND CAST(trade.id AS VARCHAR) = pay.merchant_order_id
), refund_link AS (
    SELECT
        tenant_id,
        legacy_pay_refund_id,
        MAX(CASE WHEN linked_pay_order_id IS NOT NULL THEN 1 ELSE 0 END) AS pay_order_linked_flag,
        MAX(CASE WHEN trade_order_id IS NOT NULL THEN 1 ELSE 0 END) AS trade_order_linked_flag,
        MAX(CASE WHEN linked_pay_order_id IS NOT NULL AND pay_order_user_id <> legacy_user_id THEN 1 ELSE 0 END)
            AS pay_order_user_mismatch_flag,
        MAX(CASE WHEN linked_pay_order_id IS NOT NULL AND refund_amount_minor > payable_amount_minor THEN 1 ELSE 0 END)
            AS refund_exceeds_linked_pay_order_flag,
        MAX(refund_cycle_hours) AS refund_cycle_hours,
        MAX(source_updated_at) AS refund_freshness_at,
        MAX(COALESCE(pay_order_updated_at, source_updated_at)) AS pay_order_freshness_at
    FROM refund_enriched
    GROUP BY tenant_id, legacy_pay_refund_id
)
SELECT
    pay.tenant_id,
    COUNT(*) AS pay_order_row_count,
    SUM(CASE WHEN pay.is_deleted = FALSE THEN 1 ELSE 0 END) AS active_pay_order_count,
    SUM(CASE WHEN pay.success_time IS NOT NULL AND pay.is_deleted = FALSE THEN 1 ELSE 0 END)
        AS successful_pay_order_count,
    COUNT(DISTINCT CASE WHEN pay.success_time IS NOT NULL AND pay.is_deleted = FALSE
                        THEN pay.legacy_user_id END) AS successful_paid_buyer_count,
    SUM(pay.trade_order_linked_flag) AS trade_order_linked_pay_order_count,
    SUM(pay.active_trade_order_linked_flag) AS active_trade_order_linked_pay_order_count,
    SUM(CASE WHEN pay.trade_order_linked_flag = 0 THEN 1 ELSE 0 END)
        AS trade_order_unlinked_pay_order_count,
    SUM(CASE WHEN pay.trade_order_match_count > 1 THEN 1 ELSE 0 END)
        AS duplicated_trade_order_match_count,
    SUM(pay.trade_user_mismatch_flag) AS pay_trade_user_mismatch_count,
    SUM(pay.trade_pay_amount_mismatch_flag) AS pay_trade_pay_amount_mismatch_count,
    SUM(pay.trade_refund_amount_mismatch_flag) AS pay_trade_refund_amount_mismatch_count,
    SUM(CASE WHEN pay.refund_exceeds_payable_flag THEN 1 ELSE 0 END)
        AS refund_exceeds_payable_pay_order_count,
    SUM(CASE WHEN pay.invalid_expire_window_flag THEN 1 ELSE 0 END)
        AS invalid_expire_window_pay_order_count,
    SUM(CASE WHEN pay.success_before_create_flag THEN 1 ELSE 0 END)
        AS success_before_create_pay_order_count,
    SUM(CASE WHEN pay.missing_business_reference_flag THEN 1 ELSE 0 END)
        AS missing_business_reference_pay_order_count,
    COALESCE(refund.refund_row_count, 0) AS refund_row_count,
    COALESCE(refund.active_refund_row_count, 0) AS active_refund_row_count,
    COALESCE(refund.pay_order_linked_refund_count, 0) AS pay_order_linked_refund_count,
    COALESCE(refund.trade_order_linked_refund_count, 0) AS trade_order_linked_refund_count,
    COALESCE(refund.pay_order_unlinked_refund_count, 0) AS pay_order_unlinked_refund_count,
    COALESCE(refund.pay_order_user_mismatch_refund_count, 0) AS pay_order_user_mismatch_refund_count,
    COALESCE(refund.refund_exceeds_linked_pay_order_count, 0)
        AS refund_exceeds_linked_pay_order_count,
    COALESCE(refund.observable_refund_cycle_count, 0) AS observable_refund_cycle_count,
    COALESCE(refund.average_refund_cycle_hours, 0) AS average_refund_cycle_hours,
    GREATEST(
        MAX(COALESCE(pay.trade_order_freshness_at, pay.pay_order_freshness_at)),
        COALESCE(refund.data_freshness_at, MAX(COALESCE(pay.trade_order_freshness_at, pay.pay_order_freshness_at)))
    ) AS data_freshness_at,
    'LEGACY_CURRENT_STATE_OBSERVABILITY' AS model_semantics
FROM (
    SELECT
        base.tenant_id,
        base.legacy_pay_order_id,
        base.legacy_user_id,
        base.is_deleted,
        base.success_time,
        base.refund_exceeds_payable_flag,
        base.invalid_expire_window_flag,
        base.success_before_create_flag,
        base.missing_business_reference_flag,
        link.trade_order_linked_flag,
        link.active_trade_order_linked_flag,
        link.trade_order_match_count,
        link.trade_user_mismatch_flag,
        link.trade_pay_amount_mismatch_flag,
        link.trade_refund_amount_mismatch_flag,
        link.pay_order_freshness_at,
        link.trade_order_freshness_at
    FROM yshopping_dwd.dwd_legacy_pay_order_current base
    LEFT JOIN pay_order_link link
      ON link.tenant_id = base.tenant_id
     AND link.legacy_pay_order_id = base.legacy_pay_order_id
) pay
LEFT JOIN (
    SELECT
        refund.tenant_id,
        COUNT(*) AS refund_row_count,
        SUM(CASE WHEN base.is_deleted = FALSE THEN 1 ELSE 0 END) AS active_refund_row_count,
        SUM(refund.pay_order_linked_flag) AS pay_order_linked_refund_count,
        SUM(refund.trade_order_linked_flag) AS trade_order_linked_refund_count,
        SUM(CASE WHEN refund.pay_order_linked_flag = 0 THEN 1 ELSE 0 END)
            AS pay_order_unlinked_refund_count,
        SUM(refund.pay_order_user_mismatch_flag) AS pay_order_user_mismatch_refund_count,
        SUM(refund.refund_exceeds_linked_pay_order_flag) AS refund_exceeds_linked_pay_order_count,
        SUM(CASE WHEN refund.refund_cycle_hours IS NOT NULL THEN 1 ELSE 0 END)
            AS observable_refund_cycle_count,
        AVG(refund.refund_cycle_hours) AS average_refund_cycle_hours,
        MAX(GREATEST(refund.refund_freshness_at, refund.pay_order_freshness_at))
            AS data_freshness_at
    FROM refund_link refund
    JOIN yshopping_dwd.dwd_legacy_pay_refund_current base
      ON base.tenant_id = refund.tenant_id
     AND base.legacy_pay_refund_id = refund.legacy_pay_refund_id
    GROUP BY refund.tenant_id
) refund
  ON refund.tenant_id = pay.tenant_id
GROUP BY pay.tenant_id,
         refund.refund_row_count,
         refund.active_refund_row_count,
         refund.pay_order_linked_refund_count,
         refund.trade_order_linked_refund_count,
         refund.pay_order_unlinked_refund_count,
         refund.pay_order_user_mismatch_refund_count,
         refund.refund_exceeds_linked_pay_order_count,
         refund.observable_refund_cycle_count,
         refund.average_refund_cycle_hours,
         refund.data_freshness_at;
