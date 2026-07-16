CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_after_sale_benefit_funding_reversal_event AS
SELECT
    reversal.event_id, reversal.schema_version, reversal.tenant_id,
    reversal.benefit_reversal_id, reversal.reversal_batch_id, reversal.after_sale_id,
    reversal.after_sale_item_id, reversal.order_id, reversal.order_item_id,
    reversal.benefit_application_id, reversal.benefit_allocation_id,
    reversal.amount_minor AS benefit_reversal_amount_minor,
    reversal.currency_code AS benefit_reversal_currency_code,
    reversal.occurred_at, reversal.recorded_at,
    get_json_string(funding.`value`, '$.funding_reversal_id') AS funding_reversal_id,
    get_json_string(funding.`value`, '$.benefit_funding_id') AS benefit_funding_id,
    get_json_string(funding.`value`, '$.funder_type') AS funder_type,
    get_json_string(funding.`value`, '$.funder_id') AS funder_id,
    CAST(get_json_string(funding.`value`, '$.amount_minor') AS BIGINT) AS amount_minor,
    get_json_string(funding.`value`, '$.currency_code') AS currency_code
FROM yshopping_dwd.dwd_canonical_after_sale_benefit_reversal_event reversal,
     LATERAL json_each(reversal.funding) funding;
