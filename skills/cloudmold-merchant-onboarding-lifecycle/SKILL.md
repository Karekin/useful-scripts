---
name: cloudmold-merchant-onboarding-lifecycle
description: Review governed merchant onboarding material, route KYC and contract gates, activate eligible records, and verify merchant and shop states.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: merchant
    role: merchant-onboarding-operator
---

# 商家入驻运营

商家经营域的生命周期起点：用于商家准入资料检查、审批分流、激活和状态回读。执行前读取同目录 `skill-task.json`；KYC、合同和法定准入必须由权威系统或人工确认，Agent 不得绕过准入门禁。准入完成后，托管商家的验厂、试用期与成材评审由 `cloudmold-merchant-managed-growth-lifecycle` 接续。
