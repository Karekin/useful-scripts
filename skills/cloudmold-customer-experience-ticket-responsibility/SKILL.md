---
name: cloudmold-customer-experience-ticket-responsibility
description: Operate the governed CloudMold consumer-experience ticket responsibility flow from a fresh consumer journey through complaint intake, evidence-linked investigation, merchant responsibility decision, service compensation, closure, and terminal readback.
---

# 消费者体验工单判责

该 `BUSINESS_ROLE` 主流程每天由 Temporal 创建一个全新的消费者订单与体验投诉案例，避免重复消费历史工单。

1. 创建、通知并认领消费者体验行动单。
2. 运行真实会员选购、支付、履约与售后子流程，取得规范消费者和订单引用。
3. 建立投诉工单并关联规范订单，记录受限存储中的投诉内容。
4. 客服接单调查、解决后，由独立质量复核写入判责结论与原因码。
5. 对商家责任体验缺口创建、审批并支付服务补偿，形成可审计赔付账。
6. 关闭工单与体验行动单，并双重回读业务终态。

判责结论固定保存在客服质量复核事实中；本测试场景为 `MERCHANT_RESPONSIBLE / PRODUCT_DESCRIPTION_MISMATCH`。R3 写操作必须通过消费者体验运营岗位审批，并由客服和质量责任人会签。

本流程不冒充真实支付渠道仲裁、平台处罚或司法责任认定。当前赔付使用 CloudMold 内部服务补偿账，外部支付和商家处罚仍需接入相应权威系统。
