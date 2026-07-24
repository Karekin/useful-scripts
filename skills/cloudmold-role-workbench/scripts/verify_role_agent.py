#!/usr/bin/env python3
"""Verify one CloudMold role agent with a natural business conversation."""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

from provision_role_agents import (
    DEFAULT_COOKIE_JAR,
    DEFAULT_DEERFLOW_URL,
    DEFAULT_POLICIES_FILE,
    DEFAULT_ROLES_FILE,
    ProvisionError,
    load_cookie_header,
    load_role_policies,
    load_roles,
    request_json,
    validate_policy_skills,
)


DEFAULT_PROMPTS = {
    "cloudmold-planning-agent": "夏一波连衣裙销售进度偏慢，帮我判断今天企划上要先调整什么。",
    "cloudmold-buyer-agent": "这周要补一批夏季连衣裙，请帮我整理供应商比较时最需要关注的事项。",
    "cloudmold-merchant-agent": "本周有一批意向商家待跟进，帮我按日常招商节奏安排优先级。",
    "cloudmold-inventory-control-agent": "今天先帮我看看缺断码和积压风险，告诉我库控应该优先处理什么。",
    "cloudmold-customer-service-agent": "今天有一批售后工单快到时限了，帮我安排处理顺序和升级规则。",
    "cloudmold-customer-experience-agent": "最近退款相关反馈变多了，帮我从客户旅程角度梳理排查重点。",
}

FORBIDDEN_VISIBLE_TERMS = (
    "mcp",
    "hsf",
    "skilltask",
    "capability",
    "taskid",
    "approvalref",
    "tenantid",
    "operatorid",
    "clientrequestkey",
    "cloudmold_skill_task_",
)

FORBIDDEN_SKILL_TASK_MARKERS = (
    "skill_task_submit",
    "skill_task_get",
    "skill_task_retry",
)


def message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


def final_agent_answer(state: dict[str, Any]) -> str:
    messages = state.get("messages")
    if not isinstance(messages, list):
        raise ProvisionError("role-agent state contains no messages")
    for message in reversed(messages):
        if (
            isinstance(message, dict)
            and message.get("type") in {"ai", "assistant"}
            and not message.get("tool_calls")
        ):
            text = message_text(message).strip()
            if text:
                return text
    raise ProvisionError("role agent returned no visible answer")


def assert_business_language(answer: str) -> None:
    normalized = answer.lower().replace("_", "")
    leaked = [term for term in FORBIDDEN_VISIBLE_TERMS if term.replace("_", "") in normalized]
    if leaked:
        raise ProvisionError(f"role agent leaked technical vocabulary: {leaked}")
    if re.search(r'\{\s*"[A-Za-z][A-Za-z0-9_]*"\s*:', answer):
        raise ProvisionError("role agent exposed a raw JSON object")
    if len(answer) < 60:
        raise ProvisionError(
            f"role-agent answer is too short to be a useful business response: {answer[:200]!r}"
        )
    if re.fullmatch(r"(?s).*我先(?:调取|查看|查询|了解).{0,40}[。！]?", answer.strip()):
        raise ProvisionError("role agent stopped at a promise to inspect data without delivering a result")
    if not any(marker in answer for marker in ("今日判断", "当前数据", "需要关注", "建议动作")):
        raise ProvisionError("role-agent answer is missing a business conclusion or action section")


def assert_tool_policy(messages: list[dict[str, Any]], policy: dict[str, Any]) -> None:
    tool_names = [
        message.get("name")
        for message in messages
        if isinstance(message, dict) and message.get("type") == "tool"
    ]
    # tool_search is DeerFlow's deferred-discovery transport; the checked-in
    # policy skill itself still grants only clarification plus one role alias.
    allowed = {"tool_search", *policy["allowed_tools"]}
    unexpected = sorted({name for name in tool_names if name and name not in allowed})
    if unexpected:
        raise ProvisionError(f"role agent invoked tools outside its business whitelist: {unexpected}")
    leaked_skill_task_tools = sorted(
        {
            name
            for name in tool_names
            if name and any(marker in name for marker in FORBIDDEN_SKILL_TASK_MARKERS)
        }
    )
    if leaked_skill_task_tools:
        raise ProvisionError(f"role agent invoked forbidden SkillTask tools: {leaked_skill_task_tools}")
    analytics_tool = policy["allowed_tools"][1]
    if tool_names.count(analytics_tool) > 1:
        raise ProvisionError("role agent read the dashboard snapshot more than once")


def verify(
    base_url: str,
    cookie_path: Path,
    role: dict[str, Any],
    policy: dict[str, Any],
    prompt: str,
    model_name: str,
) -> dict[str, Any]:
    cookie_header, csrf = load_cookie_header(cookie_path)
    headers = {"Cookie": cookie_header, "X-CSRF-Token": csrf, "Content-Type": "application/json"}
    get_status, _ = request_json("GET", f"{base_url.rstrip('/')}/api/agents/{role['name']}", headers)
    if get_status != 200:
        raise ProvisionError(f"role agent is not provisioned: {role['name']}")

    thread_id = f"cloudmold-role-smoke-{role['name']}-{uuid.uuid4().hex[:8]}"
    metadata = {
        "purpose": "cloudmold-role-agent-smoke",
        "visibility": "internal_test",
        "agent_name": role["name"],
    }
    create_status, _ = request_json(
        "POST", f"{base_url.rstrip('/')}/api/threads", headers,
        {"thread_id": thread_id, "metadata": metadata},
    )
    if create_status not in {200, 201}:
        raise ProvisionError(f"cannot create role-agent test thread: HTTP {create_status}")
    body = {
        "assistant_id": role["name"],
        # Explicit defense in depth: persisted thread metadata is also copied
        # into the run so memory middleware can fail closed even if a gateway
        # implementation does not inherit thread metadata.
        "metadata": metadata,
        "input": {"messages": [{"role": "user", "content": prompt}]},
        # DeerFlow middleware and deferred tool-search each consume graph steps;
        # 20 can terminate a healthy two-tool business read before synthesis.
        "config": {"recursion_limit": 60},
        "context": {
            "agent_name": role["name"],
            "model_name": model_name,
            "mode": "flash",
            "thinking_enabled": False,
            "is_plan_mode": False,
            "subagent_enabled": False,
        },
        "stream_mode": ["values"],
    }
    run_status, state = request_json(
        "POST", f"{base_url.rstrip('/')}/api/threads/{thread_id}/runs/wait", headers, body,
        timeout=120,
    )
    if run_status != 200 or not isinstance(state, dict):
        raise ProvisionError(f"role-agent run failed: HTTP {run_status}")
    values = state.get("values", state)
    answer = final_agent_answer(values)
    try:
        assert_business_language(answer)
        assert_tool_policy(values.get("messages", []), policy)
    except ProvisionError as error:
        message_summary = [
            {
                "type": message.get("type"),
                "hasToolCalls": bool(message.get("tool_calls")),
                "name": message.get("name"),
                "contentPreview": message_text(message)[:240] if message.get("type") == "tool" else "",
            }
            for message in values.get("messages", [])
            if isinstance(message, dict)
        ]
        raise ProvisionError(
            f"{error}; thread={thread_id}; messages={message_summary}"
        ) from error
    return {
        "status": "PASSED",
        "role": role["display_name"],
        "agentName": role["name"],
        "threadId": thread_id,
        "prompt": prompt,
        "answerPreview": answer[:1200],
        "answerLength": len(answer),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deerflow-url", default=DEFAULT_DEERFLOW_URL)
    parser.add_argument("--cookie-jar", type=Path, default=DEFAULT_COOKIE_JAR)
    parser.add_argument("--roles-file", type=Path, default=DEFAULT_ROLES_FILE)
    parser.add_argument("--policies-file", type=Path, default=DEFAULT_POLICIES_FILE)
    parser.add_argument("--role", default="cloudmold-inventory-control-agent")
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--model-name", default="glm-5-2")
    args = parser.parse_args()
    try:
        roles = {role["name"]: role for role in load_roles(args.roles_file.expanduser())}
        policies = load_role_policies(args.policies_file.expanduser())
        if set(policies) != set(roles):
            raise ProvisionError("role policies must match the role contract exactly")
        validate_policy_skills(policies)
        if args.role not in roles:
            raise ProvisionError(f"unknown role: {args.role}")
        if args.role not in policies:
            raise ProvisionError(f"role has no tool policy: {args.role}")
        prompt = args.prompt or DEFAULT_PROMPTS[args.role]
        result = verify(
            args.deerflow_url,
            args.cookie_jar.expanduser(),
            roles[args.role],
            policies[args.role],
            prompt,
            args.model_name,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ProvisionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
