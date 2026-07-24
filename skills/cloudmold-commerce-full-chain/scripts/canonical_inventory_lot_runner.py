#!/usr/bin/env python3
"""Prove canonical Lot lifecycle, qualified source mapping, recall fencing, and replay."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.parse
import uuid

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from canonical_inventory_runner import Client, ScenarioError, decimal, request_hash  # noqa: E402
from canonical_inventory_location_v3_runner import require  # noqa: E402


SCENARIO = "canonical-inventory-lot-lifecycle-v1"
LOT_ROUTE = "/admin-api/cloudmold/inventory/v3/lots/command"
INVENTORY_ROUTE = "/admin-api/cloudmold/inventory/v3/command"
LOT_QUERY_ROUTE = "/admin-api/cloudmold/inventory/v3/lots"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{5,31}$")
MASTER_SCENARIO = "canonical-merchant-warehouse-first-slice-v1"


def iso_time(value: dt.datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def scenario_context(run_id: str) -> tuple[str, dt.datetime]:
    digest = hashlib.sha256(run_id.encode()).hexdigest()
    correlation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:inventory-lot:{run_id}"))
    # Keep controlled events deterministic and already effective for the 2026 validation campaign.
    seconds = int(digest[:8], 16) % (180 * 24 * 60 * 60)
    return correlation_id, dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=seconds)


def load_master(path_value: str | None, tenant: int) -> dict:
    require(bool(path_value), "execute requires an explicit --master-ledger path")
    path = Path(path_value).expanduser().resolve()
    require(path.is_file(), f"master ledger does not exist: {path}")
    raw = path.read_bytes()
    try:
        ledger = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenarioError(f"cannot read master ledger: {exc}") from exc
    require(ledger.get("scenario") == MASTER_SCENARIO, "master ledger has an unexpected scenario")
    require(ledger.get("status") == "SUCCEEDED", "master ledger is not SUCCEEDED")
    require(ledger.get("tenant") == tenant, "master ledger tenant does not match")
    require(len(ledger.get("steps") or []) == 21, "master ledger must contain exactly 21 completed steps")
    replay = ledger.get("replay") or []
    require(len(replay) == 21 and all(item.get("duplicate") is True for item in replay),
            "master ledger must contain exactly 21 immutable duplicate replays")
    final = ledger.get("final") or {}
    require(final.get("merchant_status") == "ACTIVE", "master Merchant is not ACTIVE")
    require(final.get("warehouse_status") == "ACTIVE", "master Warehouse is not ACTIVE")
    require(final.get("all_replay_duplicate") is True, "master final replay assertion is missing")
    fields = ("merchant_id", "canonical_sku_id", "warehouse_id", "location_id")
    require(all(isinstance(final.get(field), str) and final.get(field) for field in fields),
            "master ledger is missing exact canonical Inventory dimensions")
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
            **{field: final[field] for field in fields}}


def lot_command(run_id: str, correlation_id: str, occurred_at: dt.datetime,
                index: int, operation: str, **values: object) -> dict:
    payload = {
        "operation": operation,
        "idempotencyKey": f"{run_id}-{index:02d}-{operation.lower().replace('_', '-')}",
        "sourceEventId": str(uuid.uuid5(uuid.NAMESPACE_URL,
                                         f"cloudmold:inventory-lot:{run_id}:{index}:{operation}")),
        "runId": run_id,
        "reasonCode": f"CONTROLLED_{operation}",
        "evidenceRef": f"run:{run_id}/lot/{index:02d}",
        "traceId": f"canonical-inventory-lot:{run_id}",
        "correlationId": correlation_id,
        "occurredAt": iso_time(occurred_at + dt.timedelta(seconds=index)),
    }
    payload.update(values)
    return payload


def inventory_command(run_id: str, master: dict, lot_id: str, correlation_id: str,
                      occurred_at: dt.datetime, index: int, operation: str, quantity: str,
                      reservation_id: str | None = None) -> dict:
    business_types = {"RECEIVE": "PURCHASE_RECEIPT", "RESERVE": "TRADE_ORDER", "RELEASE": "CANCEL"}
    payload = {
        "operation": operation,
        "idempotencyKey": f"{run_id}-{index:02d}-{operation.lower()}",
        "sourceEventId": str(uuid.uuid5(uuid.NAMESPACE_URL,
                                         f"cloudmold:inventory-lot-stock:{run_id}:{index}:{operation}")),
        "ownerType": "MERCHANT", "ownerId": master["merchant_id"],
        "canonicalSkuId": master["canonical_sku_id"], "warehouseId": master["warehouse_id"],
        "locationId": master["location_id"], "lotId": lot_id,
        "stockStatus": "SELLABLE", "qualityStatus": "QUALIFIED", "baseUomCode": "PCS",
        "quantity": quantity, "businessType": business_types[operation], "businessId": run_id,
        "businessItemId": f"lot-line-{index}", "businessNo": f"CLOT-{run_id}",
        "correlationId": correlation_id,
        "occurredAt": iso_time(occurred_at + dt.timedelta(seconds=index)),
    }
    if reservation_id is not None:
        payload["reservationId"] = reservation_id
    return payload


class Ledger:
    def __init__(self, args: argparse.Namespace, master: dict):
        root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
        directory = root / "inventory-lot" / args.run_id
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "ledger.json"
        if target.exists():
            suffix = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            target = directory / f"replay-ledger-{suffix}.json"
        self.path = target
        self.value = {
            "scenario": SCENARIO, "run_id": args.run_id, "environment": args.environment,
            "tenant": args.tenant, "master_ledger": master["path"],
            "master_ledger_sha256": master["sha256"],
            "source_authority": {"system": "CLOUDMOLD_ERP_OPERATOR", "type": "CONTROLLED_LOT",
                                 "classification": "run-scoped controlled evidence; not historical WMS/ERP proof"},
            "canonical_refs": {key: master[key] for key in
                               ("merchant_id", "canonical_sku_id", "warehouse_id", "location_id")},
            "steps": [], "replay": [], "status": "STARTED",
        }
        self.flush()

    def flush(self) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def append(self, kind: str, operation: str, payload: dict, result: dict) -> None:
        self.value["steps"].append({"kind": kind, "operation": operation,
                                    "request_hash": request_hash(payload), "result": result})
        self.flush()


def execute(args: argparse.Namespace) -> dict:
    master = load_master(args.master_ledger, args.tenant)
    client = Client(args.base_url, args.tenant, args.token, args.timeout)
    if not client.token:
        require(bool(args.username) and bool(args.password),
                "set token or username/password through environment variables")
        client.login(args.username, args.password)
    ledger = Ledger(args, master)
    correlation_id, occurred_at = scenario_context(args.run_id)
    issued: list[tuple[str, dict, dict]] = []

    register = lot_command(args.run_id, correlation_id, occurred_at, 1, "REGISTER",
                           ownerType="MERCHANT", ownerId=master["merchant_id"],
                           canonicalSkuId=master["canonical_sku_id"], lotCode=f"LOT-{args.run_id.upper()}",
                           manufacturedOn="2026-01-01", expiresOn="2027-12-31",
                           receivedAt=iso_time(occurred_at))
    registered = client.request("POST", LOT_ROUTE, register)
    require(registered.get("lotStatus") == "ACTIVE" and registered.get("lotVersion") == 1,
            "REGISTER did not create ACTIVE Lot v1")
    lot_id = registered.get("lotId")
    require(isinstance(lot_id, str) and lot_id, "REGISTER returned no Lot ID")
    ledger.append("lot_command", "REGISTER", register, registered)
    issued.append((LOT_ROUTE, register, registered))

    source_id = f"{args.run_id}:controlled-batch"
    link_a = lot_command(args.run_id, correlation_id, occurred_at, 2, "LINK_SOURCE",
                         lotId=lot_id, expectedLotVersion=1,
                         mappedSourceSystem="CLOUDMOLD_ERP_OPERATOR", mappedSourceType="CONTROLLED_LOT",
                         mappedSourceId=source_id, validFrom=iso_time(occurred_at + dt.timedelta(seconds=2)),
                         verificationRef=f"run:{args.run_id}/source/A")
    linked_a = client.request("POST", LOT_ROUTE, link_a)
    require(linked_a.get("mappingStatus") == "ACTIVE" and linked_a.get("mappingVersion") == 1,
            "first source mapping did not become ACTIVE v1")
    ledger.append("lot_command", "LINK_SOURCE_A", link_a, linked_a)
    issued.append((LOT_ROUTE, link_a, linked_a))

    receive = inventory_command(args.run_id, master, lot_id, correlation_id, occurred_at,
                                3, "RECEIVE", "10.000000")
    received = client.request("POST", INVENTORY_ROUTE, receive)
    validate_stock(received, ("10.000000", "0.000000", "10.000000", 1), "RECEIVE")
    ledger.append("inventory_command", "RECEIVE", receive, received)
    issued.append((INVENTORY_ROUTE, receive, received))

    reserve = inventory_command(args.run_id, master, lot_id, correlation_id, occurred_at,
                                4, "RESERVE", "2.000000")
    reserved = client.request("POST", INVENTORY_ROUTE, reserve)
    validate_stock(reserved, ("10.000000", "2.000000", "8.000000", 2), "RESERVE")
    reservation_id = reserved.get("reservationId")
    require(isinstance(reservation_id, str) and reservation_id, "RESERVE returned no reservation ID")
    ledger.append("inventory_command", "RESERVE", reserve, reserved)
    issued.append((INVENTORY_ROUTE, reserve, reserved))

    release = inventory_command(args.run_id, master, lot_id, correlation_id, occurred_at,
                                5, "RELEASE", "2.000000", reservation_id)
    released = client.request("POST", INVENTORY_ROUTE, release)
    validate_stock(released, ("10.000000", "0.000000", "10.000000", 3), "RELEASE")
    ledger.append("inventory_command", "RELEASE", release, released)
    issued.append((INVENTORY_ROUTE, release, released))

    recall = lot_command(args.run_id, correlation_id, occurred_at, 6, "RECALL",
                         lotId=lot_id, expectedLotVersion=1,
                         recallReference=f"ticket:{args.run_id}/product-recall")
    recalled = client.request("POST", LOT_ROUTE, recall)
    require(recalled.get("lotStatus") == "RECALLED" and recalled.get("lotVersion") == 2,
            "RECALL did not create RECALLED Lot v2")
    ledger.append("lot_command", "RECALL", recall, recalled)
    issued.append((LOT_ROUTE, recall, recalled))

    boundary = occurred_at + dt.timedelta(seconds=7)
    end_a = lot_command(args.run_id, correlation_id, occurred_at, 7, "END_SOURCE",
                        mappingId=linked_a["mappingId"], expectedMappingVersion=1, validTo=iso_time(boundary))
    ended_a = client.request("POST", LOT_ROUTE, end_a)
    require(ended_a.get("mappingStatus") == "ENDED" and ended_a.get("mappingVersion") == 2,
            "first source mapping did not end at v2")
    ledger.append("lot_command", "END_SOURCE_A", end_a, ended_a)
    issued.append((LOT_ROUTE, end_a, ended_a))

    link_b = lot_command(args.run_id, correlation_id, occurred_at, 8, "LINK_SOURCE",
                         lotId=lot_id, expectedLotVersion=2,
                         mappedSourceSystem="CLOUDMOLD_ERP_OPERATOR", mappedSourceType="CONTROLLED_LOT",
                         mappedSourceId=source_id, validFrom=iso_time(boundary),
                         verificationRef=f"run:{args.run_id}/source/B")
    linked_b = client.request("POST", LOT_ROUTE, link_b)
    require(linked_b.get("mappingStatus") == "ACTIVE" and linked_b.get("mappingVersion") == 1,
            "replacement source mapping did not become ACTIVE v1")
    ledger.append("lot_command", "LINK_SOURCE_B", link_b, linked_b)
    issued.append((LOT_ROUTE, link_b, linked_b))

    eligibility_at = iso_time(occurred_at + dt.timedelta(seconds=9))
    current_path = f"{LOT_QUERY_ROUTE}/{urllib.parse.quote(lot_id, safe='')}?eligibilityAt=" \
                   + urllib.parse.quote(eligibility_at, safe="")
    current = client.request("GET", current_path)
    require(current.get("status") == "RECALLED" and current.get("allocationEligibility") == "LOT_RECALLED",
            "current Lot query did not expose recall fencing")
    ledger.append("lot_query", "CURRENT_RECALLED", {"lotId": lot_id, "eligibilityAt": eligibility_at}, current)

    availability_path = f"{LOT_QUERY_ROUTE}/{urllib.parse.quote(lot_id, safe='')}/availability?eligibilityAt=" \
                        + urllib.parse.quote(eligibility_at, safe="")
    availability = client.request("GET", availability_path)
    rows = availability.get("value") if isinstance(availability, dict) else availability
    require(isinstance(rows, list) and len(rows) == 1, "Lot availability is not exact single balance grain")
    row = rows[0]
    require((decimal(row.get("onHandQuantity")), decimal(row.get("reservedQuantity")),
             decimal(row.get("unreservedQuantity")), decimal(row.get("allocatableQuantity")),
             row.get("allocationEligibility"))
            == ("10.000000", "0.000000", "10.000000", "0.000000", "LOT_RECALLED"),
            "recalled Lot remained allocatable")
    ledger.append("availability_query", "RECALLED_FENCED", {"lotId": lot_id,
                  "eligibilityAt": eligibility_at}, {"rows": rows})

    rejected = inventory_command(args.run_id, master, lot_id, correlation_id, occurred_at,
                                 9, "RESERVE", "1.000000")
    try:
        client.request("POST", INVENTORY_ROUTE, rejected)
    except ScenarioError as error:
        validate_api_rejection(error, "post-recall RESERVE")
        rejection = {"rejected": True, "reason": "LOT_RECALLED"}
    else:
        raise ScenarioError("post-recall RESERVE unexpectedly succeeded")
    availability_after_rejection = client.request("GET", availability_path)
    rows_after_rejection = (availability_after_rejection.get("value")
                            if isinstance(availability_after_rejection, dict)
                            else availability_after_rejection)
    require(rows_after_rejection == rows,
            "post-recall RESERVE rejection changed the exact inventory balance")
    ledger.append("negative_gate", "RESERVE_AFTER_RECALL", rejected, rejection)

    for route, payload, first in issued:
        replay = client.request("POST", route, payload)
        require(replay.get("duplicate") is True, f"{payload['operation']} replay was not duplicate")
        require({key: value for key, value in replay.items() if key != "duplicate"}
                == {key: value for key, value in first.items() if key != "duplicate"},
                f"{payload['operation']} replay changed immutable result")
        ledger.value["replay"].append({"route": route, "operation": payload["operation"],
                                       "request_hash": request_hash(payload), "duplicate": True})
        ledger.flush()

    ledger.value["final"] = {
        "lot_id": lot_id, "lot_status": "RECALLED", "lot_version": 2,
        "active_mapping_id": linked_b["mappingId"], "successful_write_count": len(issued),
        "lifecycle_event_count": 2, "mapping_event_count": 3, "inventory_event_count": 3,
        "on_hand_quantity": "10.000000", "reserved_quantity": "0.000000",
        "unreserved_quantity": "10.000000", "allocatable_quantity": "0.000000",
        "allocation_eligibility": "LOT_RECALLED", "all_replay_duplicate": True,
    }
    ledger.value["status"] = "SUCCEEDED"
    ledger.flush()
    return {"status": "succeeded", "run_id": args.run_id, "ledger": str(ledger.path),
            "final": ledger.value["final"]}


def validate_stock(result: dict, expected: tuple[str, str, str, int], operation: str) -> None:
    actual = (decimal(result.get("onHandQuantity")), decimal(result.get("reservedQuantity")),
              decimal(result.get("availableQuantity")), result.get("aggregateVersion"))
    require(actual == expected, f"{operation} stock invariant mismatch: expected={expected} actual={actual}")


def validate_api_rejection(error: ScenarioError, operation: str) -> None:
    message = str(error)
    explicit_rejection = (
        "API rejected POST" in message
        or ("Dubbo capability " in message and " rejected POST " in message)
    )
    require(explicit_rejection,
            f"{operation} failed without an explicit public API rejection: {error}")


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
    parser.add_argument("--master-ledger", default=os.getenv("CLOUDMOLD_MASTER_LEDGER"))
    parser.add_argument("--timeout", type=int, default=20)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        require(bool(RUN_ID_PATTERN.fullmatch(args.run_id)), "unsafe run_id")
        require(args.environment in {"local", "demo", "test"}, "runner is restricted to local/demo/test")
        if args.mode == "plan":
            result = {"scenario": SCENARIO, "run_id": args.run_id,
                      "successful_writes": ["REGISTER", "LINK_SOURCE_A", "RECEIVE", "RESERVE", "RELEASE",
                                            "RECALL", "END_SOURCE_A", "LINK_SOURCE_B"],
                      "negative_gate": "RESERVE_AFTER_RECALL", "final_status": "RECALLED_FENCED",
                      "source_classification": "controlled run evidence, not historical WMS/ERP proof",
                      "side_effects": False}
        elif args.mode == "dry-run":
            paths = Client(args.base_url, args.tenant, args.token, args.timeout).openapi().get("paths", {})
            required = {LOT_ROUTE: "post", INVENTORY_ROUTE: "post",
                        LOT_QUERY_ROUTE + "/{lotId}": "get",
                        LOT_QUERY_ROUTE + "/{lotId}/availability": "get"}
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
