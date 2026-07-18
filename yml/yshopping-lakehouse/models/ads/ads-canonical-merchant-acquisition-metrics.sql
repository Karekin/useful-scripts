CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_merchant_acquisition_metrics AS
SELECT
    tenant_id,
    metric_date,
    merchant_id,
    shop_id,
    channel_code,
    store_visitor_count,
    paid_session_count,
    paid_buyer_count,
    new_buyer_count,
    store_conversion_rate,
    latest_paid_at AS data_freshness_at,
    CASE
        WHEN store_visitor_count > 0 AND paid_buyer_count > 0 THEN 'NONEMPTY_LOCAL_TEST_EVIDENCE'
        WHEN store_visitor_count > 0 THEN 'VISITOR_ONLY'
        ELSE 'ATTRIBUTION_ONLY'
    END AS evidence_status,
    model_semantics
FROM yshopping_dws.dws_canonical_merchant_acquisition_daily;
