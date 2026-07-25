#!/usr/bin/env python3
"""Validate CloudMold admin/mobile journey evidence and report readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "cross-channel-capability-v1.json"
)
DIMENSIONS = {
    "surface",
    "live_api",
    "canonical_sor",
    "event",
    "agent",
    "cross_channel",
}
STATUSES = {"connected", "partial", "missing"}


class ReadinessError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReadinessError(f"cannot load registry {path}: {error}") from error


def _resolve(workspace: Path, source: str) -> Path:
    path = Path(source).expanduser()
    return path if path.is_absolute() else workspace / path


def validate_registry(
    workspace: Path = WORKSPACE,
    registry_path: Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    registry = _load(registry_path)
    if registry.get("schema_version") != 1:
        raise ReadinessError("registry schema_version must be 1")
    declared_dimensions = set(registry.get("scoring", {}).get("dimensions", []))
    if declared_dimensions != DIMENSIONS:
        raise ReadinessError(
            f"registry dimensions mismatch: {sorted(declared_dimensions)}"
        )

    stages = registry.get("stages", [])
    if not stages:
        raise ReadinessError("registry must contain stages")
    ids = [stage.get("id") for stage in stages]
    duplicate_ids = sorted({stage_id for stage_id in ids if ids.count(stage_id) > 1})
    if duplicate_ids:
        raise ReadinessError(f"duplicate stage ids: {duplicate_ids}")

    missing_files: list[dict[str, str]] = []
    invalid_stages: list[str] = []
    by_side: dict[str, dict[str, int]] = {}
    status_counts = {status: 0 for status in STATUSES}
    dimension_counts = {dimension: 0 for dimension in sorted(DIMENSIONS)}

    for stage in stages:
        stage_id = stage.get("id") or "<unknown>"
        status = stage.get("status")
        readiness = stage.get("readiness", {})
        source_files = stage.get("source_files", [])
        if (
            status not in STATUSES
            or set(readiness) != DIMENSIONS
            or not all(isinstance(value, bool) for value in readiness.values())
            or not source_files
            or not stage.get("authority")
            or not stage.get("gap")
        ):
            invalid_stages.append(stage_id)
            continue
        true_count = sum(readiness.values())
        expected_status = (
            "connected"
            if true_count == len(DIMENSIONS)
            else "missing"
            if true_count <= 1
            else "partial"
        )
        if status != expected_status:
            invalid_stages.append(
                f"{stage_id}: status={status}, expected={expected_status}"
            )
        for source in source_files:
            if not _resolve(workspace, source).is_file():
                missing_files.append({"stage": stage_id, "source": source})
        side = stage.get("side", "unknown")
        side_summary = by_side.setdefault(
            side, {"stages": 0, "points": 0, "possible": 0}
        )
        side_summary["stages"] += 1
        side_summary["points"] += true_count
        side_summary["possible"] += len(DIMENSIONS)
        status_counts[status] += 1
        for dimension, ready in readiness.items():
            dimension_counts[dimension] += int(ready)

    if invalid_stages:
        raise ReadinessError(f"invalid stages: {invalid_stages}")
    if missing_files:
        raise ReadinessError(f"missing evidence files: {missing_files}")

    for summary in by_side.values():
        summary["score_percent"] = round(
            summary["points"] * 100 / summary["possible"], 1
        )
    total_points = sum(summary["points"] for summary in by_side.values())
    total_possible = sum(summary["possible"] for summary in by_side.values())
    consumer_count = by_side.get("consumer", {}).get("stages", 0)
    consumer_critical_points = sum(
        1
        for stage in stages
        if stage.get("side") == "consumer"
        for dimension in ("canonical_sor", "event", "agent", "cross_channel")
        if stage["readiness"][dimension]
    )
    consumer_critical_possible = consumer_count * 4
    return {
        "audit_id": registry["audit_id"],
        "status": "valid",
        "stages": len(stages),
        "status_counts": status_counts,
        "dimension_counts": dimension_counts,
        "by_side": by_side,
        "overall_score_percent": round(total_points * 100 / total_possible, 1),
        "consumer_critical_integration_percent": round(
            consumer_critical_points * 100 / consumer_critical_possible, 1
        ),
        "phase_gates": len(registry.get("phase_gates", [])),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=WORKSPACE)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = validate_registry(
            args.workspace.expanduser().resolve(),
            args.registry.expanduser().resolve(),
        )
    except ReadinessError as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False))
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            "Cross-channel readiness valid: "
            f"{result['stages']} stages, overall {result['overall_score_percent']}%, "
            f"consumer critical integration "
            f"{result['consumer_critical_integration_percent']}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
