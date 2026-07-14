CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_listing_offer_current AS
SELECT
    offer.event_id, offer.tenant_id, offer.listing_id, offer.listing_no, offer.run_id,
    offer.listing_version, offer.listing_revision, offer.listing_status, offer.channel_code,
    offer.shop_id, offer.canonical_spu_id, offer.listing_offer_id, offer.canonical_sku_id,
    offer.offer_revision, offer.price_minor, offer.currency_code, offer.enabled,
    offer.external_offer_id, offer.occurred_at, offer.recorded_at
FROM yshopping_dwd.dwd_canonical_listing_offer_event offer
JOIN yshopping_dim.dim_canonical_listing_current listing
  ON listing.tenant_id = offer.tenant_id
 AND listing.listing_id = offer.listing_id
 AND listing.aggregate_version = offer.listing_version
 AND listing.revision = offer.listing_revision;
