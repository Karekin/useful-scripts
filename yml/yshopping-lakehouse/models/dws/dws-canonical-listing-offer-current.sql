CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_listing_offer_current AS
SELECT
    offer.tenant_id,
    offer.run_id,
    offer.listing_id,
    offer.listing_no,
    listing.merchant_id,
    offer.channel_code,
    offer.shop_id,
    offer.canonical_spu_id,
    offer.listing_offer_id,
    offer.canonical_sku_id,
    offer.listing_revision,
    offer.listing_version,
    offer.price_minor,
    offer.currency_code,
    offer.enabled,
    offer.external_offer_id,
    listing.current_status AS listing_status,
    catalog.catalog_status AS catalog_sku_status,
    merchant.merchant_status,
    merchant.shop_status,
    CASE
        WHEN merchant.merchant_id IS NOT NULL
         AND merchant.merchant_status = 'ACTIVE'
         AND merchant.shop_status = 'ACTIVE'
         AND merchant.channel_code = offer.channel_code
        THEN TRUE ELSE FALSE
    END AS merchant_shop_active,
    offer.recorded_at AS offer_freshness_at,
    listing.recorded_at AS listing_freshness_at,
    catalog.recorded_at AS catalog_freshness_at,
    merchant.data_freshness_at AS merchant_freshness_at
FROM yshopping_dim.dim_canonical_listing_offer_current offer
JOIN yshopping_dim.dim_canonical_listing_current listing
  ON listing.tenant_id = offer.tenant_id AND listing.listing_id = offer.listing_id
LEFT JOIN yshopping_dim.dim_canonical_catalog_sku_current catalog
  ON catalog.tenant_id = offer.tenant_id AND catalog.canonical_sku_id = offer.canonical_sku_id
LEFT JOIN yshopping_dws.dws_canonical_merchant_shop_current merchant
  ON merchant.tenant_id = offer.tenant_id
 AND merchant.merchant_id = listing.merchant_id
 AND merchant.shop_id = offer.shop_id;
