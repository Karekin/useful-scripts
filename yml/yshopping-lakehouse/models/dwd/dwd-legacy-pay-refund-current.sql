-- Bounded projection of legacy payment-refund current rows from the local Yudao source.
-- This is not a canonical refund ledger, reversible settlement effect, or after-sale authority.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_legacy_pay_refund_current AS
SELECT
    'yudao-commerce-observability' AS source_system,
    'pay_refund' AS source_table,
    refund.tenant_id,
    refund.id AS legacy_pay_refund_id,
    CONCAT('yudao-commerce-observability:', CAST(refund.tenant_id AS STRING), ':pay_refund:', CAST(refund.id AS STRING))
        AS legacy_pay_refund_key,
    refund.no AS legacy_pay_refund_no,
    refund.app_id,
    refund.channel_id,
    refund.channel_code,
    refund.order_id AS legacy_pay_order_id,
    refund.order_no AS legacy_pay_order_no,
    refund.user_id AS legacy_user_id,
    refund.user_type AS legacy_user_type,
    refund.merchant_order_id,
    refund.merchant_refund_id,
    refund.status AS legacy_status_code,
    refund.pay_price AS pay_amount_minor,
    refund.refund_price AS refund_amount_minor,
    refund.channel_order_no,
    refund.channel_refund_no,
    refund.success_time,
    refund.create_time AS source_created_at,
    refund.update_time AS source_updated_at,
    refund.deleted AS is_deleted,
    refund.refund_price > refund.pay_price AS refund_exceeds_pay_amount_flag,
    refund.success_time IS NOT NULL AND refund.success_time < refund.create_time
        AS success_before_create_flag,
    ((refund.channel_refund_no IS NOT NULL AND TRIM(refund.channel_refund_no) <> '')
        AND refund.success_time IS NULL) AS provider_reference_without_success_time_flag,
    (refund.merchant_order_id IS NULL OR TRIM(refund.merchant_order_id) = ''
        OR refund.merchant_refund_id IS NULL OR TRIM(refund.merchant_refund_id) = '')
        AS missing_business_reference_flag,
    'LEGACY_CURRENT_STATE_ROW' AS model_semantics
FROM yshopping_ods.pay_refund refund;
