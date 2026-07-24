#!/usr/bin/env python3
"""Deterministic CloudMold DeerFlow -> MCP -> Dubbo verification runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener


SCRIPT_PATH = Path(__file__).resolve()
USEFUL_SCRIPTS_ROOT = SCRIPT_PATH.parents[3]
DEFAULT_MCP_URL = "http://127.0.0.1:49090/mcp"
DEFAULT_DEERFLOW_URL = "http://127.0.0.1:2026"
DEFAULT_TOKEN_FILE = USEFUL_SCRIPTS_ROOT / "yml/yudao/data/secrets/cloudmold-mcp-bearer-token"
DEFAULT_COOKIE_JAR = USEFUL_SCRIPTS_ROOT / "yml/deer-flow/runtime/home/.admin-cookie-jar"
DEFAULT_EVIDENCE_ROOT = Path("~/.cloudmold/runs/hsf-mcp").expanduser()
PROTOCOL_VERSION = "2025-11-25"
CORE_TOOLS = {
    "cloudmold_capability_list",
    "cloudmold_capability_describe",
    "cloudmold_capability_read_invoke",
}
SKILL_TASK_TOOLS = {
    "cloudmold_skill_task_submit_r1": {"readOnlyHint": False, "idempotentHint": True},
    "cloudmold_skill_task_get": {"readOnlyHint": True, "idempotentHint": True},
    "cloudmold_skill_task_get_by_request_key": {"readOnlyHint": True, "idempotentHint": True},
    "cloudmold_skill_task_list_steps": {"readOnlyHint": True, "idempotentHint": True},
    "cloudmold_skill_task_retry_r1": {"readOnlyHint": False, "idempotentHint": False},
    "cloudmold_skill_task_submit_commerce_full_chain_r3": {
        "readOnlyHint": False, "idempotentHint": True,
    },
    "cloudmold_skill_task_retry_commerce_full_chain_r3": {
        "readOnlyHint": False, "idempotentHint": False,
    },
}
REQUIRED_TOOLS = CORE_TOOLS | set(SKILL_TASK_TOOLS)
DEERFLOW_LIST_TOOL = "cloudmold-hsf_cloudmold_capability_list"
DEERFLOW_TASK_SUBMIT_TOOL = "cloudmold-hsf_cloudmold_skill_task_submit_r1"
DEERFLOW_TASK_GET_TOOL = "cloudmold-hsf_cloudmold_skill_task_get"
DEERFLOW_R3_SUBMIT_TOOL = (
    "cloudmold-hsf_cloudmold_skill_task_submit_commerce_full_chain_r3"
)
DEERFLOW_R3_ACCEPTANCE_AGENT = "cloudmold-r3-acceptance-agent"
DEERFLOW_R3_ACCEPTANCE_POLICY_SKILL = "cloudmold-r3-acceptance-policy"
R3_SKILL_ID = "skill.cloudmold.commerce.full-chain-hsf.v1"
R3_SKILL_VERSION = "1.2.0"
R3_APPROVAL_CLOCK_SKEW_SECONDS = 120
R3_THREAD_STATE_POLL_INTERVAL_SECONDS = 2
R3_THREAD_STATE_POLL_TIMEOUT_SECONDS = 180
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class GateError(RuntimeError):
    """Raised when an acceptance gate fails."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def generated_run_id() -> str:
    return f"hsf-mcp-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"


def require_run_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,127}", value):
        raise GateError("run-id must contain 3-128 safe characters")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: Any | None = None,
    timeout: int = 15,
) -> tuple[int, Any, Any]:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request_headers = dict(headers or {})
    if data is not None:
        request_headers.setdefault("Content-Type", "application/json")
    request = Request(url, data=data, headers=request_headers, method=method)
    try:
        with build_opener().open(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
            return response.status, response.headers, parse_json_or_text(payload)
    except HTTPError as error:
        payload = error.read().decode("utf-8", errors="replace")
        return error.code, error.headers, parse_json_or_text(payload)
    except URLError as error:
        raise GateError(f"cannot reach {url}: {error.reason}") from error


def parse_json_or_text(payload: str) -> Any:
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return payload


def parse_mcp_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if not isinstance(payload, str):
        raise GateError("MCP response is neither JSON nor SSE")
    data_lines = [line[6:] for line in payload.splitlines() if line.startswith("data: ")]
    if not data_lines:
        raise GateError("MCP SSE response contains no data event")
    parsed = json.loads(data_lines[-1])
    if not isinstance(parsed, dict):
        raise GateError("MCP data event is not a JSON object")
    return parsed


def load_bearer_token(path: Path) -> str:
    try:
        mode = path.stat().st_mode & 0o777
        token = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise GateError(f"cannot read MCP token file: {path}") from error
    if mode & 0o077:
        raise GateError(f"MCP token file must not be group/world accessible: {path}")
    if len(token) < 32:
        raise GateError("MCP bearer token must contain at least 32 characters")
    return token


def load_approval_ref(path: Path) -> str:
    try:
        mode = path.stat().st_mode & 0o777
        reference = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise GateError(f"cannot read approval reference file: {path}") from error
    if mode & 0o077:
        raise GateError(f"approval reference file must not be group/world accessible: {path}")
    if not re.fullmatch(r"cma1:[A-Za-z0-9._-]{8,64}:[0-9]+:[0-9a-fA-F]{64}", reference):
        raise GateError("approval reference has an unsupported format")
    if not approval_ref_is_fresh(reference):
        raise GateError("approval reference has expired")
    return reference


def approval_ref_expiry_epoch(reference: str) -> int:
    parts = reference.split(":", 3)
    if len(parts) != 4:
        raise GateError("approval reference has an unsupported format")
    try:
        return int(parts[2])
    except ValueError as error:
        raise GateError("approval reference has an unsupported format") from error


def approval_ref_is_fresh(
    reference: str,
    *,
    now: datetime | None = None,
    clock_skew_seconds: int = R3_APPROVAL_CLOCK_SKEW_SECONDS,
) -> bool:
    current = now or datetime.now(timezone.utc)
    return int(current.timestamp()) < approval_ref_expiry_epoch(reference) + clock_skew_seconds


def r3_acceptance_agent_request() -> dict[str, Any]:
    return {
        "name": DEERFLOW_R3_ACCEPTANCE_AGENT,
        "display_name": "CloudMold R3 Acceptance",
        "description": "Hidden internal acceptance agent for the fixed approved R3 commerce task.",
        "tool_groups": [],
        "skills": [DEERFLOW_R3_ACCEPTANCE_POLICY_SKILL],
        "soul": (
            "You are a deterministic internal acceptance worker. The caller supplies one exact, "
            "already-approved fixed R3 submission. Call only the permitted fixed R3 submit tool "
            "with the supplied arguments, then query the returned task identifier once. Do not "
            "reinterpret the request, ask business questions, use any other tool, or expose the "
            "approval reference. Tool rejection is a failed acceptance run, never a reason to "
            "broaden scope."
        ),
    }


def comparable_r3_acceptance_agent(agent: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": agent.get("name"),
        "display_name": agent.get("display_name"),
        "description": agent.get("description") or "",
        "tool_groups": agent.get("tool_groups"),
        "skills": agent.get("skills"),
        "soul": (agent.get("soul") or "").strip(),
    }


def ensure_deerflow_r3_acceptance_agent(
    deerflow_url: str,
    headers: dict[str, str],
) -> str:
    desired = r3_acceptance_agent_request()
    desired_comparable = comparable_r3_acceptance_agent(desired)
    agent_url = f"{deerflow_url.rstrip('/')}/api/agents/{DEERFLOW_R3_ACCEPTANCE_AGENT}"
    status, _, current = request_json("GET", agent_url, headers=headers, timeout=15)
    if status == 404:
        status, _, created = request_json(
            "POST",
            f"{deerflow_url.rstrip('/')}/api/agents",
            headers=headers,
            body=desired,
            timeout=15,
        )
        if status != 201 or not isinstance(created, dict):
            raise GateError(f"cannot create DeerFlow R3 acceptance agent: HTTP {status}")
        current = created
    elif status != 200 or not isinstance(current, dict):
        raise GateError(f"cannot inspect DeerFlow R3 acceptance agent: HTTP {status}")

    if comparable_r3_acceptance_agent(current) != desired_comparable:
        update = {key: value for key, value in desired.items() if key != "name"}
        status, _, updated = request_json(
            "PUT",
            agent_url,
            headers=headers,
            body=update,
            timeout=15,
        )
        if status != 200 or not isinstance(updated, dict):
            raise GateError(f"cannot update DeerFlow R3 acceptance agent: HTTP {status}")
        current = updated

    if comparable_r3_acceptance_agent(current) != desired_comparable:
        raise GateError("DeerFlow R3 acceptance agent does not match the fixed policy")
    return DEERFLOW_R3_ACCEPTANCE_AGENT


def mcp_headers(token: str, session_id: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    return headers


def initialize_mcp(mcp_url: str, token: str) -> tuple[str, dict[str, Any]]:
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "cloudmold-hsf-mcp-operator", "version": "1.0.0"},
        },
    }
    status, headers, raw = request_json(
        "POST", mcp_url, headers=mcp_headers(token), body=initialize
    )
    if status != 200:
        raise GateError(f"authenticated MCP initialize returned HTTP {status}")
    response = parse_mcp_payload(raw)
    result = response.get("result")
    if not isinstance(result, dict):
        raise GateError("MCP initialize returned no result")
    session_id = headers.get("Mcp-Session-Id")
    if not session_id:
        raise GateError("MCP initialize returned no session ID")
    notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    notify_status, _, _ = request_json(
        "POST", mcp_url, headers=mcp_headers(token, session_id), body=notification
    )
    if notify_status not in {200, 202}:
        raise GateError(f"MCP initialized notification returned HTTP {notify_status}")
    return session_id, result


def mcp_rpc(
    mcp_url: str,
    token: str,
    session_id: str,
    request_id: int,
    method: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    status, _, raw = request_json(
        "POST",
        mcp_url,
        headers=mcp_headers(token, session_id),
        body={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
    )
    if status != 200:
        raise GateError(f"MCP {method} returned HTTP {status}")
    response = parse_mcp_payload(raw)
    if response.get("error"):
        raise GateError(f"MCP {method} returned a JSON-RPC error")
    result = response.get("result")
    if not isinstance(result, dict):
        raise GateError(f"MCP {method} returned no result")
    return result


def mcp_tool_call(
    mcp_url: str,
    token: str,
    session_id: str,
    request_id: int,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    return mcp_rpc(
        mcp_url,
        token,
        session_id,
        request_id,
        "tools/call",
        {"name": name, "arguments": arguments},
    )


def protocol_verification(mcp_url: str, token: str, run_id: str) -> dict[str, Any]:
    health_url = mcp_url.rsplit("/mcp", 1)[0] + "/health"
    health_status, _, health = request_json("GET", health_url)
    if health_status != 200 or not isinstance(health, dict) or health.get("status") != "UP":
        raise GateError("MCP health gate failed")

    unauthorized_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "unauthorized-check", "version": "1"},
        },
    }
    unauthorized_status, _, _ = request_json(
        "POST",
        mcp_url,
        headers={"Accept": "application/json, text/event-stream"},
        body=unauthorized_body,
    )
    if unauthorized_status != 401:
        raise GateError(f"unauthenticated MCP request returned HTTP {unauthorized_status}, expected 401")

    session_id, initialized = initialize_mcp(mcp_url, token)
    if initialized.get("protocolVersion") != PROTOCOL_VERSION:
        raise GateError("MCP protocol version mismatch")
    tools_result = mcp_rpc(mcp_url, token, session_id, 2, "tools/list", {})
    tools = tools_result.get("tools")
    if not isinstance(tools, list):
        raise GateError("MCP tools/list returned no tools")
    tool_names = {tool.get("name") for tool in tools if isinstance(tool, dict)}
    missing_tools = REQUIRED_TOOLS - tool_names
    if missing_tools:
        raise GateError(f"missing required MCP tools: {sorted(missing_tools)}")
    tools_by_name = {
        str(tool.get("name")): tool for tool in tools
        if isinstance(tool, dict) and isinstance(tool.get("name"), str)
    }
    for name, expected in SKILL_TASK_TOOLS.items():
        annotations = tools_by_name[name].get("annotations")
        if not isinstance(annotations, dict):
            raise GateError(f"Skill Task MCP tool has no annotations: {name}")
        if annotations.get("readOnlyHint") is not expected["readOnlyHint"]:
            raise GateError(f"Skill Task MCP readOnlyHint mismatch: {name}")
        if annotations.get("idempotentHint") is not expected["idempotentHint"]:
            raise GateError(f"Skill Task MCP idempotentHint mismatch: {name}")
        if annotations.get("destructiveHint") is True:
            raise GateError(f"Skill Task MCP tool must not be destructive: {name}")

    extra_tools = [tool for tool in tools if isinstance(tool, dict) and tool.get("name") not in REQUIRED_TOOLS]
    unsafe_extensions = []
    for tool in extra_tools:
        annotations = tool.get("annotations") if isinstance(tool.get("annotations"), dict) else {}
        if annotations.get("readOnlyHint") is not True or annotations.get("destructiveHint") is True:
            unsafe_extensions.append(str(tool.get("name")))
    if unsafe_extensions:
        raise GateError(f"MCP extensions must remain read-only: {sorted(unsafe_extensions)}")

    read_result = mcp_tool_call(
        mcp_url, token, session_id, 3, "cloudmold_capability_list", {"operationType": "READ"}
    )
    write_result = mcp_tool_call(
        mcp_url, token, session_id, 4, "cloudmold_capability_list", {"operationType": "WRITE"}
    )
    read_catalog = require_structured(read_result, "READ capability list")
    write_catalog = require_structured(write_result, "WRITE capability list")
    read_count = positive_count(read_catalog, "READ")
    write_count = positive_count(write_catalog, "WRITE")
    first_read = first_capability_id(read_catalog, "READ")
    first_write = first_capability_id(write_catalog, "WRITE")

    rejection = mcp_tool_call(
        mcp_url,
        token,
        session_id,
        5,
        "cloudmold_capability_read_invoke",
        {
            "capabilityId": first_write,
            "arguments": [],
            "tenantId": 1,
            "operatorId": 1,
            "operatorType": 1,
            "skillId": "skill.cloudmold.platform.hsf-mcp-operator.v1",
            "runId": f"{run_id}-write-rejection",
        },
    )
    rejection_details = require_structured(rejection, "WRITE rejection")
    if rejection.get("isError") is not True or rejection_details.get("errorType") != "SecurityException":
        raise GateError("direct MCP WRITE rejection gate failed")

    server_info = initialized.get("serverInfo") if isinstance(initialized.get("serverInfo"), dict) else {}
    return {
        "status": "SUCCEEDED",
        "checkedAt": utc_now(),
        "health": health,
        "unauthenticatedHttpStatus": unauthorized_status,
        "protocolVersion": initialized.get("protocolVersion"),
        "serverInfo": server_info,
        "requiredToolNames": sorted(REQUIRED_TOOLS),
        "skillTaskToolNames": sorted(SKILL_TASK_TOOLS),
        "allToolNames": sorted(str(name) for name in tool_names),
        "readOnlyExtensionToolNames": sorted(str(tool.get("name")) for tool in extra_tools),
        "readCapabilityCount": read_count,
        "writeCapabilityCount": write_count,
        "totalCapabilityCount": read_count + write_count,
        "firstReadCapabilityId": first_read,
        "writeRejection": {
            "capabilityId": first_write,
            "errorType": rejection_details.get("errorType"),
        },
    }


def require_structured(result: dict[str, Any], label: str) -> dict[str, Any]:
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        raise GateError(f"{label} returned no structured content")
    return structured


def positive_count(catalog: dict[str, Any], label: str) -> int:
    count = catalog.get("count")
    if not isinstance(count, int) or count <= 0:
        raise GateError(f"{label} capability catalog is empty")
    return count


def first_capability_id(catalog: dict[str, Any], label: str) -> str:
    capabilities = catalog.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        raise GateError(f"{label} capability catalog has no entries")
    first = capabilities[0]
    capability_id = first.get("capabilityId") if isinstance(first, dict) else None
    if not isinstance(capability_id, str) or not capability_id:
        raise GateError(f"{label} capability catalog has no first capability ID")
    return capability_id


def parse_arguments_json(value: str) -> list[Any]:
    try:
        arguments = json.loads(value)
    except json.JSONDecodeError as error:
        raise GateError(f"arguments-json is invalid: {error.msg}") from error
    if not isinstance(arguments, list):
        raise GateError("arguments-json must be a JSON array")
    return arguments


def summarize_value(value: Any) -> dict[str, Any]:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    summary: dict[str, Any] = {
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "encodedBytes": len(canonical.encode("utf-8")),
    }
    if isinstance(value, dict):
        summary["keys"] = sorted(str(key) for key in value.keys())
        scalars = {
            str(key): item
            for key, item in value.items()
            if item is None or isinstance(item, (str, int, float, bool))
        }
        summary["scalarPreview"] = dict(list(scalars.items())[:20])
    elif isinstance(value, list):
        summary["itemCount"] = len(value)
    else:
        summary["value"] = value
    return summary


def invoke_business_read(
    mcp_url: str,
    token: str,
    *,
    capability_id: str,
    arguments: list[Any],
    tenant_id: int,
    operator_id: int,
    operator_type: int,
    skill_id: str,
    run_id: str,
) -> dict[str, Any]:
    session_id, _ = initialize_mcp(mcp_url, token)
    response = mcp_tool_call(
        mcp_url,
        token,
        session_id,
        10,
        "cloudmold_capability_read_invoke",
        {
            "capabilityId": capability_id,
            "arguments": arguments,
            "tenantId": tenant_id,
            "operatorId": operator_id,
            "operatorType": operator_type,
            "skillId": skill_id,
            "runId": run_id,
        },
    )
    structured = require_structured(response, "business READ")
    if response.get("isError") is True or structured.get("status") != "SUCCEEDED":
        raise GateError(f"business READ failed: {structured.get('errorType', 'unknown error')}")
    return {
        "status": "SUCCEEDED",
        "checkedAt": utc_now(),
        "capabilityId": capability_id,
        "runId": run_id,
        "resultSummary": summarize_value(structured.get("result")),
    }


def parse_object_json(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise GateError(f"input-json is invalid: {error.msg}") from error
    if not isinstance(parsed, dict):
        raise GateError("input-json must be a JSON object")
    return parsed


def load_object_file(path: Path) -> dict[str, Any]:
    try:
        return parse_object_json(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise GateError(f"cannot read input file: {path}") from error


def canonical_object_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def require_r3_terminal_proof(
    task: dict[str, Any], task_input: dict[str, Any],
) -> dict[str, str]:
    expected = {
        "skillId": R3_SKILL_ID,
        "skillVersion": R3_SKILL_VERSION,
        "riskLevel": "R3",
        "inputSha256": canonical_object_sha256(task_input),
    }
    for field, expected_value in expected.items():
        if task.get(field) != expected_value:
            raise GateError(
                f"R3 full-chain terminal proof has unexpected {field}: {task.get(field)!r}"
            )
    hashes: dict[str, str] = {}
    for field in (
        "definitionSha256", "definitionClosureSha256", "terminalResultSha256",
    ):
        value = task.get(field)
        if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
            raise GateError(f"R3 full-chain terminal proof has no valid {field}")
        hashes[field] = value
    return hashes


def invoke_skill_task_r1(
    mcp_url: str,
    token: str,
    *,
    target_skill_id: str,
    target_skill_version: str,
    client_request_key: str,
    task_input: dict[str, Any],
    tenant_id: int,
    operator_id: int,
    operator_type: int,
    run_id: str,
    timeout: int,
) -> dict[str, Any]:
    session_id, _ = initialize_mcp(mcp_url, token)
    context = {
        "tenantId": tenant_id,
        "operatorId": operator_id,
        "operatorType": operator_type,
        "controlRunId": run_id,
    }
    submitted = mcp_tool_call(
        mcp_url,
        token,
        session_id,
        20,
        "cloudmold_skill_task_submit_r1",
        context | {
            "skillId": target_skill_id,
            "skillVersion": target_skill_version,
            "clientRequestKey": client_request_key,
            "input": task_input,
        },
    )
    submitted_details = require_structured(submitted, "R1 Skill Task submit")
    task = submitted_details.get("result")
    if submitted.get("isError") is True or not isinstance(task, dict):
        raise GateError(f"R1 Skill Task submit failed: {submitted_details.get('message', 'unknown error')}")
    task_id = task.get("taskId")
    if not isinstance(task_id, str) or not task_id:
        raise GateError("R1 Skill Task submit returned no taskId")

    deadline = time.monotonic() + timeout
    request_id = 21
    while True:
        queried = mcp_tool_call(
            mcp_url,
            token,
            session_id,
            request_id,
            "cloudmold_skill_task_get",
            context | {"taskId": task_id},
        )
        queried_details = require_structured(queried, "R1 Skill Task query")
        task = queried_details.get("result")
        if queried.get("isError") is True or not isinstance(task, dict):
            raise GateError(f"R1 Skill Task query failed: {queried_details.get('message', 'unknown error')}")
        status = task.get("status")
        if status == "SUCCEEDED":
            break
        if status == "NEEDS_REVIEW":
            raise GateError(f"R1 Skill Task needs review: {task.get('lastErrorMessage', 'unknown error')}")
        if time.monotonic() >= deadline:
            raise GateError(f"R1 Skill Task did not complete within {timeout}s; last status={status}")
        request_id += 1
        time.sleep(1)

    steps_response = mcp_tool_call(
        mcp_url,
        token,
        session_id,
        request_id + 1,
        "cloudmold_skill_task_list_steps",
        context | {"taskId": task_id},
    )
    steps_details = require_structured(steps_response, "R1 Skill Task steps")
    steps = steps_details.get("result")
    if steps_response.get("isError") is True or not isinstance(steps, list) or not steps:
        raise GateError("R1 Skill Task returned no persisted step evidence")
    if any(not isinstance(step, dict) or step.get("status") != "SUCCEEDED" for step in steps):
        raise GateError("R1 Skill Task has a non-succeeded persisted step")
    return {
        "status": "SUCCEEDED",
        "checkedAt": utc_now(),
        "taskId": task_id,
        "skillId": target_skill_id,
        "skillVersion": target_skill_version,
        "clientRequestKey": client_request_key,
        "taskStatus": task.get("status"),
        "attemptCount": task.get("attemptCount"),
        "version": task.get("version"),
        "inputSha256": task.get("inputSha256"),
        "steps": [
            {
                "stepCode": step.get("stepCode"),
                "capabilityId": step.get("capabilityId"),
                "status": step.get("status"),
                "attemptCount": step.get("attemptCount"),
                "requestSha256": step.get("requestSha256"),
                "resultSha256": step.get("resultSha256"),
            }
            for step in steps
        ],
    }


def await_skill_task(
    mcp_url: str,
    token: str,
    session_id: str,
    context: dict[str, Any],
    task_id: str,
    timeout: int,
    *,
    label: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    deadline = time.monotonic() + timeout
    request_id = 60
    while True:
        queried = mcp_tool_call(
            mcp_url, token, session_id, request_id,
            "cloudmold_skill_task_get", context | {"taskId": task_id})
        queried_details = require_structured(queried, f"{label} query")
        task = queried_details.get("result")
        if queried.get("isError") is True or not isinstance(task, dict):
            raise GateError(f"{label} query failed: {queried_details.get('message', 'unknown error')}")
        status = task.get("status")
        if status == "SUCCEEDED":
            break
        if status == "NEEDS_REVIEW":
            raise GateError(f"{label} needs review: {task.get('lastErrorMessage', 'unknown error')}")
        if time.monotonic() >= deadline:
            raise GateError(f"{label} did not complete within {timeout}s; last status={status}")
        request_id += 1
        time.sleep(2)

    steps_response = mcp_tool_call(
        mcp_url, token, session_id, request_id + 1,
        "cloudmold_skill_task_list_steps", context | {"taskId": task_id})
    steps_details = require_structured(steps_response, f"{label} steps")
    steps = steps_details.get("result")
    if steps_response.get("isError") is True or not isinstance(steps, list) or not steps:
        raise GateError(f"{label} returned no persisted step evidence")
    if any(not isinstance(step, dict) or step.get("status") != "SUCCEEDED" for step in steps):
        raise GateError(f"{label} has a non-succeeded persisted step")
    return task, steps


def invoke_skill_task_r3(
    mcp_url: str,
    token: str,
    *,
    client_run_id: str,
    client_request_key: str,
    task_input: dict[str, Any],
    approval_ref: str,
    tenant_id: int,
    operator_id: int,
    operator_type: int,
    run_id: str,
    timeout: int,
) -> dict[str, Any]:
    session_id, _ = initialize_mcp(mcp_url, token)
    context = {
        "tenantId": tenant_id,
        "operatorId": operator_id,
        "operatorType": operator_type,
        "controlRunId": run_id,
    }
    submitted = mcp_tool_call(
        mcp_url, token, session_id, 50,
        "cloudmold_skill_task_submit_commerce_full_chain_r3",
        context | {
            "clientRunId": client_run_id,
            "clientRequestKey": client_request_key,
            "input": task_input,
            "approvalRef": approval_ref,
        })
    submitted_details = require_structured(submitted, "R3 full-chain submit")
    task = submitted_details.get("result")
    if submitted.get("isError") is True or not isinstance(task, dict):
        raise GateError(f"R3 full-chain submit failed: {submitted_details.get('message', 'unknown error')}")
    task_id = task.get("taskId")
    if not isinstance(task_id, str) or not task_id:
        raise GateError("R3 full-chain submit returned no taskId")
    task, steps = await_skill_task(
        mcp_url, token, session_id, context, task_id, timeout, label="R3 full-chain Skill Task")
    terminal_proof = require_r3_terminal_proof(task, task_input)
    return {
        "status": "SUCCEEDED",
        "checkedAt": utc_now(),
        "taskId": task_id,
        "clientRunId": client_run_id,
        "clientRequestKey": client_request_key,
        "taskStatus": task.get("status"),
        "attemptCount": task.get("attemptCount"),
        "version": task.get("version"),
        "inputSha256": task.get("inputSha256"),
        "approvalRefSha256": hashlib.sha256(approval_ref.encode("utf-8")).hexdigest(),
        "terminalProof": terminal_proof,
        "steps": [
            {
                "stepCode": step.get("stepCode"),
                "status": step.get("status"),
                "attemptCount": step.get("attemptCount"),
                "requestSha256": step.get("requestSha256"),
                "resultSha256": step.get("resultSha256"),
            }
            for step in steps
        ],
    }


def load_cookie_header(cookie_path: Path) -> tuple[str, str]:
    try:
        lines = cookie_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise GateError(f"cannot load DeerFlow cookie jar: {cookie_path}") from error
    cookies: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_"):]
        elif line.startswith("#") or not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) >= 7:
            cookies[fields[5]] = fields[6]
    csrf = cookies.get("csrf_token")
    if not csrf or "access_token" not in cookies:
        raise GateError("DeerFlow administrator cookie jar is incomplete; run deerflowctl bootstrap")
    return "; ".join(f"{name}={value}" for name, value in cookies.items()), csrf


def internal_test_thread_metadata(purpose: str, *, agent_name: str | None = None) -> dict[str, str]:
    """Mark machine-oriented acceptance threads as internal observability data."""
    metadata = {"purpose": purpose, "visibility": "internal_test"}
    if agent_name:
        metadata["agent_name"] = agent_name
    return metadata


def with_internal_test_metadata(
    body: dict[str, Any],
    purpose: str,
    *,
    agent_name: str | None = None,
) -> dict[str, Any]:
    """Repeat test classification on the run request as defense in depth."""
    return {
        **body,
        "metadata": internal_test_thread_metadata(purpose, agent_name=agent_name),
    }


def hidden_control_message(content: str) -> dict[str, Any]:
    """Keep exact tool-control prompts available to the model but out of business chat UI."""
    return {
        "role": "user",
        "content": content,
        "additional_kwargs": {"hide_from_ui": True},
    }


def tool_message_text(message: dict[str, Any]) -> str | None:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    text_blocks = [
        block.get("text") for block in content
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    ]
    return "\n".join(text_blocks) if text_blocks else None


def r3_thread_has_submit_result(messages: list[dict[str, Any]]) -> bool:
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("type") == "tool" and message.get("name") == DEERFLOW_R3_SUBMIT_TOOL:
            return True
    return False


def r3_thread_has_get_call(messages: list[dict[str, Any]]) -> bool:
    for message in messages:
        if not isinstance(message, dict):
            continue
        for tool_call in message.get("tool_calls") or []:
            if isinstance(tool_call, dict) and tool_call.get("name") == DEERFLOW_TASK_GET_TOOL:
                return True
    return False


def r3_thread_has_get_result(messages: list[dict[str, Any]]) -> bool:
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("type") == "tool" and message.get("name") == DEERFLOW_TASK_GET_TOOL:
            return True
    return False


def r3_thread_is_terminal(messages: list[dict[str, Any]]) -> bool:
    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        if message.get("type") in {"ai", "assistant"}:
            return not bool(message.get("tool_calls"))
        if message.get("type") == "tool":
            return False
    return False


def wait_for_deerflow_r3_thread_state(
    deerflow_url: str,
    headers: dict[str, str],
    thread_id: str,
    *,
    initial_state: dict[str, Any] | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + min(timeout_seconds, R3_THREAD_STATE_POLL_TIMEOUT_SECONDS)
    state: dict[str, Any] | None = initial_state if isinstance(initial_state, dict) else None
    state_url = f"{deerflow_url.rstrip('/')}/api/threads/{thread_id}/state"

    while True:
        messages = state.get("messages") if isinstance(state, dict) else None
        if isinstance(messages, list) and (
            (r3_thread_has_submit_result(messages)
             and r3_thread_has_get_call(messages)
             and r3_thread_has_get_result(messages))
            or r3_thread_is_terminal(messages)
        ):
            return state
        if time.monotonic() >= deadline:
            raise GateError(
                "DeerFlow R3 thread state did not persist the fixed submit result within "
                f"{min(timeout_seconds, R3_THREAD_STATE_POLL_TIMEOUT_SECONDS)}s"
            )

        status, _, persisted = request_json("GET", state_url, headers=headers, timeout=15)
        if status in {401, 403}:
            raise GateError(f"cannot poll DeerFlow R3 thread state: HTTP {status}")
        if status == 200 and isinstance(persisted, dict):
            state = persisted.get("values", persisted)
        time.sleep(R3_THREAD_STATE_POLL_INTERVAL_SECONDS)


def deerflow_e2e(
    deerflow_url: str,
    cookie_path: Path,
    model_name: str,
    run_id: str,
    timeout: int,
) -> dict[str, Any]:
    cookie_header, csrf = load_cookie_header(cookie_path)
    headers = {
        "Cookie": cookie_header,
        "X-CSRF-Token": csrf,
        "Content-Type": "application/json",
    }
    thread_id = f"cloudmold-hsf-mcp-{run_id}-{uuid.uuid4().hex[:8]}"
    create_status, _, _ = request_json(
        "POST",
        f"{deerflow_url.rstrip('/')}/api/threads",
        headers=headers,
        body={"thread_id": thread_id,
              "metadata": internal_test_thread_metadata("cloudmold-hsf-mcp-e2e")},
        timeout=15,
    )
    if create_status not in {200, 201}:
        raise GateError(f"DeerFlow thread creation returned HTTP {create_status}")

    prompt = (
        "这是一次只读验收。你必须调用 MCP 工具 cloudmold_capability_list，并将 operationType 设置为 READ。"
        "不要调用 shell、文件或浏览器工具。最后只报告 MCP 调用是否成功、READ 能力总数和第一个 capabilityId。"
    )
    body = with_internal_test_metadata({
        "assistant_id": "lead_agent",
        "input": {"messages": [hidden_control_message(prompt)]},
        "config": {"recursion_limit": 30},
        "context": {
            "model_name": model_name,
            "mode": "flash",
            "thinking_enabled": False,
            "is_plan_mode": False,
            "subagent_enabled": False,
        },
        "stream_mode": ["values"],
    }, "cloudmold-hsf-mcp-e2e")
    wait_status, _, state = request_json(
        "POST",
        f"{deerflow_url.rstrip('/')}/api/threads/{thread_id}/runs/wait",
        headers=headers,
        body=body,
        timeout=timeout,
    )
    if wait_status != 200 or not isinstance(state, dict):
        raise GateError(f"DeerFlow wait run returned HTTP {wait_status}")
    messages = state.get("messages")
    if not isinstance(messages, list):
        raise GateError("DeerFlow final state contains no messages")

    selected_call: dict[str, Any] | None = None
    tool_content: str | None = None
    final_answer = ""
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("type") == "ai" and isinstance(message.get("content"), str):
            final_answer = message["content"]
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if isinstance(tool_call, dict) and tool_call.get("name") == DEERFLOW_LIST_TOOL:
                    selected_call = tool_call
        if message.get("type") == "tool" and message.get("name") == DEERFLOW_LIST_TOOL:
            tool_content = tool_message_text(message)

    if selected_call is None or selected_call.get("args") != {"operationType": "READ"}:
        raise GateError("DeerFlow did not call the CloudMold READ capability-list tool")
    if tool_content is None:
        raise GateError("DeerFlow produced no CloudMold MCP tool result")
    count_match = re.search(r'"count"\s*:\s*(\d+)', tool_content)
    capability_match = re.search(r'"capabilityId"\s*:\s*"([^"]+)"', tool_content)
    if not count_match or int(count_match.group(1)) <= 0 or not capability_match:
        raise GateError("DeerFlow MCP tool result has no capability summary")

    return {
        "status": "SUCCEEDED",
        "checkedAt": utc_now(),
        "threadId": thread_id,
        "modelName": model_name,
        "toolName": DEERFLOW_LIST_TOOL,
        "toolArguments": selected_call.get("args"),
        "readCapabilityCount": int(count_match.group(1)),
        "firstCapabilityId": capability_match.group(1),
        "finalAnswer": final_answer,
    }


def deerflow_task_e2e(
    deerflow_url: str,
    cookie_path: Path,
    model_name: str,
    run_id: str,
    timeout: int,
    *,
    target_skill_id: str,
    target_skill_version: str,
    client_request_key: str,
    task_input: dict[str, Any],
    tenant_id: int,
    operator_id: int,
    operator_type: int,
) -> dict[str, Any]:
    cookie_header, csrf = load_cookie_header(cookie_path)
    headers = {
        "Cookie": cookie_header,
        "X-CSRF-Token": csrf,
        "Content-Type": "application/json",
    }
    thread_id = f"cloudmold-skill-task-{run_id}-{uuid.uuid4().hex[:8]}"
    create_status, _, _ = request_json(
        "POST",
        f"{deerflow_url.rstrip('/')}/api/threads",
        headers=headers,
        body={"thread_id": thread_id,
              "metadata": internal_test_thread_metadata("cloudmold-skill-task-e2e")},
        timeout=15,
    )
    if create_status not in {200, 201}:
        raise GateError(f"DeerFlow thread creation returned HTTP {create_status}")

    submit_arguments = {
        "tenantId": tenant_id,
        "operatorId": operator_id,
        "operatorType": operator_type,
        "controlRunId": run_id,
        "skillId": target_skill_id,
        "skillVersion": target_skill_version,
        "clientRequestKey": client_request_key,
        "input": task_input,
    }
    prompt = (
        "这是一次 CloudMold 持久化任务验收。你必须先调用 MCP 工具 cloudmold_skill_task_submit_r1，"
        f"参数必须严格等于 {json.dumps(submit_arguments, ensure_ascii=False, separators=(',', ':'))}。"
        "从结果读取 taskId，再调用 cloudmold_skill_task_get 查询；若仍为 QUEUED 或 RUNNING 就继续查询，"
        "直到 SUCCEEDED 或 NEEDS_REVIEW。不要调用 shell、文件、浏览器或任何领域 WRITE capability。"
        "最后只报告 taskId、最终状态和 attemptCount。"
    )
    body = with_internal_test_metadata({
        "assistant_id": "lead_agent",
        "input": {"messages": [hidden_control_message(prompt)]},
        "config": {"recursion_limit": 40},
        "context": {
            "model_name": model_name,
            "mode": "flash",
            "thinking_enabled": False,
            "is_plan_mode": False,
            "subagent_enabled": False,
        },
        "stream_mode": ["values"],
    }, "cloudmold-skill-task-e2e")
    wait_status, _, state = request_json(
        "POST",
        f"{deerflow_url.rstrip('/')}/api/threads/{thread_id}/runs/wait",
        headers=headers,
        body=body,
        timeout=timeout,
    )
    if wait_status != 200 or not isinstance(state, dict):
        raise GateError(f"DeerFlow task wait run returned HTTP {wait_status}")
    messages = state.get("messages")
    if not isinstance(messages, list):
        raise GateError("DeerFlow task final state contains no messages")

    submit_call: dict[str, Any] | None = None
    get_calls: list[dict[str, Any]] = []
    submit_content: str | None = None
    get_contents: list[str] = []
    final_answer = ""
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("type") == "ai" and isinstance(message.get("content"), str):
            final_answer = message["content"]
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue
                if tool_call.get("name") == DEERFLOW_TASK_SUBMIT_TOOL:
                    submit_call = tool_call
                if tool_call.get("name") == DEERFLOW_TASK_GET_TOOL:
                    get_calls.append(tool_call)
        if message.get("type") == "tool":
            content = tool_message_text(message)
            if message.get("name") == DEERFLOW_TASK_SUBMIT_TOOL:
                submit_content = content
            if message.get("name") == DEERFLOW_TASK_GET_TOOL and content is not None:
                get_contents.append(content)

    if submit_call is None or submit_call.get("args") != submit_arguments:
        raise GateError("DeerFlow did not submit the exact governed R1 Skill Task")
    if submit_content is None:
        raise GateError("DeerFlow produced no R1 Skill Task submit result")
    task_match = re.search(r'"taskId"\s*:\s*"([^"]+)"', submit_content)
    if not task_match:
        raise GateError("DeerFlow R1 Skill Task submit result has no taskId")
    task_id = task_match.group(1)
    if not get_calls or not get_contents:
        raise GateError("DeerFlow did not query the submitted Skill Task")
    if not any(call.get("args", {}).get("taskId") == task_id for call in get_calls):
        raise GateError("DeerFlow queried a different Skill Task")
    if not any(re.search(r'"status"\s*:\s*"SUCCEEDED"', content) for content in get_contents):
        raise GateError("DeerFlow did not observe the Skill Task reaching SUCCEEDED")

    return {
        "status": "SUCCEEDED",
        "checkedAt": utc_now(),
        "threadId": thread_id,
        "modelName": model_name,
        "submitToolName": DEERFLOW_TASK_SUBMIT_TOOL,
        "queryToolName": DEERFLOW_TASK_GET_TOOL,
        "taskId": task_id,
        "clientRequestKey": client_request_key,
        "queryCount": len(get_calls),
        "finalAnswer": final_answer,
    }


def deerflow_full_chain_r3_e2e(
    deerflow_url: str,
    cookie_path: Path,
    model_name: str,
    deerflow_timeout: int,
    *,
    mcp_url: str,
    token: str,
    run_id: str,
    client_run_id: str,
    client_request_key: str,
    task_input: dict[str, Any],
    approval_ref: str,
    tenant_id: int,
    operator_id: int,
    operator_type: int,
    task_timeout: int,
) -> dict[str, Any]:
    cookie_header, csrf = load_cookie_header(cookie_path)
    headers = {
        "Cookie": cookie_header,
        "X-CSRF-Token": csrf,
        "Content-Type": "application/json",
    }
    assistant_id = ensure_deerflow_r3_acceptance_agent(deerflow_url, headers)
    thread_id = f"cloudmold-r3-full-chain-{run_id}-{uuid.uuid4().hex[:8]}"
    create_status, _, _ = request_json(
        "POST", f"{deerflow_url.rstrip('/')}/api/threads", headers=headers,
        body={"thread_id": thread_id,
              "metadata": internal_test_thread_metadata("cloudmold-r3-full-chain-e2e")},
        timeout=15)
    if create_status not in {200, 201}:
        raise GateError(f"DeerFlow R3 thread creation returned HTTP {create_status}")

    submit_arguments = {
        "tenantId": tenant_id,
        "operatorId": operator_id,
        "operatorType": operator_type,
        "controlRunId": run_id,
        "clientRunId": client_run_id,
        "clientRequestKey": client_request_key,
        "input": task_input,
        "approvalRef": approval_ref,
    }
    prompt = (
        "这是一次已审批的 CloudMold R3 全链路验收。你必须且只能先调用 MCP 工具 "
        "cloudmold_skill_task_submit_commerce_full_chain_r3，参数必须严格等于 "
        f"{json.dumps(submit_arguments, ensure_ascii=False, separators=(',', ':'))}。"
        "从提交结果读取 taskId，再调用 cloudmold_skill_task_get 查询一次持久化状态。"
        "不要直接调用任何领域 WRITE capability，不要调用 shell、文件或浏览器工具。"
        "持久化执行器会异步完成任务；查询一次后只报告 taskId 和当前状态。"
    )
    body = with_internal_test_metadata({
        "assistant_id": assistant_id,
        "input": {"messages": [hidden_control_message(prompt)]},
        "config": {"recursion_limit": 30},
        "context": {
            "model_name": model_name,
            "mode": "flash",
            "thinking_enabled": False,
            "is_plan_mode": False,
            "subagent_enabled": False,
        },
        "stream_mode": ["values"],
    }, "cloudmold-r3-full-chain-e2e")
    wait_status, _, state = request_json(
        "POST", f"{deerflow_url.rstrip('/')}/api/threads/{thread_id}/runs/wait",
        headers=headers, body=body, timeout=deerflow_timeout)
    if wait_status == 504:
        state = wait_for_deerflow_r3_thread_state(
            deerflow_url,
            headers,
            thread_id,
            initial_state=state,
            timeout_seconds=deerflow_timeout,
        )
        wait_status = 200
    if wait_status != 200 or not isinstance(state, dict):
        raise GateError(f"DeerFlow R3 wait run returned HTTP {wait_status}")
    messages = state.get("messages")
    if not isinstance(messages, list):
        raise GateError("DeerFlow R3 final state contains no messages")
    if not r3_thread_has_get_call(messages) or not r3_thread_has_get_result(messages):
        raise GateError("DeerFlow did not persist the fixed R3 task_get query")

    submit_call: dict[str, Any] | None = None
    submit_content: str | None = None
    get_calls: list[dict[str, Any]] = []
    final_answer = ""
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("type") == "ai" and isinstance(message.get("content"), str):
            final_answer = message["content"]
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue
                if tool_call.get("name") == DEERFLOW_R3_SUBMIT_TOOL:
                    submit_call = tool_call
                elif tool_call.get("name") == DEERFLOW_TASK_GET_TOOL:
                    get_calls.append(tool_call)
        if message.get("type") == "tool" and message.get("name") == DEERFLOW_R3_SUBMIT_TOOL:
            submit_content = tool_message_text(message)

    if submit_call is None or submit_call.get("args") != submit_arguments:
        raise GateError("DeerFlow did not submit the exact fixed R3 full-chain Skill Task")
    if submit_content is None:
        raise GateError("DeerFlow produced no R3 full-chain submit result")
    task_match = re.search(r'"taskId"\s*:\s*"([^"]+)"', submit_content)
    if not task_match:
        raise GateError("DeerFlow R3 full-chain submit result has no taskId")
    task_id = task_match.group(1)
    if get_calls and not any(call.get("args", {}).get("taskId") == task_id for call in get_calls):
        raise GateError("DeerFlow queried a different R3 Skill Task")

    session_id, _ = initialize_mcp(mcp_url, token)
    context = {
        "tenantId": tenant_id,
        "operatorId": operator_id,
        "operatorType": operator_type,
        "controlRunId": f"{run_id}-await",
    }
    task, steps = await_skill_task(
        mcp_url, token, session_id, context, task_id, task_timeout,
        label="DeerFlow-submitted R3 full-chain Skill Task")
    terminal_proof = require_r3_terminal_proof(task, task_input)
    return {
        "status": "SUCCEEDED",
        "checkedAt": utc_now(),
        "threadId": thread_id,
        "assistantId": assistant_id,
        "modelName": model_name,
        "submitToolName": DEERFLOW_R3_SUBMIT_TOOL,
        "queryToolName": DEERFLOW_TASK_GET_TOOL,
        "taskId": task_id,
        "clientRunId": client_run_id,
        "clientRequestKey": client_request_key,
        "taskStatus": task.get("status"),
        "attemptCount": task.get("attemptCount"),
        "inputSha256": task.get("inputSha256"),
        "approvalRefSha256": hashlib.sha256(approval_ref.encode("utf-8")).hexdigest(),
        "terminalProof": terminal_proof,
        "deerflowQueryCount": len(get_calls),
        "parentStepCount": len(steps),
        "finalAnswer": final_answer,
    }


def recover_deerflow_full_chain_r3(
    deerflow_url: str,
    cookie_path: Path,
    *,
    thread_id: str,
    mcp_url: str,
    token: str,
    run_id: str,
    client_run_id: str,
    client_request_key: str,
    task_input: dict[str, Any],
    approval_ref: str,
    tenant_id: int,
    operator_id: int,
    operator_type: int,
    task_timeout: int,
) -> dict[str, Any]:
    cookie_header, csrf = load_cookie_header(cookie_path)
    status, _, persisted = request_json(
        "GET", f"{deerflow_url.rstrip('/')}/api/threads/{thread_id}/state",
        headers={"Cookie": cookie_header, "X-CSRF-Token": csrf}, timeout=15)
    if status != 200 or not isinstance(persisted, dict):
        raise GateError(f"cannot recover DeerFlow R3 thread state: HTTP {status}")
    state = persisted.get("values", persisted)
    messages = state.get("messages") if isinstance(state, dict) else None
    if not isinstance(messages, list):
        raise GateError("recovered DeerFlow R3 thread contains no messages")
    if not (r3_thread_has_submit_result(messages) or r3_thread_is_terminal(messages)):
        state = wait_for_deerflow_r3_thread_state(
            deerflow_url,
            {"Cookie": cookie_header, "X-CSRF-Token": csrf},
            thread_id,
            initial_state=state,
            timeout_seconds=task_timeout,
        )
        messages = state.get("messages") if isinstance(state, dict) else None
        if not isinstance(messages, list):
            raise GateError("recovered DeerFlow R3 thread contains no messages")
    if not r3_thread_has_get_call(messages) or not r3_thread_has_get_result(messages):
        raise GateError("recovered DeerFlow did not persist the fixed R3 task_get query")

    expected_arguments = {
        "tenantId": tenant_id,
        "operatorId": operator_id,
        "operatorType": operator_type,
        "controlRunId": run_id,
        "clientRunId": client_run_id,
        "clientRequestKey": client_request_key,
        "input": task_input,
        "approvalRef": approval_ref,
    }
    submit_call: dict[str, Any] | None = None
    submit_content: str | None = None
    get_calls: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        for tool_call in message.get("tool_calls") or []:
            if not isinstance(tool_call, dict):
                continue
            if tool_call.get("name") == DEERFLOW_R3_SUBMIT_TOOL:
                submit_call = tool_call
            elif tool_call.get("name") == DEERFLOW_TASK_GET_TOOL:
                get_calls.append(tool_call)
        if message.get("type") == "tool" and message.get("name") == DEERFLOW_R3_SUBMIT_TOOL:
            submit_content = tool_message_text(message)
    if submit_call is None or submit_call.get("args") != expected_arguments:
        raise GateError("recovered DeerFlow thread did not submit the exact fixed R3 task")
    task_match = re.search(r'"taskId"\s*:\s*"([^"]+)"', submit_content or "")
    if not task_match:
        raise GateError("recovered DeerFlow R3 submit result has no taskId")
    task_id = task_match.group(1)
    if get_calls and not any(call.get("args", {}).get("taskId") == task_id for call in get_calls):
        raise GateError("recovered DeerFlow thread queried a different R3 task")

    session_id, _ = initialize_mcp(mcp_url, token)
    context = {
        "tenantId": tenant_id,
        "operatorId": operator_id,
        "operatorType": operator_type,
        "controlRunId": f"{run_id}-recovery",
    }
    task, steps = await_skill_task(
        mcp_url, token, session_id, context, task_id, task_timeout,
        label="Recovered DeerFlow-submitted R3 full-chain Skill Task")
    terminal_proof = require_r3_terminal_proof(task, task_input)
    return {
        "status": "SUCCEEDED",
        "checkedAt": utc_now(),
        "threadId": thread_id,
        "recoveredFromGatewayTimeout": True,
        "submitToolName": DEERFLOW_R3_SUBMIT_TOOL,
        "queryToolName": DEERFLOW_TASK_GET_TOOL,
        "taskId": task_id,
        "clientRunId": client_run_id,
        "clientRequestKey": client_request_key,
        "taskStatus": task.get("status"),
        "attemptCount": task.get("attemptCount"),
        "inputSha256": task.get("inputSha256"),
        "approvalRefSha256": hashlib.sha256(approval_ref.encode("utf-8")).hexdigest(),
        "terminalProof": terminal_proof,
        "deerflowQueryCount": len(get_calls),
        "parentStepCount": len(steps),
    }


def common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--mcp-url", default=os.getenv("CLOUDMOLD_MCP_URL", DEFAULT_MCP_URL))
    parser.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN_FILE)


def read_options(parser: argparse.ArgumentParser, *, required: bool) -> None:
    parser.add_argument("--capability-id", required=required)
    parser.add_argument("--arguments-json", required=required)
    parser.add_argument("--tenant-id", type=int, default=1)
    parser.add_argument("--operator-id", type=int, default=1)
    parser.add_argument("--operator-type", type=int, default=1)
    parser.add_argument("--skill-id", default="skill.cloudmold.platform.hsf-mcp-operator.v1")


def deerflow_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--deerflow-url", default=os.getenv("DEERFLOW_URL", DEFAULT_DEERFLOW_URL))
    parser.add_argument("--cookie-jar", type=Path, default=DEFAULT_COOKIE_JAR)
    parser.add_argument("--model-name", default=os.getenv("DEER_FLOW_MODEL_NAME", "glm-5-2"))
    parser.add_argument("--timeout", type=int, default=180)


def task_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target-skill-id", default="skill.cloudmold.catalog.inspect-active-sku.v1")
    parser.add_argument("--target-skill-version", default="1.0.0")
    parser.add_argument("--client-request-key", default=None)
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--tenant-id", type=int, default=1)
    parser.add_argument("--operator-id", type=int, default=1)
    parser.add_argument("--operator-type", type=int, default=1)


def r3_task_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--client-run-id", default=None)
    parser.add_argument("--client-request-key", default=None)
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--approval-ref-file", type=Path, required=True)
    parser.add_argument("--tenant-id", type=int, default=1)
    parser.add_argument("--operator-id", type=int, default=1)
    parser.add_argument("--operator-type", type=int, default=1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan", help="print the dependency-ordered acceptance plan")

    verify = commands.add_parser("verify", help="verify MCP protocol, catalog, auth, and write guard")
    common_options(verify)

    invoke = commands.add_parser("invoke-read", help="invoke one governed READ capability")
    common_options(invoke)
    read_options(invoke, required=True)

    task = commands.add_parser("invoke-task-r1", help="submit and await one durable R1 Skill Task")
    common_options(task)
    task_options(task)
    task.add_argument("--timeout", type=int, default=60)

    r3_task = commands.add_parser(
        "invoke-task-r3", help="submit and await the fixed durable R3 commerce full-chain Skill Task")
    common_options(r3_task)
    r3_task_options(r3_task)
    r3_task.add_argument("--timeout", type=int, default=1800)

    agent = commands.add_parser("deerflow-e2e", help="prove DeerFlow/model discovery and MCP invocation")
    common_options(agent)
    deerflow_options(agent)

    agent_task = commands.add_parser(
        "deerflow-task-e2e", help="prove DeerFlow can submit and query a durable R1 Skill Task"
    )
    common_options(agent_task)
    task_options(agent_task)
    deerflow_options(agent_task)

    agent_r3 = commands.add_parser(
        "deerflow-task-r3-e2e",
        help="prove DeerFlow submits the fixed R3 full-chain task and await its durable completion")
    common_options(agent_r3)
    r3_task_options(agent_r3)
    deerflow_options(agent_r3)
    agent_r3.add_argument("--task-timeout", type=int, default=1800)

    recover_r3 = commands.add_parser(
        "recover-deerflow-task-r3",
        help="recover and verify a persisted DeerFlow R3 submission after gateway timeout")
    common_options(recover_r3)
    r3_task_options(recover_r3)
    recover_r3.add_argument("--deerflow-url", default=os.getenv("DEERFLOW_URL", DEFAULT_DEERFLOW_URL))
    recover_r3.add_argument("--cookie-jar", type=Path, default=DEFAULT_COOKIE_JAR)
    recover_r3.add_argument("--thread-id", required=True)
    recover_r3.add_argument("--task-timeout", type=int, default=1800)

    full = commands.add_parser("full", help="run all applicable gates in dependency order")
    common_options(full)
    read_options(full, required=False)
    deerflow_options(full)
    return parser


def require_positive_context(args: argparse.Namespace) -> None:
    for name in ("tenant_id", "operator_id", "operator_type"):
        if getattr(args, name) <= 0:
            raise GateError(f"{name.replace('_', '-')} must be positive")


def print_plan() -> None:
    print(json.dumps({
        "workflow": "DeerFlow -> MCP -> governed Executor -> Dubbo -> Provider",
        "steps": [
            "health and unauthenticated rejection",
            "MCP initialize and exact tool-set verification",
            "READ/WRITE capability catalog audit",
            "direct WRITE rejection",
            "optional signed tenant-aware business READ",
            "optional durable R1 Skill Task submit/query/checkpoint proof",
            "fixed R3 commerce full-chain submit/query/child completion proof",
            "DeerFlow model tool discovery and MCP call",
            "DeerFlow model durable Skill Task submit/query proof",
            "persisted DeerFlow R3 timeout recovery proof",
        ],
        "writeBoundary": (
            "direct domain write forbidden; MCP may submit/retry governed R1 tasks "
            "and the fixed approved R3 commerce full-chain task"
        ),
    }, ensure_ascii=False, indent=2))


def execute(args: argparse.Namespace, run_id: str, run_dir: Path) -> dict[str, Any]:
    token = load_bearer_token(args.token_file.expanduser())
    if args.command == "verify":
        result = protocol_verification(args.mcp_url, token, run_id)
        write_json(run_dir / "mcp-verification.json", result)
        return result
    if args.command == "invoke-read":
        require_positive_context(args)
        result = invoke_business_read(
            args.mcp_url,
            token,
            capability_id=args.capability_id,
            arguments=parse_arguments_json(args.arguments_json),
            tenant_id=args.tenant_id,
            operator_id=args.operator_id,
            operator_type=args.operator_type,
            skill_id=args.skill_id,
            run_id=run_id,
        )
        write_json(run_dir / "capability-read.json", result)
        return result
    if args.command == "invoke-task-r1":
        require_positive_context(args)
        result = invoke_skill_task_r1(
            args.mcp_url,
            token,
            target_skill_id=args.target_skill_id,
            target_skill_version=args.target_skill_version,
            client_request_key=args.client_request_key or f"{run_id}-task",
            task_input=parse_object_json(args.input_json),
            tenant_id=args.tenant_id,
            operator_id=args.operator_id,
            operator_type=args.operator_type,
            run_id=run_id,
            timeout=args.timeout,
        )
        write_json(run_dir / "skill-task-e2e.json", result)
        return result
    if args.command == "invoke-task-r3":
        require_positive_context(args)
        result = invoke_skill_task_r3(
            args.mcp_url,
            token,
            client_run_id=args.client_run_id or f"{run_id}-task",
            client_request_key=args.client_request_key or f"{run_id}-task",
            task_input=load_object_file(args.input_file.expanduser()),
            approval_ref=load_approval_ref(args.approval_ref_file.expanduser()),
            tenant_id=args.tenant_id,
            operator_id=args.operator_id,
            operator_type=args.operator_type,
            run_id=run_id,
            timeout=args.timeout,
        )
        write_json(run_dir / "skill-task-r3-e2e.json", result)
        return result
    if args.command == "deerflow-e2e":
        result = deerflow_e2e(
            args.deerflow_url,
            args.cookie_jar.expanduser(),
            args.model_name,
            run_id,
            args.timeout,
        )
        write_json(run_dir / "deerflow-e2e.json", result)
        return result
    if args.command == "deerflow-task-e2e":
        require_positive_context(args)
        result = deerflow_task_e2e(
            args.deerflow_url,
            args.cookie_jar.expanduser(),
            args.model_name,
            run_id,
            args.timeout,
            target_skill_id=args.target_skill_id,
            target_skill_version=args.target_skill_version,
            client_request_key=args.client_request_key or f"{run_id}-task",
            task_input=parse_object_json(args.input_json),
            tenant_id=args.tenant_id,
            operator_id=args.operator_id,
            operator_type=args.operator_type,
        )
        write_json(run_dir / "deerflow-skill-task-e2e.json", result)
        return result
    if args.command == "deerflow-task-r3-e2e":
        require_positive_context(args)
        result = deerflow_full_chain_r3_e2e(
            args.deerflow_url,
            args.cookie_jar.expanduser(),
            args.model_name,
            args.timeout,
            mcp_url=args.mcp_url,
            token=token,
            run_id=run_id,
            client_run_id=args.client_run_id or f"{run_id}-task",
            client_request_key=args.client_request_key or f"{run_id}-task",
            task_input=load_object_file(args.input_file.expanduser()),
            approval_ref=load_approval_ref(args.approval_ref_file.expanduser()),
            tenant_id=args.tenant_id,
            operator_id=args.operator_id,
            operator_type=args.operator_type,
            task_timeout=args.task_timeout,
        )
        write_json(run_dir / "deerflow-skill-task-r3-e2e.json", result)
        return result
    if args.command == "recover-deerflow-task-r3":
        require_positive_context(args)
        result = recover_deerflow_full_chain_r3(
            args.deerflow_url,
            args.cookie_jar.expanduser(),
            thread_id=args.thread_id,
            mcp_url=args.mcp_url,
            token=token,
            run_id=run_id,
            client_run_id=args.client_run_id or f"{run_id}-task",
            client_request_key=args.client_request_key or f"{run_id}-task",
            task_input=load_object_file(args.input_file.expanduser()),
            approval_ref=load_approval_ref(args.approval_ref_file.expanduser()),
            tenant_id=args.tenant_id,
            operator_id=args.operator_id,
            operator_type=args.operator_type,
            task_timeout=args.task_timeout,
        )
        write_json(run_dir / "deerflow-skill-task-r3-recovered.json", result)
        return result
    if args.command == "full":
        verification = protocol_verification(args.mcp_url, token, run_id)
        write_json(run_dir / "mcp-verification.json", verification)
        business_read = None
        if args.capability_id or args.arguments_json:
            if not args.capability_id or args.arguments_json is None:
                raise GateError("full requires both capability-id and arguments-json when either is supplied")
            require_positive_context(args)
            business_read = invoke_business_read(
                args.mcp_url,
                token,
                capability_id=args.capability_id,
                arguments=parse_arguments_json(args.arguments_json),
                tenant_id=args.tenant_id,
                operator_id=args.operator_id,
                operator_type=args.operator_type,
                skill_id=args.skill_id,
                run_id=run_id,
            )
            write_json(run_dir / "capability-read.json", business_read)
        agent = deerflow_e2e(
            args.deerflow_url,
            args.cookie_jar.expanduser(),
            args.model_name,
            run_id,
            args.timeout,
        )
        write_json(run_dir / "deerflow-e2e.json", agent)
        return {
            "status": "SUCCEEDED",
            "verification": verification,
            "businessRead": business_read,
            "deerflow": agent,
        }
    raise GateError(f"unsupported command: {args.command}")


def main() -> int:
    os.umask(0o077)
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "plan":
        print_plan()
        return 0

    run_id = require_run_id(args.run_id or generated_run_id())
    run_dir = args.evidence_root.expanduser() / run_id
    started_at = utc_now()
    run_record: dict[str, Any] = {
        "schemaVersion": "cloudmold.hsf-mcp-run/v1",
        "runId": run_id,
        "command": args.command,
        "status": "RUNNING",
        "startedAt": started_at,
    }
    write_json(run_dir / "run.json", run_record)
    try:
        result = execute(args, run_id, run_dir)
        run_record.update({"status": "SUCCEEDED", "completedAt": utc_now()})
        write_json(run_dir / "run.json", run_record)
        print(json.dumps({
            "status": "SUCCEEDED",
            "runId": run_id,
            "evidenceDir": str(run_dir),
            "result": result,
        }, ensure_ascii=False, indent=2))
        return 0
    except (GateError, ValueError, json.JSONDecodeError) as error:
        run_record.update({
            "status": "FAILED",
            "completedAt": utc_now(),
            "errorType": type(error).__name__,
            "error": str(error),
        })
        write_json(run_dir / "run.json", run_record)
        print(json.dumps({
            "status": "FAILED",
            "runId": run_id,
            "evidenceDir": str(run_dir),
            "errorType": type(error).__name__,
            "error": str(error),
        }, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
