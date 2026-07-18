#!/usr/bin/env python3
"""Audit live Dubbo exports against Skill declarations and retained execution evidence."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


CAPABILITY_RE = re.compile(r"capability\.cloudmold\.[a-z0-9.$_-]+(?:\.[a-z0-9.$_-]+)+\.v\d+")
TEXT_SUFFIXES = {".json", ".jsonl", ".md", ".py", ".yaml", ".yml"}


def parse_live_capabilities(output: str) -> list[dict[str, Any]]:
    for line in reversed(output.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, list) and all(isinstance(item, dict) for item in value):
            rows = [item for item in value if isinstance(item.get("capabilityId"), str)]
            if rows:
                return rows
    raise RuntimeError("Dubbo executor did not emit a live capability catalog")


def load_live_capabilities(compose_dir: Path, timeout_seconds: int) -> list[dict[str, Any]]:
    command = [
        "docker", "compose", "--profile", "agent", "run", "--no-deps", "--rm",
        "cloudmold-agent-executor", "--list-capabilities",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=compose_dir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"live Dubbo capability inventory timed out after {timeout_seconds}s") from exc
    if completed.returncode:
        raise RuntimeError(f"live Dubbo capability inventory failed with exit {completed.returncode}")
    return parse_live_capabilities(completed.stdout)


def collect_skill_capabilities(skill_root: Path) -> tuple[set[str], dict[str, list[str]]]:
    capabilities: set[str] = set()
    sources: dict[str, list[str]] = defaultdict(list)
    if not skill_root.exists():
        return capabilities, {}
    skill_dirs = sorted(manifest.parent for manifest in skill_root.glob("*/skill.json"))
    for skill_dir in skill_dirs:
        for path in sorted(skill_dir.rglob("*")):
            if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
                continue
            relative = path.relative_to(skill_root)
            if "tests" in relative.parts or "__pycache__" in relative.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for capability_id in sorted(set(CAPABILITY_RE.findall(text))):
                capabilities.add(capability_id)
                sources[capability_id].append(relative.as_posix())
    return capabilities, dict(sources)


def _walk_succeeded_steps(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        capability_id = value.get("capabilityId") or value.get("capability_id")
        status = value.get("status")
        if isinstance(capability_id, str) and status == "SUCCEEDED":
            found.add(capability_id)
        for child in value.values():
            found.update(_walk_succeeded_steps(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_walk_succeeded_steps(child))
    return found


def collect_executed_capabilities(evidence_root: Path) -> tuple[set[str], dict[str, list[str]]]:
    capabilities: set[str] = set()
    sources: dict[str, list[str]] = defaultdict(list)
    if not evidence_root.exists():
        return capabilities, {}
    candidates = sorted(set(evidence_root.rglob("run.json")) | set(evidence_root.rglob("transport.jsonl")))
    for path in candidates:
        relative = path.relative_to(evidence_root).as_posix()
        try:
            if path.name == "transport.jsonl":
                rows = []
                for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                found = _walk_succeeded_steps(rows)
            else:
                found = _walk_succeeded_steps(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
        for capability_id in found:
            capabilities.add(capability_id)
            sources[capability_id].append(relative)
    return capabilities, dict(sources)


def classify(capability: dict[str, Any], *, skill_referenced: bool, executed: bool) -> str:
    interface_name = str(capability.get("interfaceName", ""))
    capability_id = str(capability.get("capabilityId", ""))
    if interface_name.startswith("org.apache.dubbo.") or ".metadata." in capability_id:
        return "GENERATED_OR_FRAMEWORK"
    if executed:
        return "EXECUTED_BY_HSF_SKILL"
    if skill_referenced:
        return "TEST_GAP"
    return "FLOW_GAP"


def capability_domain(capability_id: str) -> str:
    tokens = capability_id.split(".")
    return tokens[2] if len(tokens) > 2 else "unknown"


def build_report(live: list[dict[str, Any]], skill_root: Path, evidence_root: Path) -> dict[str, Any]:
    referenced, reference_sources = collect_skill_capabilities(skill_root)
    executed, execution_sources = collect_executed_capabilities(evidence_root)
    live_by_id = {row["capabilityId"]: row for row in live}
    rows: list[dict[str, Any]] = []
    classifications: Counter[str] = Counter()
    domains: dict[str, Counter[str]] = defaultdict(Counter)

    for capability_id, capability in sorted(live_by_id.items()):
        classification = classify(
            capability,
            skill_referenced=capability_id in referenced,
            executed=capability_id in executed,
        )
        classifications[classification] += 1
        domain = capability_domain(capability_id)
        domains[domain]["exported"] += 1
        domains[domain][classification] += 1
        rows.append({
            "capabilityId": capability_id,
            "interfaceName": capability.get("interfaceName"),
            "methodName": capability.get("methodName"),
            "operationType": capability.get("operationType"),
            "returnType": capability.get("returnType"),
            "domain": domain,
            "skillReferenced": capability_id in referenced,
            "executed": capability_id in executed,
            "classification": classification,
            "skillSources": reference_sources.get(capability_id, []),
            "executionSources": execution_sources.get(capability_id, []),
            "developmentPurpose": (
                "Dubbo framework metadata/introspection surface"
                if classification == "GENERATED_OR_FRAMEWORK"
                else f"Atomic {capability.get('operationType', 'UNKNOWN')} capability "
                     f"implemented by {capability.get('interfaceName')}.{capability.get('methodName')}"
            ),
        })

    missing_exports = sorted(referenced - set(live_by_id))
    return {
        "schema_version": "cloudmold.hsf-coverage-audit/v1",
        "scope": {
            "skill_root": str(skill_root),
            "evidence_root": str(evidence_root),
            "denominator": "live capability IDs exported by the governed Provider and visible to Agent Executor",
            "skill_ownership": "capability references below a direct child Skill carrying skill.json; registries alone do not count",
        },
        "denominators": {
            "live_exported_capabilities": len(live_by_id),
            "skill_referenced_capabilities": len(referenced),
            "retained_executed_capabilities": len(executed),
            "missing_live_exports": len(missing_exports),
        },
        "summary": {
            "classifications": dict(sorted(classifications.items())),
            "domains": {key: dict(sorted(value.items())) for key, value in sorted(domains.items())},
            "missingLiveExports": missing_exports,
            "allSkillReferencesExported": not missing_exports,
            "allBusinessExportsSkillOwned": classifications.get("FLOW_GAP", 0) == 0,
        },
        "capabilities": rows,
        "interpretation": {
            "zero_execution_is_redundancy": False,
            "flow_gap_meaning": "live business RPC export has no checked-in Skill reference",
            "test_gap_meaning": "Skill declares the RPC export but retained successful HSF evidence is absent",
            "deletion_requires_history_owner_and_regression_test": True,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    denominators = report["denominators"]
    summary = report["summary"]
    lines = [
        "# CloudMold HSF coverage audit",
        "",
        "Provider 实时导出的 capability 是分母；HTTP/OpenAPI 不计为 HSF 运行证据。",
        "",
        "## Denominators",
        "",
        "| Metric | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| `{key}` | {value} |" for key, value in denominators.items())
    lines.extend(["", "## Classification", "", "| Class | Count |", "|---|---:|"])
    lines.extend(f"| `{key}` | {value} |" for key, value in summary["classifications"].items())
    lines.extend([
        "",
        "## Missing live exports",
        "",
    ])
    if summary["missingLiveExports"]:
        lines.extend(f"- `{capability_id}`" for capability_id in summary["missingLiveExports"])
    else:
        lines.append("- None. Every checked-in Skill capability reference is live-exported.")
    lines.extend([
        "",
        "## Unowned or unexecuted business capabilities",
        "",
        "| Class | Operation | Capability | Implementation purpose |",
        "|---|---|---|---|",
    ])
    for row in report["capabilities"]:
        if row["classification"] not in {"FLOW_GAP", "TEST_GAP"}:
            continue
        purpose = str(row["developmentPurpose"]).replace("|", "\\|")
        lines.append(
            f"| `{row['classification']}` | `{row.get('operationType')}` | "
            f"`{row['capabilityId']}` | {purpose} |"
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--skill-root", type=Path)
    parser.add_argument("--evidence-root", type=Path, default=Path("~/.cloudmold/runs"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = args.workspace.resolve()
    skill_root = (args.skill_root or workspace / "useful-scripts/skills").resolve()
    evidence_root = args.evidence_root.expanduser().resolve()
    compose_dir = workspace / "useful-scripts/yml/yudao"
    live = load_live_capabilities(compose_dir, args.timeout_seconds)
    report = build_report(live, skill_root, evidence_root)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "hsf-coverage.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "hsf-coverage.md").write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir), **report["denominators"]}))
    return 2 if report["summary"]["missingLiveExports"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
