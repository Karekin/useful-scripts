CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_quality_current AS
SELECT *
FROM (
    SELECT
        event.*,
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id, aggregate_type, aggregate_id
            ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
        ) AS version_rank
    FROM yshopping_dwd.dwd_canonical_quality_event event
) ranked
WHERE version_rank = 1;
