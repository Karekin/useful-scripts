-- Interprets only legacy promotion current rows. It does not create a canonical activity model.
CREATE OR REPLACE VIEW yshopping_dim.dim_legacy_activity_current AS
SELECT
    activity.*,
    CASE activity_status_code
        WHEN 10 THEN 'WAIT'
        WHEN 20 THEN 'RUN'
        WHEN 30 THEN 'END'
        WHEN 40 THEN 'CLOSE'
        ELSE 'UNKNOWN_LEGACY_STATUS'
    END AS activity_status_name,
    CASE
        WHEN is_deleted = TRUE THEN 'DELETED_CURRENT_ROW'
        WHEN time_window_applicable = FALSE THEN 'CURRENT_WITHOUT_TIME_WINDOW'
        WHEN invalid_time_window_flag THEN 'INVALID_TIME_WINDOW'
        WHEN CURRENT_TIMESTAMP() < start_time THEN 'SCHEDULED_BY_TIME'
        WHEN CURRENT_TIMESTAMP() <= end_time THEN 'ACTIVE_BY_TIME'
        ELSE 'ENDED_BY_TIME'
    END AS observed_lifecycle,
    'LEGACY_CURRENT_STATE_ENRICHMENT' AS dimension_semantics
FROM yshopping_dwd.dwd_legacy_activity_current activity;
