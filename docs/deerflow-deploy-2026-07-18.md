# DeerFlow 部署记录（2026-07-18）

## 目标
- 使用 docker 部署 bytedance/deer-flow 最新可用版本并接入 CloudMold skill 目录

## 执行
- 仓库：`/Users/karekin/Downloads/coding/project/CloudMold/deer-flow`
- 版本：`v2.0.0`（`DEER_FLOW_EXPECTED_VERSION`）
- 启动命令：`cd /Users/karekin/Downloads/coding/project/CloudMold/useful-scripts && DEER_FLOW_PORT=2026 ./scripts/deerflowctl up`
- 运行服务：`deer-flow-frontend`, `deer-flow-gateway`, `deer-flow-nginx`
- 端口：`127.0.0.1:2026`

## 验证
- `curl http://127.0.0.1:2026/health` 返回 `200` 且 body 包含 `{"status":"healthy","service":"deer-flow-gateway"}`
- 本地管理员已初始化，凭据与 cookie 仅保存在被 Git 忽略且权限为 `0600` 的运行目录；未登录访问业务 API 返回 `401`
- `/api/skills` 经认证返回 11 个 CloudMold Skill，涵盖 Dubbo、ERP、WMS、MES、DreamPlant 和全链路 QA
- Store 已显式落到统一 SQLite 数据库；同一个 thread 经 `restart` 和完整 `down/up` 后仍可读取
- `/api/models` 能发现 `kimi-k2-5`；真实推理请求已到达 Moonshot，但当前账户因余额不足返回 `429`，因此模型回合尚未验收为成功
- 容器均处于 `Up` 状态

## 可复现部署锁

- DeerFlow tag：`v2.0.0`
- DeerFlow commit：`7e7f0410797693cf882594555ba414e0361d4c6f`
- Gateway image：`sha256:8bee8d7f607b3fcfa89eb721403c1a8e760adf8a45f37801bbd09c8a5989395d`
- Frontend image：`sha256:65b67a63dde2473fff4a7d7a4bbe109fac20b25a6b2c41fc0d85e1996c09af9e`
- Nginx base digest：`sha256:4a73073bd557c65b759505da037898b61f1be6cbcc3c2c3aeac22d2a470c1752`

## 结论
- 控制面链路转发可用，下一步继续推进：
  1) HSF MCP Adapter 的凭据上下文透传
  2) SkillTask 持久化执行器接入
  3) 按知识图谱节点更新 107 个未收口能力
