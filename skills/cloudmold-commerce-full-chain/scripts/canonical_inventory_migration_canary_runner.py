#!/usr/bin/env python3
"""Controlled Inventory v1 -> v3 qualification and single-opening canary runner."""

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

from canonical_inventory_runner import Client, ScenarioError, request_hash


SCENARIO = "canonical-inventory-migration-canary-v1"
WAREHOUSE_ROUTE = "/admin-api/cloudmold/warehouse/command"
V1_ROUTE = "/admin-api/cloudmold/inventory/command"
ASSESS_ROUTE = "/admin-api/cloudmold/inventory/v3/migrations/assess-v1"
QUALIFY_ROUTE = "/admin-api/cloudmold/inventory/v3/migrations/qualify-v1"
MIGRATE_ROUTE = "/admin-api/cloudmold/inventory/v3/migrations/migrate-v1"
QUERY_ROUTE = "/admin-api/cloudmold/inventory/v3/migrations"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ScenarioError(message)


def stable_uuid(run_id: str, label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:{SCENARIO}:{run_id}:{label}"))


def migration_run_id(run_id: str) -> str:
    return stable_uuid(run_id, "migration-run")


def base_time(run_id: str) -> dt.datetime:
    seconds = int(hashlib.sha256(run_id.encode()).hexdigest()[:6], 16) % 3600
    return dt.datetime(2026, 7, 15, 6, 0, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=seconds)


def iso(value: dt.datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def commands(run_id: str, owner_id: str, sku_id: str, warehouse_id: str,
             location_id: str) -> dict[str, dict]:
    correlation = stable_uuid(run_id, "correlation")
    start = base_time(run_id)
    legacy_warehouse = f"migration-canary:{run_id}"
    mapping = {
        "operation": "LINK_SOURCE", "idempotencyKey": f"{run_id}-warehouse-source",
        "sourceEventId": stable_uuid(run_id, "warehouse-source-event"),
        "correlationId": correlation, "occurredAt": iso(start),
        "sourceMapping": {
            "sourceSystem": "CLOUDMOLD_INVENTORY_V1", "sourceType": "WAREHOUSE",
            "sourceId": legacy_warehouse, "targetType": "WAREHOUSE",
            "warehouseId": warehouse_id, "validFrom": iso(start),
            "verificationRef": f"run:{run_id}/warehouse-source",
        },
    }
    receive = {
        "operation": "RECEIVE", "idempotencyKey": f"{run_id}-v1-canary-receive",
        "sourceEventId": stable_uuid(run_id, "v1-receive-event"),
        "ownerId": owner_id, "canonicalSkuId": sku_id, "warehouseId": legacy_warehouse,
        "stockStatus": "SELLABLE", "qualityStatus": "QUALIFIED", "uomCode": "PCS",
        "quantity": "10.000000", "businessType": "MIGRATION_CANARY",
        "businessId": migration_run_id(run_id), "businessItemId": "canary-1",
        "businessNo": f"CMIG-{run_id}", "correlationId": correlation,
        "occurredAt": iso(start + dt.timedelta(seconds=1)),
    }
    assess = {
        "idempotencyKey": f"{run_id}-assess", "sourceEventId": stable_uuid(run_id, "assess-event"),
        "migrationRunId": migration_run_id(run_id), "sourceBalanceId": None,
        "policyVersion": "canonical-inventory-assess-v2",
        "evidenceRef": f"run:{run_id}/assessment", "correlationId": correlation,
        "causationId": receive["sourceEventId"], "occurredAt": iso(start + dt.timedelta(seconds=2)),
    }
    qualify = {
        "idempotencyKey": f"{run_id}-qualify", "sourceEventId": stable_uuid(run_id, "qualify-event"),
        "migrationRunId": migration_run_id(run_id), "candidateId": None,
        "expectedSourceSnapshotHash": None, "warehouseId": warehouse_id, "locationId": location_id,
        "lotTrackingPolicy": "NOT_TRACKED", "lotId": None,
        "policyVersion": "canonical-inventory-qualify-v1",
        "evidenceRef": f"run:{run_id}/qualification", "correlationId": correlation,
        "causationId": assess["sourceEventId"], "occurredAt": iso(start + dt.timedelta(seconds=3)),
    }
    migrate = {
        "idempotencyKey": f"{run_id}-migrate", "sourceEventId": stable_uuid(run_id, "migrate-event"),
        "qualificationId": None, "expectedVersion": 1, "expectedSourceSnapshotHash": None,
        "evidenceRef": f"run:{run_id}/opening", "correlationId": correlation,
        "causationId": qualify["sourceEventId"], "occurredAt": iso(start + dt.timedelta(seconds=4)),
    }
    fence_probe = {
        "operation": "RECEIVE", "idempotencyKey": f"{run_id}-v1-fence-probe",
        "sourceEventId": stable_uuid(run_id, "v1-fence-probe-event"),
        "ownerId": owner_id, "canonicalSkuId": sku_id, "warehouseId": legacy_warehouse,
        "stockStatus": "SELLABLE", "qualityStatus": "QUALIFIED", "uomCode": "PCS",
        "quantity": "1.000000", "businessType": "MIGRATION_FENCE_PROBE",
        "businessId": migration_run_id(run_id), "businessItemId": "fence-1",
        "businessNo": f"CMIG-FENCE-{run_id}", "correlationId": correlation,
        "causationId": migrate["sourceEventId"],
        "occurredAt": iso(start + dt.timedelta(seconds=5)),
    }
    return {"mapping": mapping, "receive": receive, "assess": assess,
            "qualify": qualify, "migrate": migrate, "fence_probe": fence_probe}


def execute(args: argparse.Namespace) -> dict:
    client = Client(args.base_url, args.tenant, args.token, args.timeout)
    if not client.token:
        require(bool(args.username) and bool(args.password),
                "set token or username/password through environment variables")
        client.login(args.username, args.password)
    payloads = commands(args.run_id, args.owner_id, args.sku_id, args.warehouse_id, args.location_id)
    mapping = client.request("POST", WAREHOUSE_ROUTE, payloads["mapping"])
    require(mapping.get("status") == "ACTIVE" and mapping.get("warehouseId") == args.warehouse_id,
            "controlled v1 Warehouse source mapping is not ACTIVE")
    receive = client.request("POST", V1_ROUTE, payloads["receive"])
    require(receive.get("aggregateVersion") == 1 and float(receive.get("onHandQuantity")) == 10,
            "v1 canary source was not created at 10/0/0")
    source_balance_id = receive.get("balanceId")
    require(isinstance(source_balance_id, str), "v1 canary result lacks balanceId")
    payloads["assess"]["sourceBalanceId"] = source_balance_id
    assessment = client.request("POST", ASSESS_ROUTE, payloads["assess"])
    require(assessment.get("candidateCount") == 1 and assessment.get("blockedCount") == 1,
            "canary assessment must contain exactly one blocked candidate")
    candidates = client.request("GET", f"{QUERY_ROUTE}/{migration_run_id(args.run_id)}/candidates")
    require(len(candidates) == 1 and candidates[0].get("sourceClassification") == "CONTROLLED_CANARY",
            "assessment did not classify the exact source as CONTROLLED_CANARY")
    candidate = candidates[0]
    payloads["qualify"]["candidateId"] = candidate["candidateId"]
    payloads["qualify"]["expectedSourceSnapshotHash"] = candidate["legacySnapshotHash"]
    qualification = client.request("POST", QUALIFY_ROUTE, payloads["qualify"])
    require(qualification.get("status") == "QUALIFIED" and qualification.get("version") == 1,
            "canary qualification did not reach QUALIFIED/v1")
    payloads["migrate"]["qualificationId"] = qualification["qualificationId"]
    payloads["migrate"]["expectedSourceSnapshotHash"] = candidate["legacySnapshotHash"]
    opening = client.request("POST", MIGRATE_ROUTE, payloads["migrate"])
    require(opening.get("aggregateVersion") == 1 and float(opening.get("onHandQuantity")) == 10
            and float(opening.get("reservedQuantity")) == 0
            and float(opening.get("inTransitQuantity")) == 0,
            "migration opening is not the exact 10/0/0 v3 balance")
    persisted = client.request("GET", f"{QUERY_ROUTE}/qualifications/{qualification['qualificationId']}")
    require(persisted.get("status") == "MIGRATED" and persisted.get("version") == 2,
            "qualification did not reach MIGRATED/v2")
    replays = {
        "mapping": client.request("POST", WAREHOUSE_ROUTE, payloads["mapping"]),
        "receive": client.request("POST", V1_ROUTE, payloads["receive"]),
        "assess": client.request("POST", ASSESS_ROUTE, payloads["assess"]),
        "qualify": client.request("POST", QUALIFY_ROUTE, payloads["qualify"]),
        "migrate": client.request("POST", MIGRATE_ROUTE, payloads["migrate"]),
    }
    require(all(result.get("duplicate") is True for result in replays.values()),
            "one or more canary writes did not replay immutably")
    try:
        client.request("POST", V1_ROUTE, payloads["fence_probe"])
    except ScenarioError as error:
        require("legacy inventory balance is frozen after canonical migration" in str(error),
                f"post-migration v1 write failed for an unexpected reason: {error}")
        source_fence = {"rejected": True, "reason": "MIGRATED_SOURCE_FROZEN"}
    else:
        raise ScenarioError("post-migration v1 write was not rejected")
    ledger = {
        "scenario": SCENARIO, "run_id": args.run_id, "environment": args.environment,
        "tenant": args.tenant, "migration_run_id": migration_run_id(args.run_id),
        "master_data": {"owner_id": args.owner_id, "canonical_sku_id": args.sku_id,
                        "warehouse_id": args.warehouse_id, "location_id": args.location_id,
                        "warehouse_source_mapping_id": mapping.get("mappingId")},
        "requests": {name: {"request_hash": request_hash(payload)} for name, payload in payloads.items()},
        "source": receive, "assessment": assessment, "candidate": candidate,
        "qualification": qualification, "opening": opening, "persisted_qualification": persisted,
        "replays": replays, "source_fence": source_fence,
        "invariants": {"controlled_canary_only": True, "single_source": True,
                       "single_opening_driver": True, "opening_quantities": "10.000000/0.000000/0.000000",
                       "immutable_replay": True, "legacy_source_frozen": True,
                       "expected_lakehouse_stage": "MIGRATED_CANARY",
                       "expected_lakehouse_readiness": "CANARY_RECONCILED"},
    }
    root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    output = root / "inventory-migration-canary" / args.run_id / "ledger.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "succeeded", "run_id": args.run_id,
            "migration_run_id": migration_run_id(args.run_id), "ledger": str(output),
            "qualification_id": qualification["qualificationId"],
            "target_balance_id": opening["targetBalanceId"], "immutable_replay": True,
            "legacy_source_frozen": True}


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
    parser.add_argument("--owner-id", required=True)
    parser.add_argument("--sku-id", required=True)
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--location-id", required=True)
    parser.add_argument("--timeout", type=int, default=30)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        require(bool(RUN_ID_PATTERN.fullmatch(args.run_id)), "unsafe run_id")
        require(args.environment in {"local", "demo", "test"}, "runner is restricted to local/demo/test")
        if args.mode == "plan":
            result = {"scenario": SCENARIO, "run_id": args.run_id,
                      "migration_run_id": migration_run_id(args.run_id),
                      "stages": ["MAP_SOURCE", "CREATE_CANARY", "ASSESS", "QUALIFY", "MIGRATE",
                                 "VERIFY_SOURCE_FENCE"],
                      "opening_writes": 1, "side_effects": False}
        elif args.mode == "dry-run":
            paths = Client(args.base_url, args.tenant, args.token, args.timeout).openapi().get("paths", {})
            required = {WAREHOUSE_ROUTE: "post", V1_ROUTE: "post", ASSESS_ROUTE: "post",
                        QUALIFY_ROUTE: "post", MIGRATE_ROUTE: "post"}
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
