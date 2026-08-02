---
name: cloudmold-category-management-lifecycle
description: Govern the Catalog-owned, evidence-gated category-management lifecycle: scope, diagnosis, strategy, controlled domain handoffs, periodic review, remediation, upgrade, downgrade, and exit.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: product
    role: category-manager
---

# 品类管理全生命周期

这是 Catalog/商品域新增的业务角色级 **品类管理** SOP。Catalog 拥有品类策略、类目规则、准入结论、周期计划和跨域交接事实；它不直写 Merchant、Assortment、Listing、Inventory、Promotion、Quality、Supply Chain 或 BI 的权威数据。

执行前读取同目录 `skill-task.json`，再按下列资料运行：

| 资料 | 用途 |
| --- | --- |
| [生命周期与协作](references/lifecycle-sop.md) | 四层架构、16 周倒排、会议节奏、状态迁移、R3 决策与跨域边界。 |
| [规则与计算](references/rules-and-calculations.md) | 准入、优先级、卖法、坑位、F0、招商、QC、成本、人工升级。 |
| [报告与数据草案](references/report-and-data-contract.md) | 九部分报告、七张核心数据表草案、数据/BI 待定义项。 |

## 受控边界

- `cloudmold-assortment-planning-lifecycle` 仍拥有商品企划波段的候选、评估、组合、审批和发布。本 Skill 只提供已批准的品类目标、优先级和约束，并只读回查承接结果。
- `cloudmold-category-daily-operations` 保留原名和职责：下游每日问题诊断、新品铺货、实验、活动和消费者验证。本 Skill 不创建行动单，不执行这些日常运营动作，也不把其结果自动升级为品类结论。
- AI 只能产生带来源、时间窗、版本和不确定性的建议；人审及 R3 证据才可作出准入、开放、升级、降级、整改或退出结论。
- 当前没有品类管理专用 Catalog Capability 或执行器。`skill-task.json` 因而是不可运行的 `MANUAL_EVIDENCE_GATED` 定义；未接入的跨域操作只可形成受控交接和只读验收，不能伪造调用、写入或成功。

决策键固定为 `tenantId + categoryId + strategyVersion + reviewPeriod + transition`，并作为跨周期不可复用的幂等键。每次迁移必须引用期望的品类/策略版本并保留前一记录。未来实现必须把批准迁移与版本化 Outbox 事件同事务落库；本 Skill 不声称该能力已接入。

仅允许 local/test/demo 的受控演练；demo 不构成生产证据。缺少、过期、冲突或未经授权的证据时保持非终态并交人工处理，不得由 Agent 补造结论。
