-- Governed, aggregate-only KPI surface for the role-based commerce dashboard.
-- This view deliberately keeps missing business semantics out of the result set:
-- consumers must treat an absent metric as unavailable, never as zero.
-- Legacy pay/refund/member/browse/cart current-state observability stays isolated in
-- ads_legacy_commerce_source_metrics until governed identity and historical semantics exist.
CREATE OR REPLACE VIEW yshopping_ads.ads_ecommerce_role_metrics AS
WITH tenants AS (
    SELECT tenant_id FROM yshopping_dim.dim_canonical_order_current
    UNION DISTINCT
    SELECT tenant_id FROM yshopping_dws.dws_canonical_listing_offer_current
    UNION DISTINCT
    SELECT tenant_id FROM yshopping_ads.ads_canonical_inventory_health
    UNION DISTINCT
    SELECT tenant_id FROM yshopping_ads.ads_canonical_coupon_readiness
    UNION DISTINCT
    SELECT tenant_id FROM yshopping_ads.ads_canonical_commerce_acquisition_funnel
    UNION DISTINCT
    SELECT tenant_id FROM yshopping_ads.ads_canonical_risk_commerce_metrics
    UNION DISTINCT
    SELECT tenant_id FROM yshopping_ads.ads_canonical_merchant_acquisition_metrics
    UNION DISTINCT
    SELECT tenant_id FROM yshopping_ads.ads_canonical_merchant_sales_metrics
    UNION DISTINCT
    SELECT tenant_id FROM yshopping_ads.ads_canonical_marketing_campaign_performance
), paid_orders AS (
    SELECT
        orders.tenant_id,
        orders.order_id,
        orders.buyer_id,
        payment.payment_id,
        payment.captured_amount_minor,
        payment.refunded_amount_minor,
        payment.recorded_at
    FROM yshopping_dim.dim_canonical_order_current orders
    JOIN yshopping_dim.dim_canonical_payment_current payment
      ON payment.tenant_id = orders.tenant_id
     AND payment.payment_id = orders.payment_id
    WHERE payment.current_status IN ('CAPTURED', 'PARTIALLY_REFUNDED', 'REFUNDED')
      AND payment.captured_amount_minor > 0
), commerce AS (
    SELECT
        tenant_id,
        COUNT(DISTINCT order_id) AS paid_order_count,
        COUNT(DISTINCT buyer_id) AS paid_buyer_count,
        SUM(captured_amount_minor) AS captured_amount_minor,
        SUM(refunded_amount_minor) AS refunded_amount_minor,
        MAX(recorded_at) AS data_freshness_at
    FROM paid_orders
    GROUP BY tenant_id
), commerce_readiness AS (
    SELECT
        tenant_id,
        COUNT(*) AS order_count,
        SUM(CASE WHEN readiness_status = 'RECONCILED' THEN 1 ELSE 0 END) AS reconciled_order_count,
        MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_ads.ads_canonical_commerce_v2_readiness
    GROUP BY tenant_id
), buyer_window AS (
    SELECT tenant_id, MAX(recorded_at) AS window_end_at
    FROM paid_orders
    GROUP BY tenant_id
), buyer_90d AS (
    SELECT
        orders.tenant_id,
        orders.buyer_id,
        COUNT(DISTINCT orders.order_id) AS paid_order_count
    FROM paid_orders orders
    JOIN buyer_window window
      ON window.tenant_id = orders.tenant_id
    WHERE orders.recorded_at >= DATE_SUB(window.window_end_at, INTERVAL 90 DAY)
    GROUP BY orders.tenant_id, orders.buyer_id
), buyer_90d_rollup AS (
    SELECT
        tenant_id,
        COUNT(*) AS active_buyer_count,
        SUM(paid_order_count) AS paid_order_count,
        SUM(CASE WHEN paid_order_count >= 2 THEN 1 ELSE 0 END) AS repeat_buyer_count
    FROM buyer_90d
    GROUP BY tenant_id
), buyer_category_90d AS (
    SELECT
        orders.tenant_id,
        orders.buyer_id,
        COUNT(DISTINCT catalog.sales_category_ref) AS category_count
    FROM paid_orders orders
    JOIN buyer_window window
      ON window.tenant_id = orders.tenant_id
    JOIN yshopping_dws.dws_canonical_order_item_current item
      ON item.tenant_id = orders.tenant_id
     AND item.order_id = orders.order_id
    LEFT JOIN yshopping_dim.dim_canonical_catalog_sku_current catalog
      ON catalog.tenant_id = item.tenant_id
     AND catalog.canonical_sku_id = item.canonical_sku_id
    WHERE orders.recorded_at >= DATE_SUB(window.window_end_at, INTERVAL 90 DAY)
    GROUP BY orders.tenant_id, orders.buyer_id
), buyer_category_rollup AS (
    SELECT
        tenant_id,
        SUM(category_count) AS category_count,
        COUNT(*) AS buyer_count
    FROM buyer_category_90d
    WHERE category_count > 0
    GROUP BY tenant_id
), payments AS (
    SELECT
        tenant_id,
        COUNT(DISTINCT payment_id) AS payment_attempt_count,
        COUNT(DISTINCT CASE
            WHEN current_status IN ('CAPTURED', 'PARTIALLY_REFUNDED', 'REFUNDED')
            THEN payment_id END) AS successful_payment_count,
        MAX(recorded_at) AS data_freshness_at
    FROM yshopping_dim.dim_canonical_payment_current
    GROUP BY tenant_id
), merchant_supply AS (
    SELECT
        tenant_id,
        COUNT(DISTINCT merchant_id) AS candidate_merchant_count,
        COUNT(DISTINCT CASE
            WHEN enabled = TRUE
             AND listing_status = 'PUBLISHED'
             AND catalog_sku_status = 'ACTIVE'
             AND merchant_shop_active = TRUE
            THEN merchant_id END) AS active_merchant_count,
        COUNT(DISTINCT CASE
            WHEN enabled = TRUE
             AND listing_status = 'PUBLISHED'
             AND catalog_sku_status = 'ACTIVE'
             AND merchant_shop_active = TRUE
            THEN listing_offer_id END) AS active_offer_count,
        MAX(GREATEST(offer_freshness_at, listing_freshness_at,
                     catalog_freshness_at, merchant_freshness_at)) AS data_freshness_at
    FROM yshopping_dws.dws_canonical_listing_offer_current
    GROUP BY tenant_id
), listing_review AS (
    SELECT
        tenant_id,
        COUNT(DISTINCT CASE WHEN review_event_count > 0 THEN listing_id END) AS reviewed_listing_count,
        COUNT(DISTINCT CASE
            WHEN review_event_count > 0 AND passed_stage_count = 3
            THEN listing_id END) AS approved_listing_count,
        MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_ads.ads_canonical_listing_readiness
    GROUP BY tenant_id
), catalog AS (
    SELECT
        tenant_id,
        COUNT(DISTINCT CASE WHEN catalog_status = 'ACTIVE' THEN canonical_sku_id END) AS active_sku_count,
        COUNT(*) AS source_row_count,
        MAX(recorded_at) AS data_freshness_at
    FROM yshopping_dim.dim_canonical_catalog_sku_current
    GROUP BY tenant_id
), inventory_by_sku AS (
    SELECT
        tenant_id,
        canonical_sku_id,
        SUM(CASE WHEN health_status NOT IN ('INVALID', 'NON_SELLABLE')
                 THEN available_quantity ELSE 0 END) AS available_quantity,
        MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_ads.ads_canonical_inventory_health
    GROUP BY tenant_id, canonical_sku_id
), sellable_supply AS (
    SELECT
        offer.tenant_id,
        COUNT(DISTINCT offer.listing_offer_id) AS sellable_offer_count,
        COUNT(DISTINCT CASE WHEN inventory.canonical_sku_id IS NOT NULL
                            THEN offer.listing_offer_id END) AS observable_offer_count,
        COUNT(DISTINCT CASE WHEN inventory.canonical_sku_id IS NOT NULL
                             AND inventory.available_quantity > 0
                            THEN offer.listing_offer_id END) AS in_stock_offer_count,
        COUNT(DISTINCT CASE WHEN inventory.canonical_sku_id IS NOT NULL
                             AND inventory.available_quantity = 0
                            THEN offer.listing_offer_id END) AS out_of_stock_offer_count,
        COUNT(DISTINCT CASE WHEN inventory.canonical_sku_id IS NOT NULL
                             AND inventory.available_quantity > 0
                            THEN CONCAT(offer.canonical_sku_id, '|',
                                        COALESCE(catalog.sales_category_ref, '<UNMAPPED>')) END)
            AS selection_breadth,
        MAX(GREATEST(offer.offer_freshness_at,
                     COALESCE(inventory.data_freshness_at, offer.offer_freshness_at)))
            AS data_freshness_at
    FROM yshopping_dws.dws_canonical_listing_offer_current offer
    LEFT JOIN inventory_by_sku inventory
      ON inventory.tenant_id = offer.tenant_id
     AND inventory.canonical_sku_id = offer.canonical_sku_id
    LEFT JOIN yshopping_dim.dim_canonical_catalog_sku_current catalog
      ON catalog.tenant_id = offer.tenant_id
     AND catalog.canonical_sku_id = offer.canonical_sku_id
    WHERE offer.enabled = TRUE
      AND offer.listing_status = 'PUBLISHED'
      AND offer.catalog_sku_status = 'ACTIVE'
      AND offer.merchant_shop_active = TRUE
    GROUP BY offer.tenant_id
), inventory AS (
    SELECT
        tenant_id,
        COUNT(*) AS balance_count,
        SUM(CASE WHEN dimension_resolution_status = 'CANONICAL_V3' THEN 1 ELSE 0 END)
            AS canonical_v3_balance_count,
        SUM(CASE WHEN health_status = 'LOW_STOCK' THEN 1 ELSE 0 END) AS low_stock_balance_count,
        SUM(CASE WHEN health_status = 'OUT_OF_STOCK' THEN 1 ELSE 0 END) AS out_of_stock_balance_count,
        SUM(CASE WHEN health_status NOT IN ('INVALID', 'NON_SELLABLE')
                 THEN available_quantity ELSE 0 END) AS available_quantity,
        MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_ads.ads_canonical_inventory_health
    GROUP BY tenant_id
), coupons AS (
    SELECT
        tenant_id,
        entitlement_count AS claimed_coupon_count,
        used_count AS used_coupon_count,
        data_freshness_at
    FROM yshopping_ads.ads_canonical_coupon_readiness
), benefit_funding AS (
    SELECT
        tenant_id,
        COUNT(*) AS funding_row_count,
        SUM(amount_minor) AS funding_amount_minor,
        MAX(recorded_at) AS data_freshness_at
    FROM yshopping_dwd.dwd_canonical_order_benefit_funding_event
    GROUP BY tenant_id
), aftersales AS (
    SELECT
        tenant_id,
        COUNT(DISTINCT after_sale_id) AS case_count,
        MAX(recorded_at) AS data_freshness_at
    FROM yshopping_dim.dim_canonical_after_sale_current
    GROUP BY tenant_id
), aftersales_readiness AS (
    SELECT
        tenant_id,
        COUNT(*) AS case_count,
        SUM(CASE WHEN readiness_status = 'RECONCILED' THEN 1 ELSE 0 END) AS reconciled_case_count,
        SUM(CASE WHEN recovery_status IN ('REQUIRED', 'PENDING') THEN 1 ELSE 0 END)
            AS recovery_required_count,
        MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_ads.ads_canonical_after_sale_readiness
    GROUP BY tenant_id
), refunds AS (
    SELECT
        tenant_id,
        COUNT(DISTINCT CASE WHEN current_status = 'SUCCEEDED' THEN refund_id END) AS refund_count,
        SUM(CASE WHEN current_status = 'SUCCEEDED' THEN refunded_amount_minor ELSE 0 END)
            AS refunded_amount_minor,
        MAX(recorded_at) AS data_freshness_at
    FROM yshopping_dim.dim_canonical_after_sale_refund_current
    GROUP BY tenant_id
), refund_cycle_ranked AS (
    SELECT
        tenant_id,
        refund_id,
        refund_cycle_hours,
        data_freshness_at,
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id
            ORDER BY refund_cycle_hours, refund_id
        ) AS refund_rank,
        COUNT(*) OVER (PARTITION BY tenant_id) AS refund_count
    FROM yshopping_dws.dws_canonical_after_sale_refund_cycle
), refund_cycle_p50 AS (
    SELECT
        tenant_id,
        CAST(AVG(refund_cycle_hours) AS DECIMAL(38,6)) AS refund_cycle_hours_p50,
        MAX(refund_count) AS refund_count,
        MAX(data_freshness_at) AS data_freshness_at
    FROM refund_cycle_ranked
    WHERE refund_rank IN (
        FLOOR((refund_count + 1) / 2),
        FLOOR((refund_count + 2) / 2)
    )
    GROUP BY tenant_id
), fulfilled_items AS (
    SELECT
        tenant_id,
        COUNT(DISTINCT order_item_id) AS fulfilled_order_item_count,
        MAX(item_freshness_at) AS data_freshness_at
    FROM yshopping_dws.dws_canonical_order_item_current
    WHERE order_status IN ('COMPLETED', 'RETURNED')
    GROUP BY tenant_id
), returned_items AS (
    SELECT
        aftersale.tenant_id,
        COUNT(DISTINCT aftersale.order_item_id) AS returned_order_item_count
    FROM yshopping_dim.dim_canonical_after_sale_current aftersale
    JOIN yshopping_dws.dws_canonical_order_item_current item
      ON item.tenant_id = aftersale.tenant_id
     AND item.order_item_id = aftersale.order_item_id
    WHERE item.order_status IN ('COMPLETED', 'RETURNED')
    GROUP BY aftersale.tenant_id
), procurement AS (
    SELECT
        tenant_id,
        COUNT(*) AS purchase_order_count,
        SUM(CASE WHEN fulfillment_status IN ('OPEN', 'PARTIAL') THEN 1 ELSE 0 END) AS open_order_count,
        SUM(ordered_quantity) AS ordered_quantity,
        SUM(received_quantity) AS received_quantity,
        MAX(updated_at) AS data_freshness_at
    FROM yshopping_ads.ads_purchase_fulfillment
    GROUP BY tenant_id
), inventory_sell_through AS (
    SELECT
        tenant_id,
        COUNT(*) AS inventory_group_count,
        SUM(net_sold_quantity_30d) AS net_sold_quantity_30d,
        SUM(denominator_quantity_30d) AS denominator_quantity_30d,
        MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_dws.dws_canonical_inventory_sell_through_30d
    GROUP BY tenant_id
), service_first_response_ranked AS (
    SELECT
        tenant_id,
        ticket_id,
        first_response_minutes,
        data_freshness_at,
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id
            ORDER BY first_response_minutes, ticket_id
        ) AS response_rank,
        COUNT(*) OVER (PARTITION BY tenant_id) AS response_ticket_count
    FROM yshopping_dws.dws_canonical_customer_service_ticket_current
    WHERE first_response_minutes IS NOT NULL
), service_first_response_p50 AS (
    SELECT
        tenant_id,
        CAST(AVG(first_response_minutes) AS DECIMAL(38,6)) AS first_response_minutes_p50,
        MAX(response_ticket_count) AS response_ticket_count,
        MAX(data_freshness_at) AS data_freshness_at
    FROM service_first_response_ranked
    WHERE response_rank IN (
        FLOOR((response_ticket_count + 1) / 2),
        FLOOR((response_ticket_count + 2) / 2)
    )
    GROUP BY tenant_id
), behavior_subject_base AS (
    SELECT
        tenant_id,
        session_id,
        COALESCE(NULLIF(current_principal_id, ''), session_id) AS subject_key,
        current_principal_id,
        started_at,
        last_activity_at,
        pdp_viewed_session_flag,
        cart_added_session_flag,
        checkout_session_flag,
        paid_session_flag,
        paid_shop_id
    FROM yshopping_dws.dws_canonical_commerce_session_funnel
), behavior_paid_subject AS (
    SELECT tenant_id, subject_key
    FROM behavior_subject_base
    WHERE paid_session_flag = 1
    GROUP BY tenant_id, subject_key
), behavior_cart_subject AS (
    SELECT tenant_id, subject_key
    FROM behavior_subject_base
    WHERE cart_added_session_flag = 1
    GROUP BY tenant_id, subject_key
), behavior_session AS (
    SELECT
        base.tenant_id,
        COUNT(*) AS session_count,
        COUNT(DISTINCT base.subject_key) AS visitor_count,
        COUNT(DISTINCT CASE WHEN base.pdp_viewed_session_flag = 1
              THEN base.subject_key END) AS pdp_visitor_count,
        COUNT(DISTINCT CASE WHEN base.cart_added_session_flag = 1
              THEN base.subject_key END) AS cart_visitor_count,
        COUNT(DISTINCT CASE WHEN base.checkout_session_flag = 1
              THEN base.subject_key END) AS checkout_visitor_count,
        COUNT(DISTINCT CASE WHEN base.paid_session_flag = 1
              THEN base.subject_key END) AS paid_visitor_count,
        COUNT(DISTINCT CASE WHEN base.paid_session_flag = 1 AND base.paid_shop_id IS NOT NULL
              THEN CONCAT(base.paid_shop_id, '|', base.subject_key) END) AS paid_shop_subject_count,
        COUNT(DISTINCT CASE WHEN cart.subject_key IS NOT NULL AND paid.subject_key IS NULL
              THEN base.subject_key END) AS unpaid_cart_subject_count,
        MAX(base.last_activity_at) AS data_freshness_at
    FROM behavior_subject_base base
    LEFT JOIN behavior_cart_subject cart
      ON cart.tenant_id = base.tenant_id
     AND cart.subject_key = base.subject_key
    LEFT JOIN behavior_paid_subject paid
      ON paid.tenant_id = cart.tenant_id
     AND paid.subject_key = cart.subject_key
    GROUP BY base.tenant_id
), buyer_first_paid AS (
    SELECT
        principal.tenant_id,
        principal.current_principal_id AS principal_id,
        MIN(principal.started_at) AS first_visit_at,
        MIN(principal.first_paid_at) AS first_paid_at
    FROM (
        SELECT
            tenant_id,
            current_principal_id,
            started_at,
            first_paid_at
        FROM yshopping_dws.dws_canonical_commerce_session_funnel
        WHERE current_principal_id IS NOT NULL
          AND paid_session_flag = 1
    ) principal
    GROUP BY principal.tenant_id, principal.current_principal_id
), buyer_first_paid_ranked AS (
    SELECT
        tenant_id,
        principal_id,
        TIMESTAMPDIFF(SECOND, first_visit_at, first_paid_at) / 3600.0 AS first_order_hours,
        first_paid_at,
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id
            ORDER BY TIMESTAMPDIFF(SECOND, first_visit_at, first_paid_at), principal_id
        ) AS order_rank,
        COUNT(*) OVER (PARTITION BY tenant_id) AS buyer_count
    FROM buyer_first_paid
    WHERE first_visit_at IS NOT NULL
      AND first_paid_at IS NOT NULL
      AND first_paid_at >= first_visit_at
), buyer_first_paid_p50 AS (
    SELECT
        tenant_id,
        CAST(AVG(first_order_hours) AS DECIMAL(38,6)) AS first_order_hours_p50,
        MAX(buyer_count) AS buyer_count,
        MAX(first_paid_at) AS data_freshness_at
    FROM buyer_first_paid_ranked
    WHERE order_rank IN (
        FLOOR((buyer_count + 1) / 2),
        FLOOR((buyer_count + 2) / 2)
    )
    GROUP BY tenant_id
), behavior_event AS (
    SELECT
        tenant_id,
        COUNT(*) AS behavior_event_count,
        SUM(CASE WHEN behavior_type = 'PDP_VIEWED' THEN 1 ELSE 0 END) AS pdp_view_count,
        MAX(recorded_at) AS data_freshness_at
    FROM yshopping_dwd.dwd_canonical_commerce_behavior_event
    GROUP BY tenant_id
), search_funnel AS (
    SELECT
        tenant_id,
        COUNT(*) AS search_request_count,
        SUM(CASE
            WHEN search_result_exposed_flag = 1
             AND (search_result_clicked_flag = 1 OR pdp_viewed_flag = 1
                  OR cart_added_flag = 1 OR checkout_started_flag = 1)
            THEN 1 ELSE 0 END) AS successful_search_count,
        MAX(COALESCE(first_checkout_abandoned_at, first_checkout_started_at, first_cart_added_at,
                     first_pdp_viewed_at, first_result_clicked_at, first_result_exposed_at, requested_at))
            AS data_freshness_at
    FROM yshopping_dws.dws_canonical_commerce_search_request_funnel
    GROUP BY tenant_id
), merchant_acquisition AS (
    SELECT
        tenant_id,
        SUM(store_visitor_count) AS visited_store_subject_count,
        SUM(paid_buyer_count) AS paid_store_subject_count,
        SUM(new_buyer_count) AS new_buyer_count,
        COUNT(*) AS merchant_day_row_count,
        MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_ads.ads_canonical_merchant_acquisition_metrics
    GROUP BY tenant_id
), merchant_cancellations AS (
    SELECT
        tenant_id,
        metric_value,
        numerator,
        denominator,
        unit,
        source_row_count,
        evidence_note,
        data_freshness_at
    FROM yshopping_ads.ads_canonical_merchant_cancellation_metrics
), merchant_net_sales AS (
    SELECT
        tenant_id,
        SUM(numerator) AS merchant_net_sales_amount_minor,
        SUM(source_row_count) AS profitability_item_count,
        MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_ads.ads_canonical_merchant_sales_metrics
    GROUP BY tenant_id
), marketing AS (
    SELECT
        tenant_id,
        SUM(attribution_amount_minor) AS attribution_amount_minor,
        SUM(ad_spend_amount_minor) AS ad_spend_amount_minor,
        SUM(COALESCE(incremental_contribution_profit_minor, 0)) AS incremental_contribution_profit_minor,
        SUM(COALESCE(promotion_cost_minor, 0)) AS promotion_cost_minor,
        COUNT(*) AS campaign_row_count,
        MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_ads.ads_canonical_marketing_campaign_performance
    GROUP BY tenant_id
), metric_rows AS (
    SELECT tenant.tenant_id, 'commerce.order_count' AS metric_id,
           CAST(commerce.paid_order_count AS DECIMAL(38,6)) AS metric_value,
           CAST(commerce.paid_order_count AS DECIMAL(38,6)) AS numerator,
           CAST(NULL AS DECIMAL(38,6)) AS denominator, 'count' AS unit,
           commerce.paid_order_count AS source_row_count,
           'Paid canonical orders across current schema versions' AS evidence_note,
           commerce.data_freshness_at
    FROM tenants tenant JOIN commerce ON commerce.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'traffic.visitor_count',
           CAST(behavior.visitor_count AS DECIMAL(38,6)),
           CAST(behavior.visitor_count AS DECIMAL(38,6)), CAST(NULL AS DECIMAL(38,6)), 'count',
           behavior.session_count,
           'Distinct linked principal, falling back to anonymous session; LOCAL_TEST governed behavior events',
           behavior.data_freshness_at
    FROM tenants tenant JOIN behavior_session behavior ON behavior.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'search.success_rate',
           CAST(search.successful_search_count * 100.0 / NULLIF(search.search_request_count, 0) AS DECIMAL(38,6)),
           CAST(search.successful_search_count AS DECIMAL(38,6)),
           CAST(search.search_request_count AS DECIMAL(38,6)), 'percent', search.search_request_count,
           'Searches with an exposed result and a governed click/PDP/cart/checkout continuation',
           search.data_freshness_at
    FROM tenants tenant JOIN search_funnel search ON search.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'funnel.product_detail_view_count',
           CAST(behavior.pdp_view_count AS DECIMAL(38,6)),
           CAST(behavior.pdp_view_count AS DECIMAL(38,6)), CAST(NULL AS DECIMAL(38,6)), 'count',
           behavior.behavior_event_count, 'Append-only governed PDP_VIEWED events', behavior.data_freshness_at
    FROM tenants tenant JOIN behavior_event behavior ON behavior.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'funnel.add_to_cart_rate',
           CAST(behavior.cart_visitor_count * 100.0 / NULLIF(behavior.pdp_visitor_count, 0) AS DECIMAL(38,6)),
           CAST(behavior.cart_visitor_count AS DECIMAL(38,6)),
           CAST(behavior.pdp_visitor_count AS DECIMAL(38,6)), 'percent', behavior.session_count,
           'Distinct linked-or-anonymous subjects adding to cart after observable PDP engagement',
           behavior.data_freshness_at
    FROM tenants tenant JOIN behavior_session behavior ON behavior.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'funnel.checkout_start_rate',
           CAST(behavior.checkout_visitor_count * 100.0 / NULLIF(behavior.cart_visitor_count, 0) AS DECIMAL(38,6)),
           CAST(behavior.checkout_visitor_count AS DECIMAL(38,6)),
           CAST(behavior.cart_visitor_count AS DECIMAL(38,6)), 'percent', behavior.session_count,
           'Distinct linked-or-anonymous subjects starting checkout after cart engagement',
           behavior.data_freshness_at
    FROM tenants tenant JOIN behavior_session behavior ON behavior.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'funnel.visit_to_pay_rate',
           CAST(behavior.paid_visitor_count * 100.0 / NULLIF(behavior.visitor_count, 0) AS DECIMAL(38,6)),
           CAST(behavior.paid_visitor_count AS DECIMAL(38,6)),
           CAST(behavior.visitor_count AS DECIMAL(38,6)), 'percent', behavior.session_count,
           'Strict session principal plus checkout-token attribution to canonical paid order/payment',
           behavior.data_freshness_at
    FROM tenants tenant JOIN behavior_session behavior ON behavior.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'funnel.cart_abandonment_rate',
           CAST(behavior.unpaid_cart_subject_count * 100.0 / NULLIF(behavior.cart_visitor_count, 0) AS DECIMAL(38,6)),
           CAST(behavior.unpaid_cart_subject_count AS DECIMAL(38,6)),
           CAST(behavior.cart_visitor_count AS DECIMAL(38,6)), 'percent', behavior.session_count,
           'Distinct cart subjects without any strict paid attribution in the observed window',
           behavior.data_freshness_at
    FROM tenants tenant JOIN behavior_session behavior ON behavior.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'commerce.captured_amount_yuan',
           CAST(commerce.captured_amount_minor / 100.0 AS DECIMAL(38,6)),
           CAST(commerce.captured_amount_minor AS DECIMAL(38,6)), CAST(100 AS DECIMAL(38,6)), 'yuan',
           commerce.paid_order_count, 'Captured amount across current canonical payments', commerce.data_freshness_at
    FROM tenants tenant JOIN commerce ON commerce.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'commerce.reconciled_rate',
           CAST(readiness.reconciled_order_count * 100.0 / NULLIF(readiness.order_count, 0) AS DECIMAL(38,6)),
           CAST(readiness.reconciled_order_count AS DECIMAL(38,6)),
           CAST(readiness.order_count AS DECIMAL(38,6)), 'percent', readiness.order_count,
           'Commerce-v2 orders passing full cross-domain reconciliation', readiness.data_freshness_at
    FROM tenants tenant JOIN commerce_readiness readiness ON readiness.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'commerce.gmv_yuan',
           CAST(commerce.captured_amount_minor / 100.0 AS DECIMAL(38,6)),
           CAST(commerce.captured_amount_minor AS DECIMAL(38,6)), CAST(100 AS DECIMAL(38,6)), 'yuan',
           commerce.paid_order_count, 'Captured amount before refunds', commerce.data_freshness_at
    FROM tenants tenant JOIN commerce ON commerce.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'commerce.net_gmv_yuan',
           CAST((commerce.captured_amount_minor - commerce.refunded_amount_minor) / 100.0 AS DECIMAL(38,6)),
           CAST(commerce.captured_amount_minor - commerce.refunded_amount_minor AS DECIMAL(38,6)),
           CAST(100 AS DECIMAL(38,6)), 'yuan', commerce.paid_order_count,
           'Captured amount minus cumulative refunded amount', commerce.data_freshness_at
    FROM tenants tenant JOIN commerce ON commerce.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'commerce.paid_buyer_count',
           CAST(commerce.paid_buyer_count AS DECIMAL(38,6)),
           CAST(commerce.paid_buyer_count AS DECIMAL(38,6)), CAST(NULL AS DECIMAL(38,6)), 'count',
           commerce.paid_order_count, 'Distinct buyers on paid canonical orders', commerce.data_freshness_at
    FROM tenants tenant JOIN commerce ON commerce.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'commerce.average_order_value_yuan',
           CAST(commerce.captured_amount_minor / NULLIF(commerce.paid_order_count, 0) / 100.0 AS DECIMAL(38,6)),
           CAST(commerce.captured_amount_minor AS DECIMAL(38,6)),
           CAST(commerce.paid_order_count * 100 AS DECIMAL(38,6)), 'yuan', commerce.paid_order_count,
           'Captured amount divided by paid canonical orders', commerce.data_freshness_at
    FROM tenants tenant JOIN commerce ON commerce.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'buyer.time_to_first_order_hours',
           first_paid.first_order_hours_p50,
           first_paid.first_order_hours_p50, CAST(NULL AS DECIMAL(38,6)), 'hours',
           first_paid.buyer_count,
           'Median hours from first linked governed visit to first strictly attributed paid order',
           first_paid.data_freshness_at
    FROM tenants tenant JOIN buyer_first_paid_p50 first_paid ON first_paid.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'buyer.repeat_purchase_rate_90d',
           CAST(buyer.repeat_buyer_count * 100.0 / NULLIF(buyer.active_buyer_count, 0) AS DECIMAL(38,6)),
           CAST(buyer.repeat_buyer_count AS DECIMAL(38,6)),
           CAST(buyer.active_buyer_count AS DECIMAL(38,6)), 'percent', buyer.active_buyer_count,
           'Trailing 90 days relative to latest loaded paid order; loaded-history scope', window.window_end_at
    FROM tenants tenant JOIN buyer_90d_rollup buyer ON buyer.tenant_id = tenant.tenant_id
    JOIN buyer_window window ON window.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'buyer.order_frequency_90d',
           CAST(buyer.paid_order_count * 1.0 / NULLIF(buyer.active_buyer_count, 0) AS DECIMAL(38,6)),
           CAST(buyer.paid_order_count AS DECIMAL(38,6)),
           CAST(buyer.active_buyer_count AS DECIMAL(38,6)), 'ratio', buyer.active_buyer_count,
           'Trailing 90-day paid orders per active buyer; loaded-history scope', window.window_end_at
    FROM tenants tenant JOIN buyer_90d_rollup buyer ON buyer.tenant_id = tenant.tenant_id
    JOIN buyer_window window ON window.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'buyer.category_breadth_90d',
           CAST(buyer.category_count * 1.0 / NULLIF(buyer.buyer_count, 0) AS DECIMAL(38,6)),
           CAST(buyer.category_count AS DECIMAL(38,6)), CAST(buyer.buyer_count AS DECIMAL(38,6)),
           'ratio', buyer.buyer_count, 'Average mapped categories per paid buyer in trailing 90 days', window.window_end_at
    FROM tenants tenant JOIN buyer_category_rollup buyer ON buyer.tenant_id = tenant.tenant_id
    JOIN buyer_window window ON window.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'buyer.return_rate',
           CAST(COALESCE(returned.returned_order_item_count, 0) * 100.0 /
                NULLIF(fulfilled.fulfilled_order_item_count, 0) AS DECIMAL(38,6)),
           CAST(COALESCE(returned.returned_order_item_count, 0) AS DECIMAL(38,6)),
           CAST(fulfilled.fulfilled_order_item_count AS DECIMAL(38,6)), 'percent',
           fulfilled.fulfilled_order_item_count, 'Returned order lines divided by fulfilled order lines',
           fulfilled.data_freshness_at
    FROM tenants tenant JOIN fulfilled_items fulfilled ON fulfilled.tenant_id = tenant.tenant_id
    LEFT JOIN returned_items returned ON returned.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'buyer.refund_cycle_hours',
           refund.refund_cycle_hours_p50,
           refund.refund_cycle_hours_p50, CAST(NULL AS DECIMAL(38,6)), 'hours',
           refund.refund_count, 'Median hours from refund requested to success; future-dated simulation events are excluded',
           refund.data_freshness_at
    FROM tenants tenant JOIN refund_cycle_p50 refund ON refund.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'merchant.active_merchant_count',
           CAST(supply.active_merchant_count AS DECIMAL(38,6)),
           CAST(supply.active_merchant_count AS DECIMAL(38,6)),
           CAST(supply.candidate_merchant_count AS DECIMAL(38,6)), 'count',
           supply.candidate_merchant_count, 'Active merchant/shop with at least one sellable offer', supply.data_freshness_at
    FROM tenants tenant JOIN merchant_supply supply ON supply.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'merchant.new_buyer_count',
           CAST(acquisition.new_buyer_count AS DECIMAL(38,6)),
           CAST(acquisition.new_buyer_count AS DECIMAL(38,6)),
           CAST(NULL AS DECIMAL(38,6)), 'count', acquisition.merchant_day_row_count,
           'Distinct buyers whose first strictly attributed paid order is with the governed merchant',
           acquisition.data_freshness_at
    FROM tenants tenant JOIN merchant_acquisition acquisition ON acquisition.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'merchant.store_conversion_rate',
           CAST(acquisition.paid_store_subject_count * 100.0 / NULLIF(acquisition.visited_store_subject_count, 0) AS DECIMAL(38,6)),
           CAST(acquisition.paid_store_subject_count AS DECIMAL(38,6)),
           CAST(acquisition.visited_store_subject_count AS DECIMAL(38,6)), 'percent',
           acquisition.visited_store_subject_count,
           'Distinct shop visitors with validated listing-offer behavior and strict shop-level paid attribution',
           acquisition.data_freshness_at
    FROM tenants tenant JOIN merchant_acquisition acquisition ON acquisition.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'merchant.cancellation_rate',
           merchant.metric_value, merchant.numerator, merchant.denominator, merchant.unit,
           merchant.source_row_count, merchant.evidence_note, merchant.data_freshness_at
    FROM tenants tenant JOIN merchant_cancellations merchant ON merchant.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'merchant.net_sales_yuan',
           CAST(merchant.merchant_net_sales_amount_minor / 100.0 AS DECIMAL(38,6)),
           CAST(merchant.merchant_net_sales_amount_minor AS DECIMAL(38,6)),
           CAST(100 AS DECIMAL(38,6)), 'yuan', merchant.profitability_item_count,
           'Order-item net revenue joined through frozen shop/channel merchant mapping, minus fully refunded paid cancellations',
           merchant.data_freshness_at
    FROM tenants tenant JOIN merchant_net_sales merchant ON merchant.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'marketing.ad_roas',
           CAST(marketing.attribution_amount_minor * 1.0 / NULLIF(marketing.ad_spend_amount_minor, 0) AS DECIMAL(38,6)),
           CAST(marketing.attribution_amount_minor AS DECIMAL(38,6)),
           CAST(marketing.ad_spend_amount_minor AS DECIMAL(38,6)), 'ratio', marketing.campaign_row_count,
           'Governed attributed order amount divided by immutable advertising spend ledger',
           marketing.data_freshness_at
    FROM tenants tenant JOIN marketing ON marketing.tenant_id = tenant.tenant_id
    WHERE marketing.ad_spend_amount_minor > 0
    UNION ALL
    SELECT tenant.tenant_id, 'marketing.promotion_roi',
           CAST(marketing.incremental_contribution_profit_minor * 1.0 / NULLIF(marketing.promotion_cost_minor, 0) AS DECIMAL(38,6)),
           CAST(marketing.incremental_contribution_profit_minor AS DECIMAL(38,6)),
           CAST(marketing.promotion_cost_minor AS DECIMAL(38,6)), 'ratio', marketing.campaign_row_count,
           'Governed experiment incremental contribution profit divided by booked promotion cost',
           marketing.data_freshness_at
    FROM tenants tenant JOIN marketing ON marketing.tenant_id = tenant.tenant_id
    WHERE marketing.promotion_cost_minor > 0
    UNION ALL
    SELECT tenant.tenant_id, 'listing.active_offer_count',
           CAST(supply.active_offer_count AS DECIMAL(38,6)),
           CAST(supply.active_offer_count AS DECIMAL(38,6)), CAST(NULL AS DECIMAL(38,6)), 'count',
           supply.active_offer_count, 'Enabled published offer with active SKU and merchant/shop', supply.data_freshness_at
    FROM tenants tenant JOIN merchant_supply supply ON supply.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'listing.approval_rate',
           CAST(review.approved_listing_count * 100.0 / NULLIF(review.reviewed_listing_count, 0) AS DECIMAL(38,6)),
           CAST(review.approved_listing_count AS DECIMAL(38,6)),
           CAST(review.reviewed_listing_count AS DECIMAL(38,6)), 'percent', review.reviewed_listing_count,
           'Published listings passing the governed review workflow', review.data_freshness_at
    FROM tenants tenant JOIN listing_review review ON review.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'catalog.active_sku_count',
           CAST(catalog.active_sku_count AS DECIMAL(38,6)),
           CAST(catalog.active_sku_count AS DECIMAL(38,6)), CAST(NULL AS DECIMAL(38,6)), 'count',
           catalog.source_row_count, 'Distinct canonical SKUs in ACTIVE status', catalog.data_freshness_at
    FROM tenants tenant JOIN catalog ON catalog.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'catalog.selection_breadth',
           CAST(supply.selection_breadth AS DECIMAL(38,6)),
           CAST(supply.selection_breadth AS DECIMAL(38,6)), CAST(NULL AS DECIMAL(38,6)), 'count',
           supply.sellable_offer_count, 'Distinct in-stock SKU/category combinations with a sellable offer', supply.data_freshness_at
    FROM tenants tenant JOIN sellable_supply supply ON supply.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'inventory.available_quantity',
           CAST(inventory.available_quantity AS DECIMAL(38,6)),
           CAST(inventory.available_quantity AS DECIMAL(38,6)), CAST(NULL AS DECIMAL(38,6)), 'quantity',
           inventory.balance_count, 'Sellable canonical inventory balances', inventory.data_freshness_at
    FROM tenants tenant JOIN inventory ON inventory.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'inventory.balance_count',
           CAST(inventory.balance_count AS DECIMAL(38,6)),
           CAST(inventory.balance_count AS DECIMAL(38,6)), CAST(NULL AS DECIMAL(38,6)), 'count',
           inventory.balance_count, 'Canonical inventory balance rows', inventory.data_freshness_at
    FROM tenants tenant JOIN inventory ON inventory.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'inventory.canonical_v3_rate',
           CAST(inventory.canonical_v3_balance_count * 100.0 / NULLIF(inventory.balance_count, 0) AS DECIMAL(38,6)),
           CAST(inventory.canonical_v3_balance_count AS DECIMAL(38,6)),
           CAST(inventory.balance_count AS DECIMAL(38,6)), 'percent', inventory.balance_count,
           'Inventory balances with canonical V3 dimensions resolved', inventory.data_freshness_at
    FROM tenants tenant JOIN inventory ON inventory.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'inventory.low_stock_balance_count',
           CAST(inventory.low_stock_balance_count AS DECIMAL(38,6)),
           CAST(inventory.low_stock_balance_count AS DECIMAL(38,6)), CAST(NULL AS DECIMAL(38,6)), 'count',
           inventory.balance_count, 'Inventory balances classified LOW_STOCK', inventory.data_freshness_at
    FROM tenants tenant JOIN inventory ON inventory.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'inventory.out_of_stock_balance_count',
           CAST(inventory.out_of_stock_balance_count AS DECIMAL(38,6)),
           CAST(inventory.out_of_stock_balance_count AS DECIMAL(38,6)), CAST(NULL AS DECIMAL(38,6)), 'count',
           inventory.balance_count, 'Inventory balances classified OUT_OF_STOCK', inventory.data_freshness_at
    FROM tenants tenant JOIN inventory ON inventory.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'inventory.in_stock_rate',
           CAST(supply.in_stock_offer_count * 100.0 / NULLIF(supply.observable_offer_count, 0) AS DECIMAL(38,6)),
           CAST(supply.in_stock_offer_count AS DECIMAL(38,6)),
           CAST(supply.observable_offer_count AS DECIMAL(38,6)), 'percent', supply.sellable_offer_count,
           'Positive inventory among observable sellable offers; source_row_count is all sellable offers', supply.data_freshness_at
    FROM tenants tenant JOIN sellable_supply supply ON supply.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'inventory.stockout_rate',
           CAST(supply.out_of_stock_offer_count * 100.0 / NULLIF(supply.observable_offer_count, 0) AS DECIMAL(38,6)),
           CAST(supply.out_of_stock_offer_count AS DECIMAL(38,6)),
           CAST(supply.observable_offer_count AS DECIMAL(38,6)), 'percent', supply.sellable_offer_count,
           'Zero inventory among observable sellable offers; missing inventory mapping is excluded', supply.data_freshness_at
    FROM tenants tenant JOIN sellable_supply supply ON supply.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'inventory.sell_through_rate_30d',
           CAST(sell_through.net_sold_quantity_30d * 100.0 /
                NULLIF(sell_through.denominator_quantity_30d, 0) AS DECIMAL(38,6)),
           CAST(sell_through.net_sold_quantity_30d AS DECIMAL(38,6)),
           CAST(sell_through.denominator_quantity_30d AS DECIMAL(38,6)), 'percent',
           CAST(CEIL(sell_through.denominator_quantity_30d) AS BIGINT),
           'Net shipped quantity divided by opening available plus purchase receipts over the trailing 30 observed days',
           sell_through.data_freshness_at
    FROM tenants tenant JOIN inventory_sell_through sell_through ON sell_through.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'payment.success_rate',
           CAST(payment.successful_payment_count * 100.0 / NULLIF(payment.payment_attempt_count, 0) AS DECIMAL(38,6)),
           CAST(payment.successful_payment_count AS DECIMAL(38,6)),
           CAST(payment.payment_attempt_count AS DECIMAL(38,6)), 'percent', payment.payment_attempt_count,
           'Canonical current payments; local fixture population must be shown with sample size', payment.data_freshness_at
    FROM tenants tenant JOIN payments payment ON payment.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'promotion.coupon_redemption_rate',
           CAST(coupon.used_coupon_count * 100.0 / NULLIF(coupon.claimed_coupon_count, 0) AS DECIMAL(38,6)),
           CAST(coupon.used_coupon_count AS DECIMAL(38,6)),
           CAST(coupon.claimed_coupon_count AS DECIMAL(38,6)), 'percent', coupon.claimed_coupon_count,
           'Current canonical entitlement occupancy; returned rights are not counted as currently used', coupon.data_freshness_at
    FROM tenants tenant JOIN coupons coupon ON coupon.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'finance.discount_funding_yuan',
           CAST(funding.funding_amount_minor / 100.0 AS DECIMAL(38,6)),
           CAST(funding.funding_amount_minor AS DECIMAL(38,6)), CAST(100 AS DECIMAL(38,6)), 'yuan',
           funding.funding_row_count, 'Platform, merchant and third-party benefit funding allocations', funding.data_freshness_at
    FROM tenants tenant JOIN benefit_funding funding ON funding.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'aftersales.case_count',
           CAST(aftersales.case_count AS DECIMAL(38,6)),
           CAST(aftersales.case_count AS DECIMAL(38,6)), CAST(NULL AS DECIMAL(38,6)), 'count',
           aftersales.case_count, 'Distinct canonical after-sale cases', aftersales.data_freshness_at
    FROM tenants tenant JOIN aftersales ON aftersales.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'aftersales.reconciled_rate',
           CAST(readiness.reconciled_case_count * 100.0 / NULLIF(readiness.case_count, 0) AS DECIMAL(38,6)),
           CAST(readiness.reconciled_case_count AS DECIMAL(38,6)),
           CAST(readiness.case_count AS DECIMAL(38,6)), 'percent', readiness.case_count,
           'After-sale cases passing full reconciliation', readiness.data_freshness_at
    FROM tenants tenant JOIN aftersales_readiness readiness ON readiness.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'aftersales.recovery_required_count',
           CAST(readiness.recovery_required_count AS DECIMAL(38,6)),
           CAST(readiness.recovery_required_count AS DECIMAL(38,6)), CAST(NULL AS DECIMAL(38,6)), 'count',
           readiness.case_count, 'After-sale cases requiring or awaiting manual recovery', readiness.data_freshness_at
    FROM tenants tenant JOIN aftersales_readiness readiness ON readiness.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'aftersales.refunded_amount_yuan',
           CAST(refund.refunded_amount_minor / 100.0 AS DECIMAL(38,6)),
           CAST(refund.refunded_amount_minor AS DECIMAL(38,6)), CAST(100 AS DECIMAL(38,6)), 'yuan',
           refund.refund_count, 'Succeeded canonical after-sale refunds', refund.data_freshness_at
    FROM tenants tenant JOIN refunds refund ON refund.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'service.first_response_minutes',
           response.first_response_minutes_p50,
           response.first_response_minutes_p50, CAST(NULL AS DECIMAL(38,6)), 'minutes',
           response.response_ticket_count,
           'Median minutes from first customer inbound to first agent outbound; tickets without both events remain absent',
           response.data_freshness_at
    FROM tenants tenant JOIN service_first_response_p50 response ON response.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, risk.metric_id, risk.metric_value, risk.numerator, risk.denominator, risk.unit,
           risk.source_row_count, risk.evidence_note, risk.data_freshness_at
    FROM tenants tenant
    JOIN yshopping_ads.ads_canonical_risk_commerce_metrics risk ON risk.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'procurement.receipt_fulfillment_rate',
           CAST(procurement.received_quantity * 100.0 / NULLIF(procurement.ordered_quantity, 0) AS DECIMAL(38,6)),
           CAST(procurement.received_quantity AS DECIMAL(38,6)),
           CAST(procurement.ordered_quantity AS DECIMAL(38,6)), 'percent', procurement.purchase_order_count,
           'Received quantity divided by approved ordered quantity', procurement.data_freshness_at
    FROM tenants tenant JOIN procurement ON procurement.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'procurement.purchase_order_count',
           CAST(procurement.purchase_order_count AS DECIMAL(38,6)),
           CAST(procurement.purchase_order_count AS DECIMAL(38,6)), CAST(NULL AS DECIMAL(38,6)), 'count',
           procurement.purchase_order_count, 'Approved purchase orders in the fulfillment mart', procurement.data_freshness_at
    FROM tenants tenant JOIN procurement ON procurement.tenant_id = tenant.tenant_id
    UNION ALL
    SELECT tenant.tenant_id, 'procurement.open_order_count',
           CAST(procurement.open_order_count AS DECIMAL(38,6)),
           CAST(procurement.open_order_count AS DECIMAL(38,6)), CAST(NULL AS DECIMAL(38,6)), 'count',
           procurement.purchase_order_count, 'Purchase orders in OPEN or PARTIAL fulfillment status', procurement.data_freshness_at
    FROM tenants tenant JOIN procurement ON procurement.tenant_id = tenant.tenant_id
)
SELECT
    tenant_id,
    metric_id,
    metric_value,
    numerator,
    denominator,
    unit,
    'LOCAL_TEST_CANONICAL_CURRENT' AS evidence_scope,
    source_row_count,
    evidence_note,
    data_freshness_at
FROM metric_rows
WHERE metric_value IS NOT NULL;
