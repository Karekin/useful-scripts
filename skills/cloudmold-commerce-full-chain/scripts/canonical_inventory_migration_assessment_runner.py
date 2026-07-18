#!/usr/bin/env python3
"""Evidence runner for canonical Inventory v1 migration ASSESS (no opening stock)."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

from canonical_inventory_runner import Client, ScenarioError


SCENARIO = "canonical-inventory-migration-assessment-v1"
ASSESS_ROUTE = "/admin-api/cloudmold/inventory/v3/migrations/assess-v1"
QUERY_ROUTE = "/admin-api/cloudmold/inventory/v3/migrations"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ScenarioError(message)


def migration_run_id(run_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:{SCENARIO}:{run_id}"))


def occurred_at(run_id: str) -> str:
    seconds = int(hashlib.sha256(run_id.encode()).hexdigest()[:8], 16) % (365 * 24 * 60 * 60)
    value = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=seconds)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def command(run_id: str) -> dict:
    migration_id = migration_run_id(run_id)
    return {
        "idempotencyKey": f"{run_id}:inventory-v1-assess",
        "sourceEventId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:{run_id}:source-snapshot")),
        "migrationRunId": migration_id,
        "policyVersion": "canonical-inventory-assess-v1",
        "evidenceRef": f"run:{run_id}/inventory-v1-assessment",
        "correlationId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:{run_id}:correlation")),
        "causationId": None,
        "occurredAt": occurred_at(run_id),
    }


def validate_result(result: dict, expected_count: int | None, expect_all_blocked: bool) -> None:
    candidate_count = result.get("candidateCount")
    eligible = result.get("eligibleCount")
    blocked = result.get("blockedCount")
    rejected = result.get("rejectedCount")
    require(isinstance(candidate_count, int) and candidate_count > 0, "assessment returned no candidates")
    require(candidate_count == eligible + blocked + rejected, "assessment decision counts do not conserve")
    require(result.get("status") == "ASSESSED", "assessment did not reach ASSESSED")
    require(bool(re.fullmatch(r"[0-9a-f]{64}", result.get("sourceSnapshotHash", ""))),
            "assessment source snapshot hash is invalid")
    if expected_count is not None:
        require(candidate_count == expected_count,
                f"expected {expected_count} candidates, got {candidate_count}")
    if expect_all_blocked:
        require(eligible == 0 and blocked == candidate_count and rejected == 0,
                "controlled local assessment was expected to be entirely blocked")


def execute(args: argparse.Namespace) -> dict:
    client = Client(args.base_url, args.tenant, args.token, args.timeout)
    if not client.token:
        require(bool(args.username) and bool(args.password),
                "set token or username/password through environment variables")
        client.login(args.username, args.password)
    payload = command(args.run_id)
    first = client.request("POST", ASSESS_ROUTE, payload)
    validate_result(first, args.expected_candidate_count, args.expect_all_blocked)
    require(not first.get("duplicate"), "first execution unexpectedly replayed an existing operation")
    replay = client.request("POST", ASSESS_ROUTE, payload)
    validate_result(replay, args.expected_candidate_count, args.expect_all_blocked)
    require(replay.get("duplicate") is True, "identical assessment replay was not immutable")
    migration_id = payload["migrationRunId"]
    persisted = client.request("GET", f"{QUERY_ROUTE}/{migration_id}")
    candidates = client.request("GET", f"{QUERY_ROUTE}/{migration_id}/candidates")
    require(persisted.get("sourceSnapshotHash") == first.get("sourceSnapshotHash"),
            "persisted run snapshot differs from command result")
    require(isinstance(candidates, list) and len(candidates) == first["candidateCount"],
            "persisted candidate list does not match run count")
    require(len({row["sourceId"] for row in candidates}) == len(candidates),
            "migration candidates contain duplicate source identities")
    require(all(row["sourceSystem"] == "CLOUDMOLD_INVENTORY_V1" and row["sourceType"] == "BALANCE"
                for row in candidates), "candidate source identity is not v1 balance qualified")
    require(all(row["decisionStatus"] != "ELIGIBLE" or not row["reasonCodes"] for row in candidates),
            "eligible candidate contains blockers")
    require(all(row["decisionStatus"] == "ELIGIBLE" or row["reasonCodes"] for row in candidates),
            "blocked/rejected candidate lacks evidence")
    classification_counts: dict[str, int] = {}
    for row in candidates:
        key = row["sourceClassification"]
        classification_counts[key] = classification_counts.get(key, 0) + 1
    ledger = {
        "scenario": SCENARIO,
        "run_id": args.run_id,
        "environment": args.environment,
        "tenant": args.tenant,
        "migration_run_id": migration_id,
        "command": {key: value for key, value in payload.items() if key != "causationId"},
        "assessment": first,
        "replay": replay,
        "persisted_run": persisted,
        "classification_counts": classification_counts,
        "candidates": candidates,
        "invariants": {
            "immutable_replay": True,
            "source_identity_unique": True,
            "v3_opening_writes_expected": 0,
            "migration_stage": "ASSESSED_ONLY",
        },
    }
    run_root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    output = run_root / "inventory-migration-assessment" / args.run_id / "ledger.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        suffix = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = output.parent / f"replay-ledger-{suffix}.json"
    output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "succeeded", "run_id": args.run_id, "migration_run_id": migration_id,
        "ledger": str(output), "candidate_count": first["candidateCount"],
        "eligible_count": first["eligibleCount"], "blocked_count": first["blockedCount"],
        "rejected_count": first["rejectedCount"], "classification_counts": classification_counts,
        "immutable_replay": True, "v3_opening_writes": 0,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "dry-run", "execute"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", default="local")
    parser.add_argument("--base-url", default=os.getenv("CLOUDMOLD_ERP_BASE_URL", "http://127.0.0.1:48080"))
    parser.add_argument("--tenant", type=int, default=int(os.getenv("CLOUDMOLD_TENANT_ID", "1")))
    parser.add_argument("--token", default=os.getenv("CLOUDMOLD_ADMIN_TOKEN"))
    parser.add_argument("--username", default=os.getenv("CLOUDMOLD_ADMIN_USERNAME"))
    parser.add_argument("--password", default=os.getenv("CLOUDMOLD_ADMIN_PASSWORD"))
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--expected-candidate-count", type=int)
    parser.add_argument("--expect-all-blocked", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        require(bool(RUN_ID_PATTERN.fullmatch(args.run_id)), "unsafe run_id")
        require(args.environment in {"local", "demo", "test"},
                "runner is restricted to local/demo/test")
        if args.mode == "plan":
            result = {
                "scenario": SCENARIO, "run_id": args.run_id,
                "migration_run_id": migration_run_id(args.run_id),
                "stages": ["ASSESS"], "opening_writes": 0,
                "future_gates": ["QUALIFY", "MIGRATE"], "side_effects": False,
            }
        elif args.mode == "dry-run":
            paths = Client(args.base_url, args.tenant, args.token, args.timeout).openapi().get("paths", {})
            required = {ASSESS_ROUTE: "post", QUERY_ROUTE + "/{migrationRunId}": "get",
                        QUERY_ROUTE + "/{migrationRunId}/candidates": "get"}
            missing = [f"{method.upper()} {route}" for route, method in required.items()
                       if route not in paths or method not in paths[route]]
            require(not missing, "live OpenAPI is missing: " + ", ".join(missing))
            result = {"status": "ready", "routes": list(required), "side_effects": False}
        else:
            result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ScenarioError, OSError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
