#!/usr/bin/env python3
"""Governed runner for UI, Skill, and lakehouse coverage evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Step:
    step_id: str
    command: list[str]
    cwd: Path
    blocking: bool = True


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def python_runtime() -> str:
    preferred = Path("/opt/anaconda3/envs/agentmesh/bin/python3")
    return str(preferred) if preferred.exists() else sys.executable


def steps(args: argparse.Namespace, run_dir: Path) -> list[Step]:
    workspace = args.workspace.resolve()
    ui = workspace / "yudao-ui-admin-vben"
    skill_dir = Path(__file__).resolve().parent.parent
    erp_skill = Path(
        "/Users/karekin/Library/Mobile Documents/iCloud~md~obsidian/Documents/project/Agent Skills/cloudmold-erp-operator"
    )
    lakehouse = workspace / "useful-scripts/yml/yshopping-lakehouse"
    runtime = run_dir / "runtime.json"
    py = python_runtime()
    return [
        Step(
            "qa.skill_tests",
            [py, "-m", "unittest", "discover", "-s", "tests", "-v"],
            skill_dir,
        ),
        Step("ui.unit", ["pnpm", "test:unit"], ui),
        Step("ui.typecheck", ["pnpm", "--filter", "@vben/web-antd", "typecheck"], ui),
        Step("ui.lint", ["pnpm", "lint"], ui, blocking=False),
        Step("ui.build", ["pnpm", "build:antd"], ui),
        Step(
            "ui.runtime_coverage",
            [
                "node",
                str(skill_dir / "scripts/ui_runtime_coverage.mjs"),
                "--ui-root",
                str(ui),
                "--base-url",
                args.base_url,
                "--tenant-id",
                str(args.tenant_id),
                "--scenario",
                str(skill_dir / "references/scenarios/business-ui-flow-coverage-v1.json"),
                "--output",
                str(runtime),
            ],
            workspace,
        ),
        Step(
            "coverage.static_audit",
            [
                py,
                str(skill_dir / "scripts/flow_coverage_audit.py"),
                "--workspace",
                str(workspace),
                "--runtime-report",
                str(runtime),
                "--output-dir",
                str(run_dir / "static"),
            ],
            workspace,
        ),
        Step(
            "coverage.hsf_audit",
            [
                py,
                str(skill_dir / "scripts/hsf_coverage_audit.py"),
                "--workspace",
                str(workspace),
                "--output-dir",
                str(run_dir / "static"),
            ],
            workspace,
        ),
        *(
            [
                Step(
                    "canonical.evidence_gate",
                    [
                        py,
                        str(skill_dir / "scripts/canonical_evidence_gate.py"),
                        "--run-id",
                        args.canonical_run_id,
                        "--output",
                        str(run_dir / "canonical-evidence.json"),
                    ],
                    workspace,
                )
            ]
            if args.canonical_run_id
            else []
        ),
        Step("skill.erp_operator_tests", [py, "-m", "pytest", "-q"], erp_skill),
        Step("lakehouse.python_tests", [py, "-m", "pytest", "tests/python", "-q"], lakehouse),
    ]


def redact_command(command: list[str]) -> list[str]:
    return ["<redacted>" if "password" in item.lower() or "token" in item.lower() else item for item in command]


def write_hash_manifest(run_dir: Path) -> None:
    rows = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path.name == "evidence-manifest.sha256":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(f"{digest}  {path.relative_to(run_dir).as_posix()}")
    (run_dir / "evidence-manifest.sha256").write_text("\n".join(rows) + "\n", encoding="utf-8")


def execute(args: argparse.Namespace) -> int:
    if not args.run_id:
        raise SystemExit("--run-id is required for execute")
    if not os.environ.get("CLOUDMOLD_QA_USERNAME") or not os.environ.get("CLOUDMOLD_QA_PASSWORD"):
        raise SystemExit("CLOUDMOLD_QA_USERNAME and CLOUDMOLD_QA_PASSWORD are required")

    run_dir = (args.output_root.expanduser() / args.run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    ledger = {
        "schema_version": "cloudmold.qa-run/v1",
        "run_id": args.run_id,
        "status": "RUNNING",
        "started_at": now(),
        "environment": args.environment,
        "tenant_id": args.tenant_id,
        "base_url": args.base_url,
        "read_only_browser": True,
        "steps": [],
    }
    (run_dir / "run.json").write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    command_log = run_dir / "commands.jsonl"
    hard_failure = False

    for step in steps(args, run_dir):
        if hard_failure:
            ledger["steps"].append({"step_id": step.step_id, "status": "SKIPPED_UPSTREAM_FAILURE"})
            continue
        started = now()
        result = subprocess.run(
            step.command,
            cwd=step.cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
            check=False,
        )
        output_path = run_dir / f"{step.step_id.replace('.', '-')}.log"
        output_path.write_text(result.stdout, encoding="utf-8")
        row = {
            "step_id": step.step_id,
            "command": redact_command(step.command),
            "cwd": str(step.cwd),
            "started_at": started,
            "finished_at": now(),
            "exit_code": result.returncode,
            "blocking": step.blocking,
            "status": "SUCCEEDED" if result.returncode == 0 else "FAILED",
            "log": output_path.name,
        }
        ledger["steps"].append(row)
        with command_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        if result.returncode and step.blocking:
            hard_failure = True

    failures = [row for row in ledger["steps"] if row.get("status") == "FAILED"]
    ledger["status"] = "FAILED" if hard_failure else ("SUCCEEDED_WITH_WARNINGS" if failures else "SUCCEEDED")
    ledger["finished_at"] = now()
    ledger["failed_steps"] = [row["step_id"] for row in failures]
    (run_dir / "run.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "test-results.json").write_text(
        json.dumps({"status": ledger["status"], "steps": ledger["steps"]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_hash_manifest(run_dir)
    print(json.dumps({"run_id": args.run_id, "status": ledger["status"], "run_dir": str(run_dir)}))
    return 1 if hard_failure else 0


def plan(args: argparse.Namespace) -> int:
    preview_dir = args.output_root.expanduser() / (args.run_id or "<run-id>")
    payload = {
        "mode": "plan",
        "writes_business_data": False,
        "run_dir": str(preview_dir),
        "steps": [
            {
                "step_id": step.step_id,
                "command": redact_command(step.command),
                "cwd": str(step.cwd),
                "blocking": step.blocking,
            }
            for step in steps(args, preview_dir)
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("plan", "execute"))
    parser.add_argument(
        "--workspace", type=Path, default=Path("/Users/karekin/Downloads/coding/project/CloudMold")
    )
    parser.add_argument("--run-id")
    parser.add_argument("--base-url", default="http://127.0.0.1:5666")
    parser.add_argument("--tenant-id", type=int, default=1)
    parser.add_argument("--canonical-run-id")
    parser.add_argument("--environment", choices=("local", "test"), default="local")
    parser.add_argument("--output-root", type=Path, default=Path("~/.cloudmold/runs/full-chain-qa"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return plan(args) if args.mode == "plan" else execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
