CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_after_sale_benefit_reversal_current AS
SELECT reversal.* EXCEPT(row_num)
FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id, benefit_reversal_id) AS reversal_event_count,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, benefit_reversal_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_after_sale_benefit_reversal_event event
) reversal
WHERE row_num = 1;
