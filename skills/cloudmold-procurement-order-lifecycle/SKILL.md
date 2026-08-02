---
name: cloudmold-procurement-order-lifecycle
description: Generate purchase orders from one immutable approved award snapshot, then execute both resulting orders through confirmation.
metadata:
  cloudmold:
    schema_version: 1
    business_units: [dewu]
    domain: supply-chain
    role: procurement-order-operator
---

# 采购订单运营

执行前读取同目录 `skill-task.json`。输入只提交批准定标标识、期望版本和审计信封；法人主体、供应商、税额/舍入政策、逐行估值政策、金额和交期必须全部来自不可变定标快照。第一步由 `AwardReleaseCommandApi` 原子拆单并返回服务端生成的订单，后续步骤只引用该结果推进提交、批准、释放、下发和供应商确认。严禁调用方构造采购订单、猜测订单编号或回退旧 ERP。实物收货、质检和库存入账由 Warehouse、Quality 与 Inventory 权威完成。
