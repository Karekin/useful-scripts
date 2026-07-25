SELECT 'engagement_reaction_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, reaction_id
    FROM yshopping_dwd.dwd_canonical_engagement_reaction_event
    GROUP BY tenant_id, reaction_id
    HAVING COUNT(*) <> 1
) duplicate_reaction;

SELECT 'engagement_reaction_status_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_engagement_reaction_event
WHERE current_status NOT IN ('ACTIVE', 'REMOVED')
   OR reaction_type NOT IN ('LIKE', 'FOLLOW');

SELECT 'app_product_review_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, review_id
    FROM yshopping_dwd.dwd_app_product_review_event
    GROUP BY tenant_id, review_id
    HAVING COUNT(*) <> 1
) duplicate_review;

SELECT 'app_product_review_invalid_score_or_digest' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_app_product_review_event
WHERE product_score NOT BETWEEN 1 AND 5
   OR service_score NOT BETWEEN 1 AND 5
   OR logistics_score NOT BETWEEN 1 AND 5
   OR overall_score NOT BETWEEN 1 AND 5
   OR content_digest_sha256 IS NULL
   OR length(content_digest_sha256) <> 64;
