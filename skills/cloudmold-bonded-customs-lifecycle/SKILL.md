---
name: cloudmold-bonded-customs-lifecycle
description: Operate the governed bonded-customs document, exception, approval, and status-readback workflow without claiming external customs clearance.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: fulfillment
    role: bonded-customs-operations
---

# 保税关务运营

用于保税单证准备、异常分流、内部会签和状态回读。执行前读取同目录 `skill-task.json`，以其中的步骤、能力、审批和幂等约束为唯一执行定义；海关申报、放行和法定责任只能作为外部事实接入，不能由 Agent 伪造。
