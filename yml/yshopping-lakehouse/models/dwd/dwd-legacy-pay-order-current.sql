-- Bounded projection of legacy payment-order current rows from the local Yudao source.
-- This is not a canonical payment intent, attempt ledger, or immutable PSP event history.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_legacy_pay_order_current AS
SELECT
    'yudao-commerce-observability' AS source_system,
    'pay_order' AS source_table,
    pay.tenant_id,
    pay.id AS legacy_pay_order_id,
    CONCAT('yudao-commerce-observability:', CAST(pay.tenant_id AS STRING), ':pay_order:', CAST(pay.id AS STRING))
        AS legacy_pay_order_key,
    pay.app_id,
    pay.channel_id,
    pay.channel_code,
    pay.user_id AS legacy_user_id,
    pay.user_type AS legacy_user_type,
    pay.merchant_order_id,
    pay.no AS legacy_pay_order_no,
    pay.price AS payable_amount_minor,
    pay.refund_price AS refunded_amount_minor,
    pay.channel_fee_rate,
    pay.channel_fee_price,
    pay.status AS legacy_status_code,
    pay.expire_time,
    pay.success_time,
    pay.extension_id,
    pay.channel_order_no,
    pay.create_time AS source_created_at,
    pay.update_time AS source_updated_at,
    pay.deleted AS is_deleted,
    pay.refund_price > pay.price AS refund_exceeds_payable_flag,
    pay.expire_time < pay.create_time AS invalid_expire_window_flag,
    pay.success_time IS NOT NULL AND pay.success_time < pay.create_time
        AS success_before_create_flag,
    (pay.merchant_order_id IS NULL OR TRIM(pay.merchant_order_id) = '' OR pay.no IS NULL
        OR TRIM(pay.no) = '') AS missing_business_reference_flag,
    'LEGACY_CURRENT_STATE_ROW' AS model_semantics
FROM yshopping_ods.pay_order pay;
