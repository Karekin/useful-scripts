CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_return_fulfillment_current AS
SELECT ranked.* EXCEPT(row_num)
FROM (
    SELECT event.*,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, return_fulfillment_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_return_fulfillment_status_event event
) ranked
WHERE row_num = 1;
