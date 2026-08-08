---
name: cloudmold-customer-sales-pipeline-lifecycle
description: 以客户与销售岗位完成线索培育、客户建档、联系人确认、商机推进、合同独立审批和应收结清回读。
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: customer-sales
    role: customer-sales-operator
---

# 客户与销售运营

这是 CRM 岗位级业务主流程，不是静态销售报表或旧 CRM 页面脚本。

每天由 Temporal 生成一组全新的受控销售场景，并在 R3 审批后执行：

1. 创建新线索并记录首次触达。
2. 将具备有效需求的线索推进为合格线索。
3. 建立客户与主要联系人，并把原线索标记为已转化。
4. 创建商机，记录商机跟进，依次推进方案、谈判和赢单阶段。
5. 赢单后创建引用 CloudMold 客户、Canonical SKU 和 Merchant 主体的销售合同，并提交独立 BPM 复核。
6. 等待与提交人不同的合同审批人完成复核；只有合同回读为 `ACTIVE/v3` 才继续。
7. 由 Finance 建立应收计划、登记客户回款并完成核销。
8. 只有应收计划 `SETTLED`、回款 `FULLY_ALLOCATED`，且未收与未核销金额均为 0 时，本次岗位工作才完成。

原始电话、邮箱、地址和沟通正文不得进入 SkillTask、Outbox 或运行证据；联系渠道只能使用受控引用与脱敏值。合同审批人必须有 ACTIVE 统一身份且与提交人分离；CRM 不持有回款权威，真实外部沟通送达和银行/支付渠道到账仍由对应外部权威事实约束。
