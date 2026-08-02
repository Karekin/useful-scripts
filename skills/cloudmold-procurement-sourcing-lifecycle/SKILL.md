---
name: cloudmold-procurement-sourcing-lifecycle
description: Execute canonical Procurement purchase requisition, multi-supplier sourcing, quotation, evaluation, award approval, and event close operations.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: procurement
    role: procurement-sourcing-operator
---

# 采购寻源与定标运营

执行前读取同目录 `skill-task.json`。输入必须明确携带已筛选的规范供应商 ID、法人主体、独立复核人和审批人；本流程不会创建供应商主档、替代供应商准入策略，也不会生成或猜测候选供应商。

流程由 Procurement 权威完成多行、多交期采购申请、寻源事件、双供应商报价、独立评分、定标审批和事件关闭。采购订单由独立的 Procurement 订单生命周期根据已批准定标快照创建。
