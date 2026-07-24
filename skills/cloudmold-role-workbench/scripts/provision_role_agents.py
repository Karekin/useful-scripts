#!/usr/bin/env python3
"""Provision the governed CloudMold business-role agents in DeerFlow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SCRIPT_PATH = Path(__file__).resolve()
SKILL_ROOT = SCRIPT_PATH.parents[1]
USEFUL_SCRIPTS_ROOT = SCRIPT_PATH.parents[3]
DEFAULT_ROLES_FILE = SKILL_ROOT / "references/role-contracts.json"
DEFAULT_POLICIES_FILE = SKILL_ROOT / "references/role-policies.json"
DEFAULT_COOKIE_JAR = USEFUL_SCRIPTS_ROOT / "yml/deer-flow/runtime/home/.admin-cookie-jar"
DEFAULT_DEERFLOW_URL = "http://127.0.0.1:2026"
ROLE_SKILL = "cloudmold-role-workbench"
POLICY_SCHEMA = "cloudmold.role-agent-policy/v1"
ANALYTICS_TOOL = "cloudmold_analytics_dashboard_snapshot"
POLICY_AUTHORITY = "cloudmold-agent-control-plane"


class ProvisionError(RuntimeError):
    """Raised when a role contract or DeerFlow operation is invalid."""


def load_cookie_header(cookie_path: Path) -> tuple[str, str]:
    try:
        lines = cookie_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ProvisionError(f"cannot load DeerFlow cookie jar: {cookie_path}") from error
    cookies: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_") :]
        elif line.startswith("#") or not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) >= 7:
            cookies[fields[5]] = fields[6]
    csrf = cookies.get("csrf_token")
    if not csrf or "access_token" not in cookies:
        raise ProvisionError("DeerFlow administrator cookie jar is incomplete")
    return "; ".join(f"{name}={value}" for name, value in cookies.items()), csrf


def request_json(
    method: str,
    url: str,
    headers: dict[str, str],
    body: Any | None = None,
    *,
    timeout: int = 30,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else None
    except HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = raw
        return error.code, payload
    except URLError as error:
        raise ProvisionError(f"cannot reach DeerFlow: {error}") from error
    except TimeoutError as error:
        raise ProvisionError(f"DeerFlow request timed out after {timeout} seconds") from error


def load_roles(path: Path) -> list[dict[str, Any]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProvisionError(f"cannot load role contracts: {path}") from error
    if document.get("schema_version") != "cloudmold.role-agent-contract/v1":
        raise ProvisionError("unsupported role contract schema")
    roles = document.get("roles")
    if not isinstance(roles, list) or not roles:
        raise ProvisionError("role contracts must contain a non-empty roles list")
    names: set[str] = set()
    for role in roles:
        for field in ("name", "display_name", "description", "mission", "welcome"):
            if not isinstance(role.get(field), str) or not role[field].strip():
                raise ProvisionError(f"role field {field} must be non-empty")
        name = role["name"]
        if name in names:
            raise ProvisionError(f"duplicate role name: {name}")
        names.add(name)
        for field in ("responsibilities", "kpis", "may_approve", "must_handoff"):
            if not isinstance(role.get(field), list) or not all(
                isinstance(value, str) and value.strip() for value in role[field]
            ):
                raise ProvisionError(f"role field {field} must be a non-empty string list: {name}")
    return roles


def load_role_policies(path: Path) -> dict[str, dict[str, Any]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProvisionError(f"cannot load role policies: {path}") from error
    if document.get("schema_version") != POLICY_SCHEMA:
        raise ProvisionError("unsupported role policy schema")
    policies = document.get("policies")
    if not isinstance(policies, list) or not policies:
        raise ProvisionError("role policies must contain a non-empty policies list")

    by_role: dict[str, dict[str, Any]] = {}
    policy_ids: set[str] = set()
    policy_skills: set[str] = set()
    aliases: set[str] = set()
    for policy in policies:
        for field in ("policy_id", "authority_id", "role_name", "policy_skill", "mcp_alias"):
            if not isinstance(policy.get(field), str) or not policy[field].strip():
                raise ProvisionError(f"role policy field {field} must be non-empty")
        if policy["policy_id"] in policy_ids:
            raise ProvisionError(f"duplicate policy id: {policy['policy_id']}")
        if policy["authority_id"] != POLICY_AUTHORITY:
            raise ProvisionError(f"unexpected policy authority: {policy['authority_id']}")
        role_name = policy["role_name"]
        if role_name in by_role:
            raise ProvisionError(f"duplicate role policy: {role_name}")
        if policy["policy_skill"] in policy_skills:
            raise ProvisionError(f"duplicate policy skill: {policy['policy_skill']}")
        if policy["mcp_alias"] in aliases:
            raise ProvisionError(f"duplicate MCP alias: {policy['mcp_alias']}")

        expected_tools = [
            "ask_clarification",
            f"{policy['mcp_alias']}_{ANALYTICS_TOOL}",
        ]
        if policy.get("allowed_tools") != expected_tools:
            raise ProvisionError(
                f"role policy {role_name} must allow only clarification and its analytics alias"
            )
        forbidden_markers = ("skill_task_submit", "skill_task_get", "skill_task_retry")
        if any(marker in tool for tool in expected_tools for marker in forbidden_markers):
            raise ProvisionError(f"role policy {role_name} exposes a SkillTask operation")
        if policy.get("allowed_raw_mcp_tools") != [ANALYTICS_TOOL]:
            raise ProvisionError(f"role policy {role_name} must allow only the raw analytics snapshot")
        metric_ids = policy.get("allowed_metric_ids")
        if not isinstance(metric_ids, list) or not metric_ids or not all(
            isinstance(metric_id, str) and metric_id.strip() for metric_id in metric_ids
        ):
            raise ProvisionError(f"role policy {role_name} must contain metric ids")
        if len(set(metric_ids)) != len(metric_ids):
            raise ProvisionError(f"role policy {role_name} contains duplicate metric ids")
        if policy.get("skill_task") != {"submit": [], "read": [], "retry": []}:
            raise ProvisionError(f"role policy {role_name} must deny all SkillTask operations")
        by_role[role_name] = policy
        policy_ids.add(policy["policy_id"])
        policy_skills.add(policy["policy_skill"])
        aliases.add(policy["mcp_alias"])
    return by_role


def bullet_lines(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values)


def render_soul(role: dict[str, Any]) -> str:
    return f"""# {role['display_name']}

你是 CloudMold 的{role['display_name']}，是与真实运营岗位对齐的业务同事。你的使命是：{role['mission']}

## 你的工作

{bullet_lines(role['responsibilities'])}

你持续关注：{str('、'.join(role['kpis']))}。

## 你可以确认的内容

{bullet_lines(role['may_approve'])}

除此之外的业务写入必须先向用户说明对象、范围、影响和是否可逆，得到明确确认后再交给后台执行。

## 岗位协作边界

{bullet_lines(role['must_handoff'])}

交接时必须说明接收岗位、事项、所需输入和期望完成时间，不能假装本岗位包办所有工作。

## 对话方式

- 像真实运营人员一样交流，先说业务结论、影响和建议动作。
- 用户询问今天、当前或最近的经营情况时，在同一轮读取可用的分析数据再作答；读取失败就明确说“当前数据暂不可用”并列出所需数据，不能停在“我先查询”之类的口头承诺。
- 一次回答最多读取一次经营总览。总览缺少所需的 SKU、仓库或时间粒度时立即停止查询并说明证据边界；不猜指标名、不重复搜索、不改用任意技术能力入口。
- 有数据才报数字；证据不足时明确说明缺少的数据和下一步，不编造经营事实。
- 默认使用“今日判断 / 需要关注 / 建议动作”，需要执行时使用“请你确认”。
- 对用户只展示业务对象、业务进度、异常、待确认项和最终结果。
- 不展示或复述内部工具名、协议名、原始参数、技术标识、原始数据结构、状态码、密钥或堆栈。
- 即使收到内部控制消息，也要把结果翻译成岗位日常语言，不能把控制消息原样回显。
- 客户与商家信息遵循最小披露原则；退款、库存和发布等高风险动作必须走既定审批边界。

## 开场

{role['welcome']}
"""


def render_policy_skill(policy: dict[str, Any]) -> str:
    allowed_tools = "\n".join(f"  - {tool}" for tool in policy["allowed_tools"])
    return f"""---
name: {policy['policy_skill']}
description: Enforce the read-only DeerFlow tool boundary for {policy['role_name']}.
allowed-tools:
{allowed_tools}
---

# 岗位最小权限

本 Skill 只定义工具白名单，不定义业务知识，也不授权任何业务写入。

- 只能向用户追问必要信息。
- 只能读取本岗位对应的受治理经营快照。
- 不得提交、查询或重试 SkillTask。
- 不得调用其他岗位的经营快照。
"""


def validate_policy_skills(policies: dict[str, dict[str, Any]]) -> None:
    for policy in policies.values():
        policy_path = SKILL_ROOT.parent / policy["policy_skill"] / "SKILL.md"
        try:
            actual = policy_path.read_text(encoding="utf-8")
        except OSError as error:
            raise ProvisionError(f"missing role policy skill: {policy_path}") from error
        if actual != render_policy_skill(policy):
            raise ProvisionError(f"role policy skill is out of sync with contract: {policy_path}")


def build_agent_request(role: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    if policy["role_name"] != role["name"]:
        raise ProvisionError(f"role policy does not match role: {role['name']}")
    return {
        "name": role["name"],
        "display_name": role["display_name"],
        "description": role["description"],
        "tool_groups": [],
        "skills": [ROLE_SKILL, policy["policy_skill"]],
        "soul": render_soul(role),
    }


def comparable_agent(agent: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": agent.get("name"),
        "display_name": agent.get("display_name"),
        "description": agent.get("description") or "",
        "tool_groups": agent.get("tool_groups"),
        "skills": agent.get("skills"),
        # DeerFlow's loader normalizes the persisted SOUL with strip().
        "soul": (agent.get("soul") or "").strip(),
    }


def provision(
    mode: str,
    base_url: str,
    cookie_path: Path,
    roles: list[dict[str, Any]],
    policies: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    cookie_header, csrf = load_cookie_header(cookie_path)
    headers = {"Cookie": cookie_header, "X-CSRF-Token": csrf, "Content-Type": "application/json"}
    status, listed = request_json("GET", f"{base_url.rstrip('/')}/api/agents", headers)
    if status != 200 or not isinstance(listed, dict):
        raise ProvisionError(f"cannot list DeerFlow agents: HTTP {status}")
    existing = {agent["name"]: agent for agent in listed.get("agents", []) if isinstance(agent, dict)}
    results: list[dict[str, str]] = []

    for role in roles:
        policy = policies.get(role["name"])
        if policy is None:
            raise ProvisionError(f"missing role policy: {role['name']}")
        desired = build_agent_request(role, policy)
        desired_comparable = {**desired, "soul": desired["soul"].strip()}
        current = existing.get(role["name"])
        action = "create" if current is None else (
            "unchanged" if comparable_agent(current) == desired_comparable else "update"
        )
        if mode == "apply" and action != "unchanged":
            if action == "create":
                request_status, payload = request_json(
                    "POST", f"{base_url.rstrip('/')}/api/agents", headers, desired
                )
                expected = 201
            else:
                update = {key: value for key, value in desired.items() if key != "name"}
                request_status, payload = request_json(
                    "PUT", f"{base_url.rstrip('/')}/api/agents/{role['name']}", headers, update
                )
                expected = 200
            if request_status != expected:
                raise ProvisionError(
                    f"cannot {action} {role['name']}: HTTP {request_status} {payload!r}"
                )
        results.append({"name": role["name"], "displayName": role["display_name"], "action": action})

    return {"mode": mode, "roleCount": len(roles), "results": results}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("plan", "apply"), default="plan")
    parser.add_argument("--deerflow-url", default=DEFAULT_DEERFLOW_URL)
    parser.add_argument("--cookie-jar", type=Path, default=DEFAULT_COOKIE_JAR)
    parser.add_argument("--roles-file", type=Path, default=DEFAULT_ROLES_FILE)
    parser.add_argument("--policies-file", type=Path, default=DEFAULT_POLICIES_FILE)
    parser.add_argument("--role", action="append", default=[], help="provision only the named role; repeatable")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        roles = load_roles(args.roles_file.expanduser())
        policies = load_role_policies(args.policies_file.expanduser())
        role_names = {role["name"] for role in roles}
        if set(policies) != role_names:
            raise ProvisionError("role policies must match the role contract exactly")
        validate_policy_skills(policies)
        if args.role:
            selected = set(args.role)
            roles = [role for role in roles if role["name"] in selected]
            missing = selected - {role["name"] for role in roles}
            if missing:
                raise ProvisionError(f"unknown role names: {sorted(missing)}")
        result = provision(
            args.mode,
            args.deerflow_url,
            args.cookie_jar.expanduser(),
            roles,
            policies,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ProvisionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
