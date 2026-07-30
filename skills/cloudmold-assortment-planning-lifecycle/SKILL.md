---
name: cloudmold-assortment-planning-lifecycle
description: Operate the daily CloudMold assortment-manager main flow from trend signals and candidate discovery through AI evaluation, constrained portfolio selection, R3 approval, launch-calendar publication, and product-development handoff.
---

# CloudMold 选品与波段企划闭环

该 Skill 模拟选品经理/买手的每日主流程，不是单点查询或技术巡检。

## 业务闭环

1. 建立 occurrence 级全新波段，冻结目标人群、价格带、毛利率、退货率和上市窗口。
2. 从趋势、站内需求和供应信号建立三个候选商品概念。
3. 由 AI 对趋势热度、需求、受众匹配、供给风险和预测退货率进行多因子评分。
4. 在毛利、退货率、目标款数和价格带多样性约束下选择商品组合。
5. 通过 R3 独立审批后发布上市日历，并向商品开发/建档流程交接。
6. 只有波段达到 `PUBLISHED/v10`，且被选候选和交接物均存在，流程才算完成。

## 自动运行

AI 运营控制台每天由 Temporal Schedule 触发。测试环境输入按 occurrence 生成新的
`waveId`、候选池、证据摘要和日历/交接引用；同一 occurrence 重试保持幂等，不会重复建波段，
不同 occurrence 不会反复处理同一组候选。

## 风险边界

- 风险等级为 R3；批准凭证只能由审批子流程注入，输入不得自带有效批准证据。
- Catalog 只拥有选品企划事实，不写渠道价格、库存或刊登。
- 毛利或退货率不达标的候选必须失败关闭，不能为了凑款数降低约束。
- 所有状态变化必须保留幂等操作、版本历史和事务 Outbox。
