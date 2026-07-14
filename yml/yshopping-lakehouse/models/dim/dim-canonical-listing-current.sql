CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_listing_current AS
SELECT
    event_id, tenant_id, listing_id, listing_no, run_id, aggregate_version, revision,
    merchant_id, channel_code, shop_id, canonical_spu_id, previous_status, current_status,
    completion_passed, business_approved, risk_approved, reason, correlation_id,
    occurred_at, recorded_at, listing_event_count
FROM (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id, listing_id) AS listing_event_count,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, listing_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_listing_status_event event
) ranked
WHERE row_num = 1;
