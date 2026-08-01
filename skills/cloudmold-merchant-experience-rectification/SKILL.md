---
name: cloudmold-merchant-experience-rectification
description: Operate the governed CloudMold merchant-triggered consumer-experience recovery flow after an effective merchant-responsibility decision and paid service compensation.
---

# 商家触发整改与消费者体验恢复

该 `BUSINESS_ROLE` 主流程不是无条件触发。Temporal 只有在上一条消费者体验工单判责流程成功、工单已关闭且服务补偿已支付后，才生成商家整改任务。

1. 校验被判责商家和店铺仍为有效规范主体。
2. 创建、通知并认领商家整改行动单，来源引用绑定具体商家。
3. 重开原消费者工单，向消费者回传商家整改进度。
4. 记录整改后的二次解决和独立质量验收。
5. 收集消费者体验恢复反馈，重新关闭工单。
6. 关闭商家整改行动单，并回读行动单和消费者工单双终态。

本测试场景记录 `RECTIFICATION_VERIFIED / MERCHANT_ACTION_COMPLETED`，并以消费者满意反馈作为恢复证据。R3 写操作必须通过商家体验运营岗位审批，并由客服和运营负责人会签。

当前流程使用 CloudMold 内部商家、客服和运营事实，不冒充外部商家工作台签收、平台处罚、扣款或真实通知渠道；这些权威能力接入后应替换当前受控整改证据。
