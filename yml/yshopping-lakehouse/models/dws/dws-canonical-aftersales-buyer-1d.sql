CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_aftersales_buyer_1d AS
WITH case_daily AS (
    SELECT tenant_id, buyer_id, CAST(recorded_at AS DATE) AS business_date,
           COUNT(IF(current_status = 'REQUESTED', 1, NULL)) AS requested_case_count,
           COUNT(IF(current_status = 'APPROVED', 1, NULL)) AS approved_case_count,
           COUNT(IF(current_status = 'COMPLETED', 1, NULL)) AS completed_case_count,
           COUNT(DISTINCT after_sale_id) AS affected_case_count,
           SUM(IF(current_status = 'REQUESTED', quantity, 0)) AS requested_quantity,
           SUM(IF(current_status = 'APPROVED', approved_amount_minor, 0)) AS approved_refund_amount_minor,
           MAX(recorded_at) AS case_freshness_at
    FROM yshopping_dwd.dwd_canonical_after_sale_status_event
    GROUP BY tenant_id, buyer_id, CAST(recorded_at AS DATE)
), refund_daily AS (
    SELECT event.tenant_id, after_sale.buyer_id, CAST(event.recorded_at AS DATE) AS business_date,
           COUNT(IF(event.current_status = 'SUCCEEDED', 1, NULL)) AS succeeded_refund_count,
           SUM(IF(event.current_status = 'SUCCEEDED', event.refunded_amount_minor, 0)) AS refunded_amount_minor,
           MAX(event.recorded_at) AS refund_freshness_at
    FROM yshopping_dwd.dwd_canonical_after_sale_refund_status_event event
    JOIN yshopping_dim.dim_canonical_after_sale_current after_sale
      ON after_sale.tenant_id = event.tenant_id AND after_sale.after_sale_id = event.after_sale_id
    GROUP BY event.tenant_id, after_sale.buyer_id, CAST(event.recorded_at AS DATE)
), return_daily AS (
    SELECT event.tenant_id, after_sale.buyer_id, CAST(event.recorded_at AS DATE) AS business_date,
           COUNT(IF(event.current_status = 'HANDED_OVER', 1, NULL)) AS handed_over_return_count,
           SUM(IF(event.current_status = 'HANDED_OVER', event.return_shipping_amount_minor, 0))
             AS return_shipping_amount_minor,
           MAX(event.recorded_at) AS return_freshness_at
    FROM yshopping_dwd.dwd_canonical_return_fulfillment_status_event event
    JOIN yshopping_dim.dim_canonical_after_sale_current after_sale
      ON after_sale.tenant_id = event.tenant_id AND after_sale.after_sale_id = event.after_sale_id
     AND after_sale.after_sale_item_id = event.after_sale_item_id
    GROUP BY event.tenant_id, after_sale.buyer_id, CAST(event.recorded_at AS DATE)
), buyer_day AS (
    SELECT tenant_id, buyer_id, business_date FROM case_daily
    UNION
    SELECT tenant_id, buyer_id, business_date FROM refund_daily
    UNION
    SELECT tenant_id, buyer_id, business_date FROM return_daily
)
SELECT buyer_day.tenant_id, buyer_day.buyer_id, buyer_day.business_date,
       COALESCE(cases.requested_case_count, 0) AS requested_case_count,
       COALESCE(cases.approved_case_count, 0) AS approved_case_count,
       COALESCE(cases.completed_case_count, 0) AS completed_case_count,
       COALESCE(cases.affected_case_count, 0) AS affected_case_count,
       COALESCE(cases.requested_quantity, 0) AS requested_quantity,
       COALESCE(cases.approved_refund_amount_minor, 0) AS approved_refund_amount_minor,
       COALESCE(refunds.succeeded_refund_count, 0) AS succeeded_refund_count,
       COALESCE(refunds.refunded_amount_minor, 0) AS refunded_amount_minor,
       COALESCE(returns.handed_over_return_count, 0) AS handed_over_return_count,
       COALESCE(returns.return_shipping_amount_minor, 0) AS return_shipping_amount_minor,
       GREATEST(COALESCE(cases.case_freshness_at, buyer_day.business_date),
                COALESCE(refunds.refund_freshness_at, buyer_day.business_date),
                COALESCE(returns.return_freshness_at, buyer_day.business_date)) AS data_freshness_at
FROM buyer_day
LEFT JOIN case_daily cases
  ON cases.tenant_id = buyer_day.tenant_id AND cases.buyer_id = buyer_day.buyer_id
 AND cases.business_date = buyer_day.business_date
LEFT JOIN refund_daily refunds
  ON refunds.tenant_id = buyer_day.tenant_id AND refunds.buyer_id = buyer_day.buyer_id
 AND refunds.business_date = buyer_day.business_date
LEFT JOIN return_daily returns
  ON returns.tenant_id = buyer_day.tenant_id AND returns.buyer_id = buyer_day.buyer_id
 AND returns.business_date = buyer_day.business_date;
