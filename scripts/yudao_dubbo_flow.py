#!/usr/bin/env python3
"""Execute a declared yudao ERP/WMS/MES workflow only through governed Dubbo capabilities."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[2]
COMPOSE_DIR = WORKSPACE / "useful-scripts/yml/yudao"
SKILLS_DIR = WORKSPACE / "useful-scripts/skills"
PROVIDER_CONTAINER = "yudao-provider"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def lookup(root: Any, path: str) -> Any:
    value = root
    for token in path.split("."):
        if isinstance(value, dict) and token in value:
            value = value[token]
        elif isinstance(value, list) and token.isdigit() and int(token) < len(value):
            value = value[int(token)]
        else:
            raise KeyError(path)
    return value


def resolve(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("$"):
        resolved = lookup(context, value[1:])
        return resolve(resolved, context) if isinstance(resolved, (dict, list)) else resolved
    if isinstance(value, list):
        return [resolve(item, context) for item in value]
    if isinstance(value, dict):
        return {key: resolve(item, context) for key, item in value.items()}
    return value


def parse_result(output: str) -> dict[str, Any]:
    for line in reversed(output.splitlines()):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and candidate.get("status") in {"SUCCEEDED", "FAILED"}:
            return candidate
    raise RuntimeError("Executor did not emit a structured invocation result")


def assert_expected(step: dict[str, Any], result: dict[str, Any], context: dict[str, Any] | None = None) -> None:
    """Fail the workflow when a declared business postcondition is not met."""
    for path, expected in step.get("expect", {}).items():
        if context is not None:
            expected = resolve(expected, context)
        try:
            actual = lookup(result, path)
        except KeyError as exc:
            raise AssertionError(f"step {step['id']} missing expected result path {path}") from exc
        if actual != expected:
            raise AssertionError(
                f"step {step['id']} expected {path}={expected!r}, got {actual!r}"
            )


def validate_authority(inputs: dict[str, Any]) -> None:
    """Require one consistent canonical Merchant/Shop/OWNER authority tuple."""
    authority = inputs.get("authority")
    if not isinstance(authority, dict):
        raise RuntimeError("input authority ledger is required")
    reference = authority.get("reference")
    operator = authority.get("operator")
    if not isinstance(reference, dict) or not isinstance(operator, dict):
        raise RuntimeError("authority must contain reference and operator commands")
    for name, value in {
        "merchantId": reference.get("merchantId"),
        "shopId": reference.get("shopId"),
        "principalId": operator.get("principalId"),
    }.items():
        if not isinstance(value, str) or not value.strip() or value.startswith("internal-"):
            raise RuntimeError(f"authority {name} must be a canonical non-virtual identifier")
    if operator.get("merchantId") != reference.get("merchantId") or operator.get("shopId") != reference.get("shopId"):
        raise RuntimeError("authority operator must belong to the validated Merchant/Shop")
    if operator.get("roleCode") != "OWNER":
        raise RuntimeError("authority operator roleCode must be OWNER")


def require_provider_ready() -> None:
    """Fail before a flow starts instead of letting one-shot clients mutate dependencies."""
    completed = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Health.Status}}", PROVIDER_CONTAINER],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=10,
    )
    if completed.returncode != 0 or completed.stdout.strip() != "healthy":
        detail = completed.stdout.strip() or f"exit {completed.returncode}"
        raise RuntimeError(
            f"Dubbo Provider {PROVIDER_CONTAINER} is not healthy ({detail}); "
            "start the HSF base stack before executing a Skill"
        )


def execute_step(step: dict[str, Any], arguments: list[Any], args: argparse.Namespace) -> dict[str, Any]:
    command = [
        "docker", "compose", "--profile", "agent", "run", "--no-deps", "--rm",
        "cloudmold-agent-executor",
        f"--capability-id={step['capabilityId']}",
        "--arguments-json=" + json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
        f"--tenant-id={args.tenant_id}", f"--operator-id={args.operator_id}",
        f"--operator-type={args.operator_type}", f"--skill-id={args.skill_id}",
        f"--run-id={args.run_id}-{step['id']}",
        f"--write-approved={str(bool(step.get('write')) and args.write_approved).lower()}",
    ]
    try:
        completed = subprocess.run(command, cwd=COMPOSE_DIR, text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, check=False,
                                   timeout=args.step_timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"step {step['id']} timed out after {args.step_timeout_seconds}s while starting or invoking Dubbo"
        ) from exc
    result = parse_result(completed.stdout)
    if completed.returncode != 0 or result.get("status") != "SUCCEEDED":
        raise RuntimeError(f"step {step['id']} failed: {result.get('message', completed.returncode)}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["plan", "execute"])
    parser.add_argument("--scenario", required=True, type=Path)
    parser.add_argument("--input-json", type=Path)
    parser.add_argument("--tenant-id", type=int)
    parser.add_argument("--operator-id", type=int)
    parser.add_argument("--operator-type", type=int)
    parser.add_argument("--skill-id")
    parser.add_argument("--run-id")
    parser.add_argument("--idempotency-key", help="Stable business replay key; defaults to --run-id")
    parser.add_argument("--write-approved", action="store_true")
    parser.add_argument("--step-timeout-seconds", type=int, default=90,
                        help="Bound each one-shot Dubbo executor invocation; default: 90")
    parser.add_argument("--evidence-root", type=Path, default=Path.home() / ".cloudmold/runs/yudao-dubbo")
    args = parser.parse_args()

    scenario_path = args.scenario.resolve()
    if SKILLS_DIR.resolve() not in scenario_path.parents:
        raise RuntimeError("scenario must be checked in below useful-scripts/skills")
    scenario = load_json(scenario_path)
    if args.mode == "plan":
        print(json.dumps({"flowId": scenario["flowId"], "requiredInputs": scenario["requiredInputs"],
                          "steps": [{"id": step["id"], "capabilityId": step["capabilityId"],
                                     "write": step.get("write", False)} for step in scenario["steps"]],
                          "transport": "Dubbo", "uiDependency": "none"}, indent=2, ensure_ascii=False))
        return 0

    for name in ("tenant_id", "operator_id", "operator_type"):
        if not getattr(args, name) or getattr(args, name) <= 0:
            raise RuntimeError(f"--{name.replace('_', '-')} must be positive")
    if args.step_timeout_seconds <= 0:
        raise RuntimeError("--step-timeout-seconds must be positive")
    if not args.skill_id or not args.run_id or not args.input_json:
        raise RuntimeError("execute requires --input-json, --skill-id and --run-id")
    if any(step.get("write") for step in scenario["steps"]) and not args.write_approved:
        raise RuntimeError("workflow contains writes; pass --write-approved for this exact local/test run")
    inputs = load_json(args.input_json)
    validate_authority(inputs)
    require_provider_ready()
    idempotency_key = args.idempotency_key or args.run_id
    if isinstance(inputs.get("command"), dict) and not inputs["command"].get("idempotencyKey"):
        inputs["command"]["idempotencyKey"] = f"{idempotency_key}-create"
    missing = [name for name in scenario["requiredInputs"] if name not in inputs or inputs[name] in (None, "", [])]
    if missing:
        raise RuntimeError("missing required input ledger keys: " + ", ".join(missing))

    run_dir = args.evidence_root / args.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    context: dict[str, Any] = {"input": inputs, "run": {"id": args.run_id},
                               "idempotency": {"key": idempotency_key}, "steps": {}}
    ledger: dict[str, Any] = {"schemaVersion": "cloudmold.yudao-dubbo-flow/v1",
                              "flowId": scenario["flowId"], "skillId": args.skill_id,
                              "runId": args.run_id, "idempotencyKey": idempotency_key,
                              "startedAt": now(), "status": "RUNNING", "steps": []}
    try:
        for step in scenario["steps"]:
            started = now()
            result = execute_step(step, resolve(step.get("arguments", []), context), args)
            assert_expected(step, result, context)
            context["steps"][step["id"]] = result
            ledger["steps"].append({"id": step["id"], "capabilityId": step["capabilityId"],
                                    "status": "SUCCEEDED", "startedAt": started, "finishedAt": now(),
                                    "result": result.get("result")})
        ledger["status"] = "SUCCEEDED"
        return_code = 0
    except KeyboardInterrupt as exc:
        ledger["status"] = "ABORTED"
        ledger["error"] = {"type": type(exc).__name__, "message": "workflow interrupted"}
        return_code = 130
    except Exception as exc:
        ledger["status"] = "FAILED"
        ledger["error"] = {"type": type(exc).__name__, "message": str(exc)}
        return_code = 1
    finally:
        ledger["finishedAt"] = now()
        ledger_path = run_dir / "run.json"
        ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        digest = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
        (run_dir / "evidence-manifest.sha256").write_text(f"{digest}  run.json\n", encoding="utf-8")
        print(json.dumps(ledger, indent=2, ensure_ascii=False))
    return return_code


if __name__ == "__main__":
    sys.exit(main())
