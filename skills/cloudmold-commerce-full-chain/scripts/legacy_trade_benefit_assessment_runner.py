#!/usr/bin/env python3
"""Evidence runner for the local legacy Trade benefit assessment (no import)."""

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


SCENARIO = "legacy-trade-benefit-assessment-v1"
BASE_ROUTE = "/admin-api/cloudmold/order/migrations/legacy-trade-benefits"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
EXPECTED_STATUS = "BLOCKED_REQUIRES_GOVERNED_EVIDENCE"


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
    return {
        "idempotencyKey": f"{run_id}:legacy-trade-benefit-assess",
        "sourceEventId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:{run_id}:legacy-trade-snapshot")),
        "migrationRunId": migration_run_id(run_id),
        "policyVersion": "legacy-trade-benefit-v2",
        "evidenceRef": f"run:{run_id}/local-yudao-trade-current",
        "correlationId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:{run_id}:correlation")),
        "causationId": None,
        "occurredAt": occurred_at(run_id),
    }


def validate_result(result: dict, expected: dict[str, int] | None = None) -> None:
    source = result.get("sourceOrderCount")
    non_deleted = result.get("nonDeletedOrderCount")
    deleted = result.get("deletedExcludedCount")
    no_benefit = result.get("noBenefitOrderCount")
    pending = result.get("benefitEvidencePendingOrderCount")
    quarantined = result.get("quarantinedOrderCount")
    components = result.get("benefitComponentCount")
    require(isinstance(source, int) and source > 0, "assessment returned an empty source denominator")
    require(source == non_deleted + deleted, "source/deleted denominator does not conserve")
    require(non_deleted == no_benefit + pending + quarantined,
            "non-deleted assessment classes do not conserve")
    require(isinstance(components, int) and components > 0, "assessment returned no benefit evidence")
    require(result.get("sourceBenefitAmountMinor") == result.get("componentAmountMinor"),
            "benefit component amount does not conserve")
    require(result.get("unresolvedIdentityCount") == components,
            "every component must remain identity-unresolved")
    require(result.get("unresolvedFundingCount") == components,
            "every component must remain funding-unresolved")
    require(result.get("importAllowedComponentCount") == 0,
            "assessment illegally authorized component import")
    require(result.get("productionMigrationEnabled") is False,
            "assessment illegally enabled production migration")
    require(result.get("status") == EXPECTED_STATUS, "assessment did not fail closed")
    require(bool(re.fullmatch(r"[0-9a-f]{64}", result.get("sourceSnapshotHash", ""))),
            "assessment source snapshot hash is invalid")
    if expected:
        for field, value in expected.items():
            require(result.get(field) == value,
                    f"expected {field}={value}, got {result.get(field)}")


def execute(args: argparse.Namespace) -> dict:
    client = Client(args.base_url, args.tenant, args.token, args.timeout)
    if not client.token:
        require(bool(args.username) and bool(args.password),
                "set token or username/password through environment variables")
        client.login(args.username, args.password)
    payload = command(args.run_id)
    expected = {
        "sourceOrderCount": args.expected_source_orders,
        "nonDeletedOrderCount": args.expected_non_deleted,
        "deletedExcludedCount": args.expected_deleted,
        "noBenefitOrderCount": args.expected_no_benefit,
        "benefitEvidencePendingOrderCount": args.expected_pending,
        "quarantinedOrderCount": args.expected_quarantined,
        "benefitComponentCount": args.expected_components,
        "sourceBenefitAmountMinor": args.expected_benefit_amount,
    } if args.verify_reference_snapshot else None
    first = client.request("POST", f"{BASE_ROUTE}/assess", payload)
    validate_result(first, expected)
    require(not first.get("duplicate"), "first execution unexpectedly replayed an existing operation")
    replay = client.request("POST", f"{BASE_ROUTE}/assess", payload)
    validate_result(replay, expected)
    require(replay.get("duplicate") is True, "identical assessment replay was not immutable")

    migration_id = payload["migrationRunId"]
    persisted = client.request("GET", f"{BASE_ROUTE}/{migration_id}")
    candidates = client.request("GET", f"{BASE_ROUTE}/{migration_id}/candidates")
    components = client.request("GET", f"{BASE_ROUTE}/{migration_id}/components")
    require(persisted.get("sourceSnapshotHash") == first.get("sourceSnapshotHash"),
            "persisted run snapshot differs from command result")
    require(isinstance(candidates, list) and len(candidates) == first["sourceOrderCount"],
            "candidate denominator differs from persisted run")
    require(len({row["legacyOrderId"] for row in candidates}) == len(candidates),
            "candidate source order identities are not unique")
    require(all(row["canonicalImportAllowed"] is False for row in candidates),
            "candidate import authority is not closed")
    require(all((row["assessmentStatus"] == "NO_BENEFIT") == (len(row["reasonCodes"]) == 0)
                for row in candidates), "candidate blocker shape is inconsistent")
    require(isinstance(components, list) and len(components) == first["benefitComponentCount"],
            "component denominator differs from persisted run")
    require(sum(row["componentAmountMinor"] for row in components) == first["componentAmountMinor"],
            "component rows do not conserve the persisted amount")
    require(all(row["fundingResolutionStatus"] == "MISSING_NAMED_FUNDER_BREAKDOWN"
                and row["canonicalImportAllowed"] is False for row in components),
            "component governance fence is open")
    status_counts: dict[str, int] = {}
    for row in candidates:
        status = row["assessmentStatus"]
        status_counts[status] = status_counts.get(status, 0) + 1
    component_counts: dict[str, int] = {}
    for row in components:
        component_type = row["componentType"]
        component_counts[component_type] = component_counts.get(component_type, 0) + 1

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
        "status_counts": status_counts,
        "component_counts": component_counts,
        "candidates": candidates,
        "components": components,
        "invariants": {
            "immutable_replay": True,
            "source_identity_unique": True,
            "canonical_import_allowed": False,
            "production_migration_enabled": False,
            "governed_scope": "LOCAL_YUDAO_TRADE_NOT_YSHOPPING_SOURCE",
        },
    }
    run_root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    output = run_root / "legacy-trade-benefit-assessment" / args.run_id / "ledger.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        suffix = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = output.parent / f"replay-ledger-{suffix}.json"
    output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "succeeded", "run_id": args.run_id, "migration_run_id": migration_id,
        "ledger": str(output), "assessment": first, "status_counts": status_counts,
        "component_counts": component_counts, "immutable_replay": True,
        "canonical_import_allowed": False, "production_migration_enabled": False,
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
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--verify-reference-snapshot", action="store_true")
    parser.add_argument("--expected-source-orders", type=int, default=238)
    parser.add_argument("--expected-non-deleted", type=int, default=230)
    parser.add_argument("--expected-deleted", type=int, default=8)
    parser.add_argument("--expected-no-benefit", type=int, default=104)
    parser.add_argument("--expected-pending", type=int, default=115)
    parser.add_argument("--expected-quarantined", type=int, default=11)
    parser.add_argument("--expected-components", type=int, default=128)
    parser.add_argument("--expected-benefit-amount", type=int, default=16845818)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        require(bool(RUN_ID_PATTERN.fullmatch(args.run_id)), "unsafe run_id")
        require(args.environment in {"local", "demo", "test"},
                "runner is restricted to local/demo/test")
        if args.mode == "plan":
            result = {"scenario": SCENARIO, "run_id": args.run_id,
                      "migration_run_id": migration_run_id(args.run_id),
                      "stages": ["ASSESS"], "import_writes": 0,
                      "future_gates": ["MAP_ORDER_ITEMS", "RESOLVE_BENEFIT_VERSIONS", "NAME_FUNDERS"],
                      "side_effects": False}
        elif args.mode == "dry-run":
            paths = Client(args.base_url, args.tenant, args.token, args.timeout).openapi().get("paths", {})
            required = {f"{BASE_ROUTE}/assess": "post", f"{BASE_ROUTE}/{{migrationRunId}}": "get",
                        f"{BASE_ROUTE}/{{migrationRunId}}/candidates": "get",
                        f"{BASE_ROUTE}/{{migrationRunId}}/components": "get"}
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
