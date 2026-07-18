#!/usr/bin/env python3
"""Deploy and verify the local CloudMold governed Dubbo capability plane."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
WORKSPACE = SKILL_DIR.parents[2]
BACKEND = WORKSPACE / "yudao-cloud"
COMPOSE_DIR = WORKSPACE / "useful-scripts" / "yml" / "yudao"
DEFAULT_NACOS = "http://127.0.0.1:8848"
GOVERNED_SERVICE_COUNT = 85
YUDAO_PROVIDER_SERVICE_COUNT = 83
HESSIAN_COMPATIBILITY_ARGS = [
    "-Ddubbo.application.serialize-check-status=STRICT",
    "-Ddubbo.application.check-serializable=false",
    "-Ddubbo.hessian.allowNonSerializable=true",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_secret_file() -> Path:
    path = Path(os.environ.get("CLOUDMOLD_RPC_SECRET_FILE",
                               COMPOSE_DIR / "data/secrets/cloudmold-rpc-shared-secret"))
    if not path.is_file() or path.stat().st_size < 32:
        raise RuntimeError(f"RPC secret file must exist and contain at least 32 bytes: {path}")
    return path


class Evidence:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.directory = Path.home() / ".cloudmold" / "runs" / "dubbo" / run_id
        self.directory.mkdir(parents=True, exist_ok=True)
        self.commands = self.directory / "commands.jsonl"
        self.started_at = utc_now()

    def record(self, name: str, command: list[str], status: str, returncode: int | None = None) -> None:
        safe_command = ["<redacted>" if "secret" in part.lower() else part for part in command]
        with self.commands.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"time": utc_now(), "name": name, "command": safe_command,
                                     "status": status, "returncode": returncode}, ensure_ascii=False) + "\n")

    def finish(self, status: str, details: dict | None = None) -> None:
        payload = {"schemaVersion": "cloudmold.dubbo-run/v1", "runId": self.run_id,
                   "status": status, "startedAt": self.started_at, "finishedAt": utc_now(),
                   "workspace": str(WORKSPACE)}
        if details:
            payload.update(details)
        (self.directory / "run.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                                                   encoding="utf-8")


def run_checked(evidence: Evidence, name: str, command: list[str], cwd: Path, env: dict | None = None) -> None:
    evidence.record(name, command, "STARTED")
    result = subprocess.run(command, cwd=cwd, env=env, check=False)
    evidence.record(name, command, "SUCCEEDED" if result.returncode == 0 else "FAILED", result.returncode)
    if result.returncode != 0:
        raise RuntimeError(f"{name} failed with exit code {result.returncode}")


def get_json(url: str, timeout: float = 5.0) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_nacos(base_url: str, timeout: int) -> dict:
    deadline = time.monotonic() + timeout
    url = base_url.rstrip("/") + "/nacos/v1/console/health/liveness"
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(url, headers={"Accept": "application/json, text/plain"})
            with urllib.request.urlopen(request, timeout=5.0) as response:
                body = response.read().decode("utf-8").strip()
            if body.upper() == "OK":
                return {"status": "UP", "response": body}
            result = json.loads(body)
            if str(result.get("status", "")).upper() == "UP":
                return result
            last_error = body
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"Nacos did not become live within {timeout}s: {last_error}")


def registered_services(base_url: str) -> dict:
    query = urllib.parse.urlencode({"pageNo": 1, "pageSize": 1000, "groupName": "CLOUDMOLD_DUBBO"})
    return get_json(base_url.rstrip("/") + "/nacos/v1/ns/service/list?" + query)


def deploy_registry(args: argparse.Namespace, evidence: Evidence) -> dict:
    run_checked(evidence, "deploy-registry", ["docker", "compose", "up", "-d", "yudao-nacos"], COMPOSE_DIR)
    return wait_nacos(args.nacos_url, args.timeout)


def build(evidence: Evidence) -> None:
    run_checked(evidence, "install-thin-runtime-dependencies",
                ["mvn", "-pl", "yudao-server,cloudmold-agent-executor,cloudmold-module-skill-task/cloudmold-module-skill-task-server", "-am", "-DskipTests",
                 "-Dspring-boot.repackage.skip=true", "clean", "install"],
                BACKEND)
    run_checked(evidence, "package-provider-and-executor-entrypoints",
                ["mvn", "-pl", "yudao-server,cloudmold-agent-executor,cloudmold-module-skill-task/cloudmold-module-skill-task-server", "-DskipTests", "package"], BACKEND)
    run_checked(evidence, "test-rpc-contracts",
                ["mvn", "-pl", "cloudmold-rpc,cloudmold-agent-executor,cloudmold-module-skill-task/cloudmold-module-skill-task-server", "-am",
                 "-Dspring-boot.repackage.skip=true", "test"], BACKEND)
    require_secret_file()
    run_checked(evidence, "build-compose-capability-plane",
                ["docker", "compose", "--profile", "agent", "build",
                 "yudao-dubbo-admin", "yudao-provider", "cloudmold-skill-task-executor",
                 "cloudmold-agent-executor"], COMPOSE_DIR)


def port_open(port: int) -> bool:
    with socket.socket() as connection:
        connection.settimeout(0.5)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def start_provider(args: argparse.Namespace, evidence: Evidence) -> dict:
    require_secret_file()
    provider_inspect = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Status}}", "yudao-provider"],
        text=True, capture_output=True, check=False)
    compose_provider_running = provider_inspect.returncode == 0 and provider_inspect.stdout.strip() == "running"
    if (port_open(20880) or port_open(48080)) and not compose_provider_running:
        raise RuntimeError("Provider port 20880 or 48080 is already in use; stop the exact legacy host process first")
    command = ["docker", "compose", "--profile", "agent", "up", "-d",
               "yudao-dubbo-admin", "yudao-provider", "cloudmold-skill-task-executor"]
    run_checked(evidence, "start-control-and-data-plane", command, COMPOSE_DIR)
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        inspect = subprocess.run(["docker", "inspect", "--format", "{{.State.Health.Status}}",
                                  "yudao-provider"], text=True, capture_output=True, check=False)
        admin = subprocess.run(["docker", "inspect", "--format", "{{.State.Health.Status}}",
                                "yudao-dubbo-admin"], text=True, capture_output=True, check=False)
        task = subprocess.run(["docker", "inspect", "--format", "{{.State.Health.Status}}",
                               "cloudmold-skill-task-executor"], text=True, capture_output=True, check=False)
        logs = subprocess.run(["docker", "logs", "--tail", "400", "yudao-provider"],
                              text=True, capture_output=True, check=False)
        task_logs = subprocess.run(["docker", "logs", "--tail", "200", "cloudmold-skill-task-executor"],
                                   text=True, capture_output=True, check=False)
        expected = f"Exported {YUDAO_PROVIDER_SERVICE_COUNT} governed CloudMold Dubbo services"
        task_expected = "Exported 2 governed CloudMold Dubbo services"
        if (inspect.stdout.strip() == "healthy" and admin.stdout.strip() == "healthy"
                and task.stdout.strip() == "healthy" and expected in logs.stdout + logs.stderr
                and task_expected in task_logs.stdout + task_logs.stderr):
            return {"providerContainer": "yudao-provider", "adminContainer": "yudao-dubbo-admin",
                    "taskExecutorContainer": "cloudmold-skill-task-executor",
                    "adminUrl": "http://127.0.0.1:38080/admin/",
                    "providerServices": YUDAO_PROVIDER_SERVICE_COUNT, "taskServices": 2,
                    "exportedServices": GOVERNED_SERVICE_COUNT}
        time.sleep(2)
    raise RuntimeError(f"Compose capability plane did not become healthy with {YUDAO_PROVIDER_SERVICE_COUNT} "
                       "Yudao Provider services")


def verify(args: argparse.Namespace, evidence: Evidence) -> dict:
    health = wait_nacos(args.nacos_url, args.timeout)
    services = registered_services(args.nacos_url)
    names = services.get("doms", [])
    providers = [name for name in names if name.startswith("providers:")]
    count = len(providers)
    result = {"nacos": health, "registryGroup": "CLOUDMOLD_DUBBO", "registeredProviders": count,
              "registeredEntries": int(services.get("count", len(names))),
              "minimumServices": args.minimum_services, "verifiedAt": utc_now()}
    (evidence.directory / "verification.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if count < args.minimum_services:
        raise RuntimeError(f"Expected at least {args.minimum_services} registered services but found {count}")
    return result


def executor_jar() -> Path:
    return BACKEND / "cloudmold-agent-executor" / "target" / "cloudmold-agent-executor.jar"


def run_executor(args: argparse.Namespace, evidence: Evidence, list_only: bool) -> None:
    require_secret_file()
    command = ["docker", "compose", "--profile", "agent", "run", "--no-deps", "--rm",
               "cloudmold-agent-executor"]
    if list_only:
        command.append("--list-capabilities")
    else:
        command.extend([f"--capability-id={args.capability_id}", f"--arguments-json={args.arguments_json}",
                        f"--tenant-id={args.tenant_id}", f"--operator-id={args.operator_id}",
                        f"--operator-type={args.operator_type}", f"--skill-id={args.skill_id}",
                        f"--run-id={args.run_id}", f"--write-approved={str(args.write_approved).lower()}"])
    action = "list-capabilities" if list_only else "invoke-capability"
    evidence.record(action, command, "STARTED")
    result = subprocess.run(command, cwd=COMPOSE_DIR, env=os.environ.copy(), check=False,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(result.stdout, end="")
    (evidence.directory / "executor.log").write_text(result.stdout, encoding="utf-8")
    payload = None
    for line in reversed(result.stdout.splitlines()):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (list_only and isinstance(candidate, list)) or (
                not list_only and isinstance(candidate, dict) and "status" in candidate):
            payload = candidate
            break
    succeeded = result.returncode == 0 and payload is not None
    if not list_only:
        succeeded = succeeded and payload.get("status") == "SUCCEEDED"
    evidence.record(action, command, "SUCCEEDED" if succeeded else "FAILED", result.returncode)
    if not succeeded:
        raise RuntimeError(f"{action} did not produce a successful structured result "
                           f"(exit code {result.returncode})")
    output_name = "capabilities.json" if list_only else "capability-result.json"
    (evidence.directory / output_name).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("mode", choices=["plan", "deploy-registry", "build", "start-provider", "status",
                                         "verify", "capabilities", "invoke", "full"])
    result.add_argument("--run-id", default=f"dubbo-{int(time.time())}")
    result.add_argument("--nacos-url", default=DEFAULT_NACOS)
    result.add_argument("--timeout", type=int, default=180)
    result.add_argument("--minimum-services", type=int, default=GOVERNED_SERVICE_COUNT)
    result.add_argument("--capability-id")
    result.add_argument("--arguments-json", default="[]")
    result.add_argument("--tenant-id", type=int)
    result.add_argument("--operator-id", type=int)
    result.add_argument("--operator-type", type=int)
    result.add_argument("--skill-id")
    result.add_argument("--write-approved", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    evidence = Evidence(args.run_id)
    try:
        if args.mode == "plan":
            print(json.dumps({"steps": ["deploy-registry", "build", "start-provider", "verify",
                                               "signed read-only invoke"],
                              "writePolicy": "deny unless --write-approved", "evidence": str(evidence.directory)},
                             indent=2))
        elif args.mode == "deploy-registry":
            print(json.dumps(deploy_registry(args, evidence), indent=2))
        elif args.mode == "build":
            build(evidence)
        elif args.mode == "start-provider":
            print(json.dumps(start_provider(args, evidence), indent=2))
        elif args.mode == "status":
            print(json.dumps({"nacos": wait_nacos(args.nacos_url, args.timeout),
                              "services": registered_services(args.nacos_url)}, indent=2))
        elif args.mode == "verify":
            print(json.dumps(verify(args, evidence), indent=2))
        elif args.mode == "capabilities":
            run_executor(args, evidence, True)
        elif args.mode == "invoke":
            required = [args.capability_id, args.tenant_id, args.operator_id, args.operator_type, args.skill_id]
            if any(value in (None, "") for value in required):
                raise RuntimeError("invoke requires capability, tenant, operator, operator-type, and skill IDs")
            run_executor(args, evidence, False)
        elif args.mode == "full":
            deploy_registry(args, evidence)
            build(evidence)
            start_provider(args, evidence)
            print(json.dumps(verify(args, evidence), indent=2))
        evidence.finish("SUCCEEDED")
        return 0
    except Exception as exc:
        evidence.finish("FAILED", {"error": str(exc)})
        print(json.dumps({"status": "FAILED", "error": str(exc), "evidence": str(evidence.directory)},
                         ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
