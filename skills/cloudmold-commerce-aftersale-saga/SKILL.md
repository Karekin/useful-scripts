---
name: cloudmold-commerce-aftersale-saga
description: Operate governed return, refund, reverse-inventory, and terminal-state verification for the after-sales role.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: user
    role: aftersales-operator
---

# 售后运营

用于处理退货、退款、逆向入库和售后终态核验。执行前读取同目录 `skill-task.json`，所有写入必须沿用定义中的审批门禁和幂等键；支付机构结果、消费者真实身份和资金终态必须由外部权威系统确认。
