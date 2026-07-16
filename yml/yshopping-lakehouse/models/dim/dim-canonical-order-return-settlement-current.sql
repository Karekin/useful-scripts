CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_order_return_settlement_current AS
SELECT event.* EXCEPT(row_num),
       aggregate_version AS settlement_version
FROM (
    SELECT settlement.*,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, order_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_order_after_sale_settlement_event settlement
) event
WHERE row_num = 1;
