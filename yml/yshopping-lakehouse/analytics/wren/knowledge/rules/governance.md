## 查询边界

- 只能查询已经建模的 `yshopping_ads` 与 `yshopping_dws` 对象，不允许绕过语义模型访问 ODS、DIM、DWD 或 Superset/Wren 元数据库。
- 所有业务查询必须带 `tenant_id`。租户不明确时先请求补充，不得猜测或使用全租户结果。
- 默认只生成只读查询。不得通过 MCP、SQL 或应用代码执行写入、DDL、权限变更或自动执法。
- 不得查询或展示未在模型中显式暴露的 PII、物流单号、自由文本原因和错误信息。

## 证据与发布

- 当前模型只拥有本地测试证据，不得把 `RECONCILED`、`HEALTHY` 或零异常解释成生产完成。
- 空表、空结果或缺失时间戳应显示“缺少证据”，不得显示为零风险或已通过。
- 附件审计后的严格最终来源口径为 `0/719`，报表生成不能修改该事实。
- Snapshot 只能用于演示和一次性分析；Live 应通过受鉴权后端查询代理，不得把数据库凭证放入浏览器。
- 发布前必须经过规格校验、SQL allowlist、租户隔离、数据新鲜度和截图人工复核。

## 指标口径

- 金额字段以 minor unit 存储，展示为元时除以 100；禁止从格式化字符串反推金额。
- 库存数量使用 canonical inventory balance；WMS 负责物理作业，不是账面库存权威。
- 交易与售后闭合只按 ADS 的 `readiness_status = 'RECONCILED'` 计算，不重新发明闭合条件。
- 采购收货履约率为 `SUM(received_quantity) / SUM(ordered_quantity)`，分母为零时失败关闭。
- AI 线索只用于人工复核，`automatic_enforcement_enabled` 必须保持 false。
