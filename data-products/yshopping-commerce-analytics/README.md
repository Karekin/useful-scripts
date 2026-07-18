# Y-Shopping 电商经营数据产品

这是 CloudMold 报表前端的**唯一可版本化数据入口**。它把报表所依赖的聚合快照、指标口径、角色视图和数据资产覆盖情况放在 `useful-scripts` 中，避免业务数字散落在前端组件里。

## 目录

```text
yshopping-commerce-analytics/
├── manifest-v1.json                         # 数据产品清单、血缘与证据边界
├── kpis/ecommerce-kpi-catalog-v1.json      # 多角色 KPI 语义目录
├── reports/report-portfolio-v1.json        # 角色视图与电商旅程编排
├── coverage/source-graduation-plan-v1.json # 719 来源终态处置、生产准入就绪与实际生产验收
├── coverage/kpi-data-gap-backlog-v1.json   # 缺失指标任务、责任人和验收条件
└── snapshots/local-test/tenant-1/latest.json # 脱敏聚合快照
```

前端发布副本位于：

```text
yml/yshopping-lakehouse/analytics/apps/cloudmold-analytics/app/data/
```

使用统一命令校验并同步：

```bash
./scripts/commerce-analyticsctl validate
./scripts/commerce-analyticsctl sync-site
```

`sync-site` 只复制聚合 JSON，不复制数据库凭证、买家标识、地址、电话、运单号或原始订单明细。正式刷新数据时，应由服务端 Agent 使用受限只读身份查询 StarRocks/Wren，先写入新快照并通过 `validate`，再更新站点副本。

## 当前证据边界

- `LOCAL_TEST` 数字来自 Tenant 1 的本地 StarRocks ADS，经 Wren 0.13.0 MySQL Connector 查询验证。
- Y-Shopping 当前治理宇宙为 719 项来源候选；严格生产最终语义证据仍为 `0/719`。
- 208 个 SQL 模型表示结构与建模资产，不等同于生产非空、财务对账或业务验收。
- `ads_ecommerce_role_metrics` 已将 33 个可验证指标汇聚成统一、聚合、无 PII 的角色报表接口。
- `coverage/kpi-source-readiness-v1.json` 对全部 76 个 KPI 逐项分类；缺权威语义的指标保持为空，不使用 0 或演示值替代。
- `coverage/kpi-data-gap-backlog-v1.json` 把 CDC、后端事件、身份回填、Promise/SLA 与商业账本缺口固化为 P0–P2 任务和验收条件。
- `coverage/source-graduation-plan-v1.json` 明确区分“719/719 已完成终态处置”“5 个来源已在 LOCAL_TEST 通过完整生产准入门禁”和“0 个来源已完成实际生产验收”；进入准入分子不要求先在生产产数。
- 经营驾驶舱是唯一跨域一级总览；七个专业视图的 76 个指标按责任域互斥编排，避免同一指标在多个页签反复出现。
- `ads_legacy_commerce_source_metrics` 单独暴露旧 Trade 当前快照及质量告警，明确标记为 `LEGACY_SOURCE_ONLY`，禁止与 Canonical 指标相加。
- 指标状态分为 `runtime_local_test`、`model_ready_no_runtime`、`governed_source_only`。前端对后两类显示“待运行”或“待接入”，不得把缺失值渲染成 0。

## 公开经营框架参考

指标组合参考公开披露的电商经营框架，而不是照搬任何公司的内部口径：

- Amazon：经营规模与质量同时看销售、经营利润、经营现金流/自由现金流；履约质量关注准时送达、有效追踪和取消率。
- Alibaba：围绕消费者、商家、品牌、零售商与服务商构建多边生态；买家体验关注供给、价格、质量、物流速度与可靠性、客服，商家侧关注交易、营销和供应链履约。
- Shopify：公开披露 GMV、收入、毛利、经营利润、自由现金流等平台经营指标。

官方参考：

- https://ir.aboutamazon.com/news-release/news-release-details/2026/Amazon-com-Announces-Fourth-Quarter-Results/
- https://sellercentral.amazon.com/gp/help/external/G202072570
- https://www.hkexnews.hk/listedco/listconews/sehk/2025/0626/2025062601064.pdf
- https://www.shopify.com/investors/press-releases/shopify-delivers-again-merchants-clear-100-billion-q1-gmv
