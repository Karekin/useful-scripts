---
name: cloudmold-role-policy-planning
description: Enforce the read-only DeerFlow tool boundary for cloudmold-planning-agent.
allowed-tools:
  - ask_clarification
  - cloudmold-planning_cloudmold_analytics_dashboard_snapshot
---

# 岗位最小权限

本 Skill 只定义工具白名单，不定义业务知识，也不授权任何业务写入。

- 只能向用户追问必要信息。
- 只能读取本岗位对应的受治理经营快照。
- 不得提交、查询或重试 SkillTask。
- 不得调用其他岗位的经营快照。
