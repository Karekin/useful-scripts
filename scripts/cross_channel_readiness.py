#!/usr/bin/env python3
"""Validate CloudMold admin/mobile journey evidence and derive readiness."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "cross-channel-capability-v1.json"
)
DIMENSIONS = (
    "surface",
    "live_api",
    "canonical_sor",
    "event",
    "agent",
    "cross_channel",
)
STATUSES = {"connected", "partial", "missing"}
EVIDENCE_KINDS = {
    "SOURCE_FILE",
    "CONTRACT_TEST",
    "INTEGRATION_TEST",
    "SCENARIO_RECEIPT",
    "RUNTIME_LINKAGE",
}
EVIDENCE_SCOPES = {
    "LOCAL_REPOSITORY",
    "LOCAL_TEST",
    "LOCAL_RUNTIME_VERIFIED",
}
LINKAGE_KINDS = {"SCENARIO_RECEIPT", "RUNTIME_LINKAGE"}
LINKAGE_KEYS = (
    "run_id",
    "tenant_id",
    "session_id",
    "principal_id",
    "order_id",
    "after_sale_id",
    "ticket_id",
    "address_ref",
)


class ReadinessError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReadinessError(f"cannot load registry {path}: {error}") from error
    if not isinstance(value, dict):
        raise ReadinessError(f"registry root must be an object: {path}")
    return value


def _resolve(workspace: Path, source: str) -> Path:
    path = Path(source).expanduser()
    return path if path.is_absolute() else workspace / path


def _parse_time(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise ReadinessError(f"{field} must be ISO-8601") from error
    if parsed.tzinfo is None:
        raise ReadinessError(f"{field} must include timezone")
    return parsed.astimezone(timezone.utc)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReadinessError(message)


def _load_now(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _validate_test_receipt(
    receipt: dict[str, Any],
    workspace: Path,
    now: datetime,
    evidence_name: str,
) -> None:
    _require(isinstance(receipt, dict), f"{evidence_name}: receipt must be an object")
    _require(
        receipt.get("suite") in {"unittest", "pytest", "cli"},
        f"{evidence_name}: receipt suite is invalid",
    )
    _require(
        isinstance(receipt.get("path"), str) and receipt["path"].strip(),
        f"{evidence_name}: receipt path is required",
    )
    path = _resolve(workspace, receipt["path"])
    _require(path.is_file(), f"{evidence_name}: missing receipt path {receipt['path']}")
    _require(
        isinstance(receipt.get("case"), str) and receipt["case"].strip(),
        f"{evidence_name}: receipt case is required",
    )
    captured_at = receipt.get("captured_at")
    if captured_at:
        _parse_time(captured_at, f"{evidence_name} receipt captured_at")
    max_age_days = receipt.get("max_age_days")
    if captured_at is not None or max_age_days is not None:
        _require(
            isinstance(max_age_days, int) and max_age_days > 0,
            f"{evidence_name}: receipt max_age_days must be a positive integer",
        )
        age_days = (
            now - _parse_time(captured_at, f"{evidence_name} receipt captured_at")
        ).total_seconds() / 86400
        _require(
            age_days <= max_age_days,
            f"{evidence_name}: receipt is older than {max_age_days} days",
        )


def _validate_evidence(
    evidence: dict[str, Any],
    *,
    stage_id: str,
    dimension: str,
    workspace: Path,
    now: datetime,
) -> None:
    evidence_name = f"{stage_id}.{dimension}"
    _require(
        evidence.get("kind") in EVIDENCE_KINDS,
        f"{evidence_name}: evidence kind is invalid",
    )
    _require(
        evidence.get("scope") in EVIDENCE_SCOPES,
        f"{evidence_name}: evidence scope is invalid",
    )
    stable = evidence.get("stable")
    _require(isinstance(stable, bool), f"{evidence_name}: stable must be boolean")
    source_files = evidence.get("source_files")
    _require(
        isinstance(source_files, list) and source_files,
        f"{evidence_name}: source_files are required",
    )
    for source in source_files:
        _require(
            isinstance(source, str) and source.strip(),
            f"{evidence_name}: source file must be a non-empty string",
        )
        _require(
            _resolve(workspace, source).is_file(),
            f"{evidence_name}: missing source file {source}",
        )
    denominator = evidence.get("denominator")
    _require(
        isinstance(denominator, dict), f"{evidence_name}: denominator is required"
    )
    _require(
        isinstance(denominator.get("unit"), str) and denominator["unit"].strip(),
        f"{evidence_name}: denominator unit is required",
    )
    expected = denominator.get("expected")
    verified = denominator.get("verified")
    _require(
        isinstance(expected, int) and expected > 0,
        f"{evidence_name}: denominator expected must be positive",
    )
    _require(
        isinstance(verified, int) and verified > 0,
        f"{evidence_name}: denominator verified must be positive",
    )
    _require(
        verified == expected,
        f"{evidence_name}: denominator verified must equal expected",
    )

    test_receipts = evidence.get("test_receipts", [])
    _require(
        isinstance(test_receipts, list),
        f"{evidence_name}: test_receipts must be a list",
    )
    if evidence["kind"] != "SOURCE_FILE":
        _require(test_receipts, f"{evidence_name}: test_receipts are required")
    for receipt in test_receipts:
        _validate_test_receipt(receipt, workspace, now, evidence_name)

    lineage = evidence.get("lineage")
    if evidence["kind"] in LINKAGE_KINDS:
        _require(
            isinstance(lineage, dict),
            f"{evidence_name}: lineage is required for linkage evidence",
        )
        _require(
            isinstance(lineage.get("run_id"), str) and lineage["run_id"].strip(),
            f"{evidence_name}: lineage.run_id is required",
        )
        _require(
            isinstance(lineage.get("tenant_id"), str) and lineage["tenant_id"].strip(),
            f"{evidence_name}: lineage.tenant_id is required",
        )
        _require(
            any(
                isinstance(lineage.get(key), str) and lineage[key].strip()
                for key in LINKAGE_KEYS[2:]
            ),
            f"{evidence_name}: exact linkage evidence is required",
        )
    elif lineage is not None:
        _require(isinstance(lineage, dict), f"{evidence_name}: lineage must be an object")

    commit = evidence.get("commit")
    if not stable and evidence["scope"] == "LOCAL_REPOSITORY":
        _require(
            isinstance(commit, str) and commit.strip(),
            f"{evidence_name}: non-stable repository evidence requires commit",
        )

    if stable:
        return

    captured_at = evidence.get("captured_at")
    max_age_days = evidence.get("max_age_days")
    _require(
        isinstance(captured_at, str) and captured_at.strip(),
        f"{evidence_name}: captured_at is required for non-stable evidence",
    )
    _require(
        isinstance(max_age_days, int) and max_age_days > 0,
        f"{evidence_name}: max_age_days must be positive for non-stable evidence",
    )
    age_days = (
        now - _parse_time(captured_at, f"{evidence_name}.captured_at")
    ).total_seconds() / 86400
    _require(
        age_days <= max_age_days,
        f"{evidence_name}: evidence is older than {max_age_days} days",
    )


def _status_from_readiness(readiness: dict[str, bool]) -> str:
    true_count = sum(readiness.values())
    if true_count == len(DIMENSIONS):
        return "connected"
    if true_count <= 1:
        return "missing"
    return "partial"


def _validate_stage_v1(stage: dict[str, Any], workspace: Path) -> tuple[dict[str, bool], str]:
    stage_id = stage.get("id") or "<unknown>"
    status = stage.get("status")
    readiness = stage.get("readiness", {})
    source_files = stage.get("source_files", [])
    if (
        status not in STATUSES
        or set(readiness) != set(DIMENSIONS)
        or not all(isinstance(value, bool) for value in readiness.values())
        or not source_files
        or not stage.get("authority")
        or not stage.get("gap")
    ):
        raise ReadinessError(f"invalid v1 stage: {stage_id}")
    expected_status = _status_from_readiness(readiness)
    _require(
        status == expected_status,
        f"{stage_id}: status={status}, expected={expected_status}",
    )
    for source in source_files:
        _require(
            _resolve(workspace, source).is_file(),
            f"{stage_id}: missing source file {source}",
        )
    return readiness, status


def _validate_stage_v2(
    stage: dict[str, Any],
    *,
    workspace: Path,
    now: datetime,
) -> tuple[dict[str, bool], str]:
    stage_id = stage.get("id") or "<unknown>"
    for field in ("id", "name", "side", "authority", "gap"):
        _require(
            isinstance(stage.get(field), str) and stage[field].strip(),
            f"{stage_id}: {field} is required",
        )
    evidence_by_dimension = stage.get("evidence_by_dimension")
    _require(
        isinstance(evidence_by_dimension, dict),
        f"{stage_id}: evidence_by_dimension is required",
    )
    unknown_dimensions = sorted(set(evidence_by_dimension) - set(DIMENSIONS))
    _require(
        not unknown_dimensions,
        f"{stage_id}: unknown evidence dimensions {unknown_dimensions}",
    )
    readiness: dict[str, bool] = {}
    source_union: list[str] = []
    for dimension in DIMENSIONS:
        evidence = evidence_by_dimension.get(dimension)
        if evidence is None:
            readiness[dimension] = False
            continue
        _validate_evidence(
            evidence,
            stage_id=stage_id,
            dimension=dimension,
            workspace=workspace,
            now=now,
        )
        readiness[dimension] = True
        for source in evidence["source_files"]:
            if source not in source_union:
                source_union.append(source)
    if "status" in stage:
        _require(
            stage["status"] == _status_from_readiness(readiness),
            f"{stage_id}: status is not derived from evidence",
        )
    if "readiness" in stage:
        _require(
            stage["readiness"] == readiness,
            f"{stage_id}: readiness is not derived from evidence",
        )
    if "source_files" in stage:
        declared = stage["source_files"]
        _require(
            isinstance(declared, list) and declared,
            f"{stage_id}: source_files must be a non-empty list when declared",
        )
        _require(
            set(declared).issubset(set(source_union)),
            f"{stage_id}: source_files must be covered by evidence",
        )
    return readiness, _status_from_readiness(readiness)


def validate_registry(
    workspace: Path = WORKSPACE,
    registry_path: Path = DEFAULT_REGISTRY,
    now: datetime | None = None,
) -> dict[str, Any]:
    registry = _load(registry_path)
    version = registry.get("schema_version")
    _require(version in {1, 2}, "registry schema_version must be 1 or 2")
    declared_dimensions = tuple(registry.get("scoring", {}).get("dimensions", []))
    _require(
        declared_dimensions == DIMENSIONS,
        f"registry dimensions mismatch: {list(declared_dimensions)}",
    )

    stages = registry.get("stages", [])
    _require(stages, "registry must contain stages")
    ids = [stage.get("id") for stage in stages]
    duplicate_ids = sorted({stage_id for stage_id in ids if ids.count(stage_id) > 1})
    _require(not duplicate_ids, f"duplicate stage ids: {duplicate_ids}")

    clock = _load_now(now)
    audited_at = registry.get("audited_at")
    if audited_at is not None:
        _parse_time(audited_at, "audited_at")

    by_side: dict[str, dict[str, int | float]] = {}
    status_counts = {status: 0 for status in STATUSES}
    dimension_counts = {dimension: 0 for dimension in DIMENSIONS}
    stage_summaries: list[dict[str, Any]] = []

    for stage in stages:
        if version == 1:
            readiness, status = _validate_stage_v1(stage, workspace)
        else:
            readiness, status = _validate_stage_v2(
                stage,
                workspace=workspace,
                now=clock,
            )
        side = stage.get("side", "unknown")
        points = sum(readiness.values())
        side_summary = by_side.setdefault(
            side, {"stages": 0, "points": 0, "possible": 0}
        )
        side_summary["stages"] += 1
        side_summary["points"] += points
        side_summary["possible"] += len(DIMENSIONS)
        status_counts[status] += 1
        for dimension, ready in readiness.items():
            dimension_counts[dimension] += int(ready)
        stage_summaries.append(
            {
                "id": stage["id"],
                "side": side,
                "derived_readiness": readiness,
                "derived_status": status,
            }
        )

    for summary in by_side.values():
        summary["score_percent"] = round(
            float(summary["points"]) * 100 / float(summary["possible"]),
            1,
        )
    total_points = sum(float(summary["points"]) for summary in by_side.values())
    total_possible = sum(float(summary["possible"]) for summary in by_side.values())
    consumer_count = int(by_side.get("consumer", {}).get("stages", 0))
    consumer_critical_points = sum(
        1
        for stage in stage_summaries
        if stage["side"] == "consumer"
        for dimension in ("canonical_sor", "event", "agent", "cross_channel")
        if stage["derived_readiness"][dimension]
    )
    consumer_critical_possible = consumer_count * 4
    return {
        "audit_id": registry["audit_id"],
        "status": "valid",
        "schema_version": version,
        "stages": len(stages),
        "status_counts": status_counts,
        "dimension_counts": dimension_counts,
        "by_side": by_side,
        "overall_score_percent": round(total_points * 100 / total_possible, 1),
        "consumer_critical_integration_percent": round(
            consumer_critical_points * 100 / consumer_critical_possible,
            1,
        ),
        "phase_gates": len(registry.get("phase_gates", [])),
        "stage_summaries": stage_summaries,
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
