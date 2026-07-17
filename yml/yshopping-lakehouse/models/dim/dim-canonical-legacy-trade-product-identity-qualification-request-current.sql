CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_legacy_trade_product_identity_qualification_request_current AS
SELECT latest.* EXCEPT(request_rank)
FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id,request_id) AS request_event_count,
           ROW_NUMBER() OVER (
             PARTITION BY tenant_id,request_id
             ORDER BY request_version DESC,recorded_at DESC,event_id DESC
           ) AS request_rank
    FROM yshopping_dwd.dwd_canonical_legacy_trade_product_identity_qualification_review_event event
) latest
WHERE request_rank=1;
