#!/usr/bin/env python3
"""Deterministic CloudMold DeerFlow -> MCP -> Dubbo verification runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
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
REQUIRED_TOOLS = {
    "cloudmold_capability_list",
    "cloudmold_capability_describe",
    "cloudmold_capability_read_invoke",
}
DEERFLOW_LIST_TOOL = "cloudmold-hsf_cloudmold_capability_list"


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
        body={"thread_id": thread_id, "metadata": {"purpose": "cloudmold-hsf-mcp-e2e"}},
        timeout=15,
    )
    if create_status not in {200, 201}:
        raise GateError(f"DeerFlow thread creation returned HTTP {create_status}")

    prompt = (
        "这是一次只读验收。你必须调用 MCP 工具 cloudmold_capability_list，并将 operationType 设置为 READ。"
        "不要调用 shell、文件或浏览器工具。最后只报告 MCP 调用是否成功、READ 能力总数和第一个 capabilityId。"
    )
    body = {
        "assistant_id": "lead_agent",
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "config": {"recursion_limit": 30},
        "context": {
            "model_name": model_name,
            "mode": "flash",
            "thinking_enabled": False,
            "is_plan_mode": False,
            "subagent_enabled": False,
        },
        "stream_mode": ["values"],
    }
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
            if isinstance(message.get("content"), str):
                tool_content = message["content"]

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan", help="print the dependency-ordered acceptance plan")

    verify = commands.add_parser("verify", help="verify MCP protocol, catalog, auth, and write guard")
    common_options(verify)

    invoke = commands.add_parser("invoke-read", help="invoke one governed READ capability")
    common_options(invoke)
    read_options(invoke, required=True)

    agent = commands.add_parser("deerflow-e2e", help="prove DeerFlow/model discovery and MCP invocation")
    common_options(agent)
    deerflow_options(agent)

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
            "DeerFlow model tool discovery and MCP call",
        ],
        "writeBoundary": "durable Skill Task only; direct MCP write forbidden",
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
