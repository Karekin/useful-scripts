CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_merchant_order_item_sales_current AS
WITH merchant_responsible_cancellation AS (
    SELECT DISTINCT
        tenant_id,
        order_id,
        saga_id,
        responsibility_code,
        data_freshness_at
    FROM yshopping_dws.dws_canonical_merchant_cancellation_current
    WHERE counts_toward_paid_cancellation_rate = TRUE
      AND responsibility_party = 'MERCHANT'
      AND cancellation_mode = 'PAID_UNSHIPPED'
      AND order_status_at_request = 'PAYMENT_CONFIRMED'
      AND saga_status = 'COMPLETED'
      AND order_status = 'CANCELLED'
      AND order_cancellation_saga_id = saga_id
      AND order_responsibility_party = responsibility_party
      AND order_responsibility_code = responsibility_code
)
SELECT
    item.tenant_id,
    item.run_id,
    offer.merchant_id,
    offer.shop_id,
    offer.channel_code,
    item.order_id,
    item.order_no,
    item.order_item_id,
    item.canonical_sku_id,
    item.listing_id,
    item.listing_offer_id,
    item.currency_code,
    item.quantity,
    GREATEST(item.line_amount_minor - COALESCE(benefit.discount_amount_minor, 0), 0)
      AS merchant_booked_sales_amount_minor,
    LEAST(
        GREATEST(COALESCE(settlement.refunded_net_amount_minor, 0), 0),
        GREATEST(item.line_amount_minor - COALESCE(benefit.discount_amount_minor, 0), 0)
    )
      AS merchant_refund_deduction_amount_minor,
    CASE
        WHEN cancellation.order_id IS NOT NULL
        THEN GREATEST(
            GREATEST(item.line_amount_minor - COALESCE(benefit.discount_amount_minor, 0), 0)
              - LEAST(
                    GREATEST(COALESCE(settlement.refunded_net_amount_minor, 0), 0),
                    GREATEST(item.line_amount_minor - COALESCE(benefit.discount_amount_minor, 0), 0)
                ),
            0
        )
        ELSE 0
    END AS merchant_cancellation_deduction_amount_minor,
    GREATEST(item.line_amount_minor - COALESCE(benefit.discount_amount_minor, 0), 0)
      - LEAST(
            GREATEST(COALESCE(settlement.refunded_net_amount_minor, 0), 0),
            GREATEST(item.line_amount_minor - COALESCE(benefit.discount_amount_minor, 0), 0)
        )
      - CASE
            WHEN cancellation.order_id IS NOT NULL
            THEN GREATEST(
                GREATEST(item.line_amount_minor - COALESCE(benefit.discount_amount_minor, 0), 0)
                  - LEAST(
                        GREATEST(COALESCE(settlement.refunded_net_amount_minor, 0), 0),
                        GREATEST(item.line_amount_minor - COALESCE(benefit.discount_amount_minor, 0), 0)
                    ),
                0
            )
            ELSE 0
        END AS merchant_net_sales_amount_minor,
    cancellation.saga_id AS merchant_cancellation_saga_id,
    cancellation.responsibility_code AS merchant_cancellation_responsibility_code,
    GREATEST(
        item.item_freshness_at,
        item.order_freshness_at,
        COALESCE(item.payment_freshness_at, item.item_freshness_at),
        offer.offer_freshness_at,
        COALESCE(benefit.benefit_freshness_at, item.item_freshness_at),
        COALESCE(settlement.recorded_at, item.item_freshness_at),
        COALESCE(cancellation.data_freshness_at, item.item_freshness_at)
    ) AS data_freshness_at
FROM yshopping_dws.dws_canonical_order_item_current item
JOIN yshopping_dws.dws_canonical_listing_offer_current offer
  ON offer.tenant_id = item.tenant_id
 AND offer.listing_id = item.listing_id
 AND offer.listing_offer_id = item.listing_offer_id
 AND offer.canonical_sku_id = item.canonical_sku_id
 AND offer.shop_id = item.shop_id
 AND offer.channel_code = item.channel_code
LEFT JOIN yshopping_dws.dws_canonical_order_item_benefit_current benefit
  ON benefit.tenant_id = item.tenant_id
 AND benefit.order_id = item.order_id
 AND benefit.order_item_id = item.order_item_id
LEFT JOIN yshopping_dim.dim_canonical_order_item_return_settlement_current settlement
  ON settlement.tenant_id = item.tenant_id
 AND settlement.order_id = item.order_id
 AND settlement.order_item_id = item.order_item_id
LEFT JOIN merchant_responsible_cancellation cancellation
  ON cancellation.tenant_id = item.tenant_id
 AND cancellation.order_id = item.order_id
WHERE item.payment_status IN ('CAPTURED', 'PARTIALLY_REFUNDED', 'REFUNDED')
  AND item.captured_amount_minor > 0;
