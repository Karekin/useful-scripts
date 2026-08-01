---
name: cloudmold-risk-dispute-resolution
description: Operate governed chargeback, dispute, loss-control, and loss-ledger workflows with explicit external decision gates.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: risk-data
    role: risk-operations
---

# 风险争议与损失运营

用于拒付、争议、止损和损失台账处置。执行前读取同目录 `skill-task.json`；生产风控模型、支付机构裁决和法律结论属于外部事实，Agent 不得自行判定最终责任。
