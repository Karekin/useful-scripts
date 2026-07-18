#!/usr/bin/env python3
"""Route declared internal operations to governed Dubbo capabilities, never HTTP."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any
import urllib.parse
import uuid


WORKSPACE = Path(os.getenv(
    "CLOUDMOLD_WORKSPACE", "/Users/karekin/Downloads/coding/project/CloudMold"
)).expanduser().resolve()
COMPOSE_DIR = WORKSPACE / "useful-scripts/yml/yudao"
DEFAULT_REGISTRY = WORKSPACE / "useful-scripts/skills/registries/internal-transport-capabilities.json"
PROVIDER_CONTAINER = "yudao-provider"


class DubboTransportError(RuntimeError):
    pass


def _load_registry(path: Path) -> dict[str, Any]:
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DubboTransportError(f"cannot load Dubbo transport registry {path}: {exc}") from exc
    if registry.get("schema_version") != "cloudmold.internal-transport/v1":
        raise DubboTransportError("unsupported Dubbo transport registry schema")
    return registry


def _structured_result(output: str) -> dict[str, Any]:
    for line in reversed(output.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("status") in {"SUCCEEDED", "FAILED"}:
            return value
    raise DubboTransportError("Agent Executor did not emit a structured result")


class DubboClient:
    """A small compatibility surface for legacy runners with a pure Dubbo data path."""

    def __init__(self, tenant: int, timeout: int,
                 registry_path: str | Path | None = None):
        if tenant <= 0:
            raise DubboTransportError("tenant must be positive")
        self.tenant = tenant
        self.timeout = timeout
        self.registry_path = Path(registry_path or os.getenv(
            "CLOUDMOLD_DUBBO_TRANSPORT_REGISTRY", str(DEFAULT_REGISTRY))).expanduser().resolve()
        self.registry = _load_registry(self.registry_path)
        self.routes: dict[str, dict[str, Any]] = self.registry["routes"]
        self.operator_id = int(os.getenv("CLOUDMOLD_OPERATOR_ID", "1"))
        self.operator_type = int(os.getenv("CLOUDMOLD_OPERATOR_TYPE", "1"))
        self.skill_id = os.getenv("CLOUDMOLD_SKILL_ID", "skill.cloudmold.erp.full-chain-hsf.v1")
        trace_file = os.getenv("CLOUDMOLD_HSF_TRACE_FILE")
        self.trace_file = Path(trace_file).expanduser().resolve() if trace_file else None

    def available_paths(self) -> dict[str, dict[str, dict]]:
        paths: dict[str, dict[str, dict]] = {}
        for route_key, contract in self.routes.items():
            method, path = route_key.split(" ", 1)
            paths.setdefault(path, {})[method.lower()] = {
                "x-cloudmold-capability-id": contract["capability_id"],
                "x-cloudmold-transport": "dubbo",
            }
        return paths

    def request(self, method: str, path: str, payload: dict | None = None) -> Any:
        parsed = urllib.parse.urlsplit(path)
        key = f"{method.upper()} {parsed.path}"
        contract = self.routes.get(key)
        if contract is None:
            raise DubboTransportError(f"no governed Dubbo capability mapped for {key}")
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        arguments = [self._argument(spec, payload, query) for spec in contract.get("arguments", [])]
        invocation_id = "rpc-" + uuid.uuid4().hex[:16]
        run_id = os.getenv("CLOUDMOLD_HSF_RUN_ID", invocation_id)
        self._require_provider_ready()
        command = [
            "docker", "compose", "--profile", "agent", "run", "--no-deps", "--rm",
            "cloudmold-agent-executor",
            f"--capability-id={contract['capability_id']}",
            "--arguments-json=" + json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
            f"--tenant-id={self.tenant}",
            f"--operator-id={self.operator_id}",
            f"--operator-type={self.operator_type}",
            f"--skill-id={self.skill_id}",
            f"--run-id={run_id}",
            f"--write-approved={str(bool(contract.get('write'))).lower()}",
        ]
        started = time.monotonic()
        completed = subprocess.run(
            command, cwd=COMPOSE_DIR, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=max(self.timeout + 20, 30), check=False)
        result = _structured_result(completed.stdout)
        self._append_trace({
            "schema_version": "cloudmold.hsf-invocation/v1",
            "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            "transport": "dubbo",
            "protocol": "dubbo",
            "http_used": False,
            "run_id": run_id,
            "invocation_id": invocation_id,
            "tenant_id": self.tenant,
            "skill_id": self.skill_id,
            "route_alias": key,
            "capability_id": contract["capability_id"],
            "operation_type": "WRITE" if contract.get("write") else "READ",
            "arguments_sha256": hashlib.sha256(
                json.dumps(arguments, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "duration_ms": round((time.monotonic() - started) * 1000),
            "executor_exit_code": completed.returncode,
            "status": result.get("status"),
        })
        if completed.returncode != 0 or result.get("status") != "SUCCEEDED":
            raise DubboTransportError(
                f"Dubbo capability {contract['capability_id']} rejected {key}: "
                f"{result.get('message', completed.returncode)}")
        value = result.get("result")
        if isinstance(value, dict):
            value = dict(value)
            for source_name, alias_name in contract.get("result_aliases", {}).items():
                if source_name in value and alias_name not in value:
                    value[alias_name] = value[source_name]
        return value

    @staticmethod
    def _require_provider_ready() -> None:
        completed = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", PROVIDER_CONTAINER],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10,
            check=False,
        )
        if completed.returncode != 0 or completed.stdout.strip() != "healthy":
            detail = completed.stdout.strip() or f"exit {completed.returncode}"
            raise DubboTransportError(
                f"Dubbo Provider {PROVIDER_CONTAINER} is not healthy ({detail}); "
                "start the HSF base stack before invoking capabilities"
            )

    def _append_trace(self, record: dict[str, Any]) -> None:
        if self.trace_file is None:
            return
        self.trace_file.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    @staticmethod
    def _argument(spec: str, payload: dict | None,
                  query: dict[str, list[str]]) -> Any:
        if spec == "payload":
            if payload is None:
                raise DubboTransportError("mapped capability requires a payload")
            return payload
        if spec == "now":
            return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        if spec.startswith("query:"):
            name = spec.split(":", 1)[1]
            values = query.get(name)
            if not values or values[0] == "":
                raise DubboTransportError(f"mapped capability requires query parameter {name}")
            return values[0]
        raise DubboTransportError(f"unsupported Dubbo argument binding: {spec}")
