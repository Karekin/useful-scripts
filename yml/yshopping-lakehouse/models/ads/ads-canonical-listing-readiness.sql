CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_listing_readiness AS
SELECT
    listing.tenant_id,
    listing.run_id,
    listing.listing_id,
    listing.listing_no,
    listing.aggregate_version AS listing_version,
    listing.revision AS listing_revision,
    listing.current_status AS listing_status,
    listing.listing_event_count,
    COALESCE(review.review_event_count, 0) AS review_event_count,
    COALESCE(review.passed_stage_count, 0) AS passed_stage_count,
    COALESCE(offer.offer_count, 0) AS offer_count,
    COALESCE(offer.enabled_offer_count, 0) AS enabled_offer_count,
    COALESCE(offer.active_catalog_sku_count, 0) AS active_catalog_sku_count,
    COALESCE(offer.active_merchant_shop_offer_count, 0) AS active_merchant_shop_offer_count,
    CASE
        WHEN listing.current_status = 'PUBLISHED'
         AND listing.completion_passed = TRUE
         AND listing.business_approved = TRUE
         AND listing.risk_approved = TRUE
         AND listing.listing_event_count = 6
         AND COALESCE(review.review_event_count, 0) = 3
         AND COALESCE(review.passed_stage_count, 0) = 3
         AND COALESCE(offer.offer_count, 0) > 0
         AND offer.offer_count = offer.enabled_offer_count
         AND offer.offer_count = offer.active_catalog_sku_count
        THEN 'LISTING_PUBLISHED'
        ELSE 'IN_PROGRESS'
    END AS readiness_status,
    CASE
        WHEN listing.current_status = 'PUBLISHED'
         AND listing.completion_passed = TRUE
         AND listing.business_approved = TRUE
         AND listing.risk_approved = TRUE
         AND COALESCE(offer.offer_count, 0) > 0
         AND offer.offer_count = offer.enabled_offer_count
         AND offer.offer_count = offer.active_catalog_sku_count
         AND offer.offer_count = offer.active_merchant_shop_offer_count
        THEN 'LISTING_SELLABLE'
        WHEN listing.current_status = 'PUBLISHED'
         AND COALESCE(offer.offer_count, 0) > 0
         AND offer.offer_count <> COALESCE(offer.active_merchant_shop_offer_count, 0)
        THEN 'SELLING_BLOCKED_MERCHANT_SHOP'
        ELSE 'NOT_SELLABLE'
    END AS sellability_status,
    GREATEST(listing.recorded_at, COALESCE(review.review_freshness_at, listing.recorded_at),
             COALESCE(offer.offer_freshness_at, listing.recorded_at),
             COALESCE(offer.merchant_freshness_at, listing.recorded_at)) AS data_freshness_at
FROM yshopping_dim.dim_canonical_listing_current listing
LEFT JOIN (
    SELECT tenant_id, listing_id, revision,
           COUNT(*) AS review_event_count,
           COUNT(DISTINCT IF(review_decision = 'PASSED', review_stage, NULL)) AS passed_stage_count,
           MAX(recorded_at) AS review_freshness_at
    FROM yshopping_dwd.dwd_canonical_listing_review_event
    GROUP BY tenant_id, listing_id, revision
) review ON review.tenant_id = listing.tenant_id
        AND review.listing_id = listing.listing_id
        AND review.revision = listing.revision
LEFT JOIN (
    SELECT tenant_id, listing_id,
           COUNT(*) AS offer_count,
           COUNT(IF(enabled = TRUE AND currency_code = 'CNY', 1, NULL)) AS enabled_offer_count,
           COUNT(IF(catalog_sku_status = 'ACTIVE', 1, NULL)) AS active_catalog_sku_count,
           COUNT(IF(merchant_shop_active = TRUE, 1, NULL)) AS active_merchant_shop_offer_count,
           MAX(offer_freshness_at) AS offer_freshness_at,
           MAX(merchant_freshness_at) AS merchant_freshness_at
    FROM yshopping_dws.dws_canonical_listing_offer_current
    GROUP BY tenant_id, listing_id
) offer ON offer.tenant_id = listing.tenant_id AND offer.listing_id = listing.listing_id;
