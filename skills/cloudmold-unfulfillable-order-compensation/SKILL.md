---
name: cloudmold-unfulfillable-order-compensation
description: Run the governed consumer compensation workflow for a paid, unshipped order that cannot be fulfilled.
---

# 无法履约订单主动赔付

先委托规范订单取消 Saga 完成发货拦截、全额退款、库存释放和订单取消，再创建客服工单完成平台责任判定、服务赔付、消费者通知与结案。不得由 Agent 直接调用 Payment 退款、Inventory 释放或 Order 终态命令。
