---
name: cloudmold-finance-close-lifecycle
description: Coordinate governed finance close, reconciliation exceptions, internal postings, approvals, and evidence readback.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: finance
    role: finance-operations
---

# 财务结算运营

用于关账编排、结算差异处置和内部凭证回读。执行前读取同目录 `skill-task.json`；银行、PSP、税务和法定账簿属于外部权威事实，所有财务写操作必须经过定义中的审批门禁。
