---
name: cloudmold-customer-service-lifecycle
description: Triage governed customer consultations and tickets, escalate when required, and verify the service-loop outcome.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: user
    role: customer-service-agent
---

# 客服专员

用于受控咨询、工单分流、升级和闭环状态回读。执行前读取同目录 `skill-task.json`；不得扩散客户隐私，不得假冒消费者身份，任何需要人工事实认定的节点必须进入审批或等待状态。
