-- Tenant-level observability rollup for local legacy member, browse, and cart current-state rows.
-- This exposes join coverage only; it is not a sessionized user journey or cart event funnel.
CREATE OR REPLACE VIEW yshopping_dws.dws_legacy_user_behavior_current AS
WITH members AS (
    SELECT
        tenant_id,
        legacy_member_user_id,
        is_deleted,
        source_updated_at
    FROM yshopping_dwd.dwd_legacy_member_user_current
), browse AS (
    SELECT
        browse.tenant_id,
        browse.legacy_browse_history_id,
        browse.legacy_user_id,
        browse.legacy_spu_id,
        browse.source_user_deleted_flag,
        browse.is_deleted,
        browse.update_before_create_flag,
        browse.source_updated_at,
        member.legacy_member_user_id IS NOT NULL AS member_linked_flag,
        CASE WHEN member.legacy_member_user_id IS NOT NULL AND member.is_deleted = TRUE THEN 1 ELSE 0 END
            AS member_deleted_flag
    FROM yshopping_dwd.dwd_legacy_product_browse_history_current browse
    LEFT JOIN members member
      ON member.tenant_id = browse.tenant_id
     AND member.legacy_member_user_id = browse.legacy_user_id
), cart AS (
    SELECT
        cart.tenant_id,
        cart.legacy_cart_id,
        cart.legacy_user_id,
        cart.legacy_spu_id,
        cart.legacy_sku_id,
        cart.cart_quantity,
        cart.selected_flag,
        cart.is_deleted,
        cart.invalid_quantity_flag,
        cart.update_before_create_flag,
        cart.source_updated_at,
        member.legacy_member_user_id IS NOT NULL AS member_linked_flag,
        CASE WHEN member.legacy_member_user_id IS NOT NULL AND member.is_deleted = TRUE THEN 1 ELSE 0 END
            AS member_deleted_flag
    FROM yshopping_dwd.dwd_legacy_trade_cart_current cart
    LEFT JOIN members member
      ON member.tenant_id = cart.tenant_id
     AND member.legacy_member_user_id = cart.legacy_user_id
)
SELECT
    tenant.tenant_id,
    COALESCE(member.member_row_count, 0) AS member_row_count,
    COALESCE(member.active_member_row_count, 0) AS active_member_row_count,
    COALESCE(browse.browse_row_count, 0) AS browse_row_count,
    COALESCE(browse.active_browse_row_count, 0) AS active_browse_row_count,
    COALESCE(browse.distinct_browse_user_count, 0) AS distinct_browse_user_count,
    COALESCE(browse.distinct_browse_spu_count, 0) AS distinct_browse_spu_count,
    COALESCE(browse.member_linked_browse_count, 0) AS member_linked_browse_count,
    COALESCE(browse.member_unresolved_browse_count, 0) AS member_unresolved_browse_count,
    COALESCE(browse.active_member_linked_browse_count, 0) AS active_member_linked_browse_count,
    COALESCE(browse.active_member_unresolved_browse_count, 0) AS active_member_unresolved_browse_count,
    COALESCE(browse.member_deleted_browse_count, 0) AS member_deleted_browse_count,
    COALESCE(browse.source_user_deleted_browse_count, 0) AS source_user_deleted_browse_count,
    COALESCE(browse.update_before_create_browse_count, 0) AS update_before_create_browse_count,
    COALESCE(cart.cart_row_count, 0) AS cart_row_count,
    COALESCE(cart.active_cart_row_count, 0) AS active_cart_row_count,
    COALESCE(cart.selected_cart_row_count, 0) AS selected_cart_row_count,
    COALESCE(cart.member_linked_cart_count, 0) AS member_linked_cart_count,
    COALESCE(cart.member_unresolved_cart_count, 0) AS member_unresolved_cart_count,
    COALESCE(cart.active_member_linked_cart_count, 0) AS active_member_linked_cart_count,
    COALESCE(cart.active_member_unresolved_cart_count, 0) AS active_member_unresolved_cart_count,
    COALESCE(cart.member_deleted_cart_count, 0) AS member_deleted_cart_count,
    COALESCE(cart.invalid_quantity_cart_count, 0) AS invalid_quantity_cart_count,
    COALESCE(cart.update_before_create_cart_count, 0) AS update_before_create_cart_count,
    COALESCE(cart.selected_cart_quantity, 0) AS selected_cart_quantity,
    GREATEST(
        COALESCE(member.data_freshness_at, CAST('1970-01-01 00:00:00' AS DATETIME)),
        COALESCE(browse.data_freshness_at, CAST('1970-01-01 00:00:00' AS DATETIME)),
        COALESCE(cart.data_freshness_at, CAST('1970-01-01 00:00:00' AS DATETIME))
    ) AS data_freshness_at,
    'LEGACY_CURRENT_STATE_OBSERVABILITY' AS model_semantics
FROM (
    SELECT tenant_id FROM yshopping_dwd.dwd_legacy_member_user_current
    UNION DISTINCT
    SELECT tenant_id FROM yshopping_dwd.dwd_legacy_product_browse_history_current
    UNION DISTINCT
    SELECT tenant_id FROM yshopping_dwd.dwd_legacy_trade_cart_current
) tenant
LEFT JOIN (
    SELECT
        tenant_id,
        COUNT(*) AS member_row_count,
        SUM(CASE WHEN is_deleted = FALSE THEN 1 ELSE 0 END) AS active_member_row_count,
        MAX(source_updated_at) AS data_freshness_at
    FROM members
    GROUP BY tenant_id
) member ON member.tenant_id = tenant.tenant_id
LEFT JOIN (
    SELECT
        tenant_id,
        COUNT(*) AS browse_row_count,
        SUM(CASE WHEN is_deleted = FALSE THEN 1 ELSE 0 END) AS active_browse_row_count,
        COUNT(DISTINCT legacy_user_id) AS distinct_browse_user_count,
        COUNT(DISTINCT legacy_spu_id) AS distinct_browse_spu_count,
        SUM(CASE WHEN member_linked_flag THEN 1 ELSE 0 END) AS member_linked_browse_count,
        SUM(CASE WHEN member_linked_flag = FALSE THEN 1 ELSE 0 END) AS member_unresolved_browse_count,
        SUM(CASE WHEN is_deleted = FALSE AND source_user_deleted_flag = FALSE
                  AND member_linked_flag THEN 1 ELSE 0 END) AS active_member_linked_browse_count,
        SUM(CASE WHEN is_deleted = FALSE AND source_user_deleted_flag = FALSE
                  AND member_linked_flag = FALSE THEN 1 ELSE 0 END) AS active_member_unresolved_browse_count,
        SUM(member_deleted_flag) AS member_deleted_browse_count,
        SUM(CASE WHEN source_user_deleted_flag THEN 1 ELSE 0 END) AS source_user_deleted_browse_count,
        SUM(CASE WHEN update_before_create_flag THEN 1 ELSE 0 END) AS update_before_create_browse_count,
        MAX(source_updated_at) AS data_freshness_at
    FROM browse
    GROUP BY tenant_id
) browse ON browse.tenant_id = tenant.tenant_id
LEFT JOIN (
    SELECT
        tenant_id,
        COUNT(*) AS cart_row_count,
        SUM(CASE WHEN is_deleted = FALSE THEN 1 ELSE 0 END) AS active_cart_row_count,
        SUM(CASE WHEN is_deleted = FALSE AND selected_flag THEN 1 ELSE 0 END) AS selected_cart_row_count,
        SUM(CASE WHEN member_linked_flag THEN 1 ELSE 0 END) AS member_linked_cart_count,
        SUM(CASE WHEN member_linked_flag = FALSE THEN 1 ELSE 0 END) AS member_unresolved_cart_count,
        SUM(CASE WHEN is_deleted = FALSE AND member_linked_flag THEN 1 ELSE 0 END)
            AS active_member_linked_cart_count,
        SUM(CASE WHEN is_deleted = FALSE AND member_linked_flag = FALSE THEN 1 ELSE 0 END)
            AS active_member_unresolved_cart_count,
        SUM(member_deleted_flag) AS member_deleted_cart_count,
        SUM(CASE WHEN invalid_quantity_flag THEN 1 ELSE 0 END) AS invalid_quantity_cart_count,
        SUM(CASE WHEN update_before_create_flag THEN 1 ELSE 0 END) AS update_before_create_cart_count,
        SUM(CASE WHEN is_deleted = FALSE AND selected_flag THEN cart_quantity ELSE 0 END)
            AS selected_cart_quantity,
        MAX(source_updated_at) AS data_freshness_at
    FROM cart
    GROUP BY tenant_id
) cart ON cart.tenant_id = tenant.tenant_id;
