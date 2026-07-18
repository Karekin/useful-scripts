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
- `/api/skills` 与 `/api/threads` 在未登录上下文下返回 `401`（鉴权边界正常）
- 容器均处于 `Up` 状态

## 结论
- 控制面链路转发可用，下一步继续推进：
  1) HSF MCP Adapter 的凭据上下文透传
  2) SkillTask 持久化执行器接入
  3) 按知识图谱节点更新 107 个未收口能力
