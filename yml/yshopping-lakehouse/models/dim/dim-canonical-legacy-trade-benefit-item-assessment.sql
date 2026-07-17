CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_legacy_trade_benefit_item_assessment AS
SELECT
    event.tenant_id,
    event.migration_run_id,
    event.candidate_id,
    event.legacy_order_id,
    event.legacy_order_no,
    event.assessment_status AS order_assessment_status,
    get_json_string(item.`value`, '$.item_evidence_id') AS item_evidence_id,
    CAST(get_json_string(item.`value`, '$.legacy_order_item_id') AS BIGINT) AS legacy_order_item_id,
    CAST(get_json_string(item.`value`, '$.legacy_buyer_id') AS BIGINT) AS legacy_buyer_id,
    get_json_string(item.`value`, '$.legacy_item_snapshot_hash') AS legacy_item_snapshot_hash,
    CAST(REPLACE(SUBSTR(get_json_string(item.`value`, '$.source_created_at'), 1, 19), 'T', ' ') AS DATETIME)
        AS source_created_at,
    CAST(REPLACE(SUBSTR(get_json_string(item.`value`, '$.source_updated_at'), 1, 19), 'T', ' ') AS DATETIME)
        AS source_updated_at,
    CAST(get_json_string(item.`value`, '$.is_deleted') AS BOOLEAN) AS is_deleted,
    CAST(get_json_string(item.`value`, '$.legacy_spu_id') AS BIGINT) AS legacy_spu_id,
    get_json_string(item.`value`, '$.legacy_spu_name') AS legacy_spu_name,
    CAST(get_json_string(item.`value`, '$.legacy_sku_id') AS BIGINT) AS legacy_sku_id,
    get_json_string(item.`value`, '$.legacy_sku_properties_json') AS legacy_sku_properties_json,
    get_json_string(item.`value`, '$.legacy_sku_pic_url') AS legacy_sku_pic_url,
    get_json_string(item.`value`, '$.historical_product_snapshot_hash') AS historical_product_snapshot_hash,
    get_json_string(item.`value`, '$.product_snapshot_status') AS product_snapshot_status,
    get_json_string(item.`value`, '$.product_snapshot_semantics') AS product_snapshot_semantics,
    get_json_string(item.`value`, '$.source_product_identity_status') AS source_product_identity_status,
    CAST(get_json_string(item.`value`, '$.item_quantity') AS BIGINT) AS item_quantity,
    CAST(get_json_string(item.`value`, '$.unit_price_minor') AS BIGINT) AS unit_price_minor,
    CAST(get_json_string(item.`value`, '$.gross_amount_minor') AS BIGINT) AS gross_amount_minor,
    CAST(get_json_string(item.`value`, '$.generic_discount_amount_minor') AS BIGINT)
        AS generic_discount_amount_minor,
    CAST(get_json_string(item.`value`, '$.coupon_amount_minor') AS BIGINT) AS coupon_amount_minor,
    CAST(get_json_string(item.`value`, '$.point_amount_minor') AS BIGINT) AS point_amount_minor,
    CAST(get_json_string(item.`value`, '$.vip_amount_minor') AS BIGINT) AS vip_amount_minor,
    CAST(get_json_string(item.`value`, '$.delivery_amount_minor') AS BIGINT) AS delivery_amount_minor,
    CAST(get_json_string(item.`value`, '$.adjust_amount_minor') AS BIGINT) AS adjust_amount_minor,
    CAST(get_json_string(item.`value`, '$.pay_amount_minor') AS BIGINT) AS pay_amount_minor,
    CAST(get_json_string(item.`value`, '$.used_point_quantity') AS BIGINT) AS used_point_quantity,
    CAST(get_json_string(item.`value`, '$.canonical_import_allowed') AS BOOLEAN) AS canonical_import_allowed,
    event.assessed_at
FROM yshopping_dwd.dwd_canonical_legacy_trade_benefit_assessment_event event,
     LATERAL json_each(event.items) item
WHERE event.schema_version IN (2, 3, 4) AND event.item_evidence_complete;
