#!/usr/bin/env python3
"""Deterministic Agent runner for canonical-inventory-first-slice-v1."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
import uuid


ROUTE = "/admin-api/cloudmold/inventory/command"
STEPS = (
    ("RECEIVE", "10.000000", ("10.000000", "0.000000", "10.000000", 1)),
    ("RESERVE", "3.000000", ("10.000000", "3.000000", "7.000000", 2)),
    ("SHIP", "3.000000", ("7.000000", "0.000000", "7.000000", 3)),
    ("RETURN", "1.000000", ("8.000000", "0.000000", "8.000000", 4)),
    ("RESERVE", "2.000000", ("8.000000", "2.000000", "6.000000", 5)),
    ("RELEASE", "2.000000", ("8.000000", "0.000000", "8.000000", 6)),
)


class ScenarioError(RuntimeError):
    pass


class Client:
    def __init__(self, base_url: str, tenant: int, token: str | None, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.tenant = tenant
        self.token = token
        self.timeout = timeout
        self.transport = os.getenv("CLOUDMOLD_INTERNAL_TRANSPORT", "dubbo").lower()
        self.dubbo = None
        if self.transport != "dubbo":
            raise ScenarioError("cloudmold-commerce-full-chain forbids REST/OpenAPI transport")
        if self.transport == "dubbo":
            workspace = Path(os.getenv(
                "CLOUDMOLD_WORKSPACE", "/Users/karekin/Downloads/coding/project/CloudMold"))
            transport_scripts = workspace.expanduser().resolve() / "useful-scripts/scripts"
            if str(transport_scripts) not in sys.path:
                sys.path.insert(0, str(transport_scripts))
            try:
                from cloudmold_dubbo_client import DubboClient
            except ImportError as exc:
                raise ScenarioError(f"cannot load governed Dubbo client: {exc}") from exc
            self.dubbo = DubboClient(tenant, timeout)
            self.token = token or "governed-dubbo-context"

    def request(self, method: str, path: str, payload: dict | None = None,
                authenticated: bool = True) -> dict:
        if self.dubbo is not None:
            try:
                return self.dubbo.request(method, path, payload)
            except RuntimeError as exc:
                raise ScenarioError(str(exc)) from exc
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json", "tenant-id": str(self.tenant)}
        if authenticated:
            if not self.token:
                raise ScenarioError("authenticated request requires a token")
            headers["Authorization"] = "Bearer " + self.token
        request = urllib.request.Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            raise ScenarioError(f"HTTP {exc.code} {method} {path}: {raw[:500]}") from exc
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise ScenarioError(f"request failed for {method} {path}: {exc}") from exc
        if not isinstance(result, dict) or result.get("code") != 0:
            raise ScenarioError(f"API rejected {method} {path}: {result.get('code')} {result.get('msg')}")
        return result.get("data")

    def login(self, username: str, password: str) -> None:
        if self.dubbo is not None:
            return
        data = self.request("POST", "/admin-api/system/auth/login",
                            {"username": username, "password": password}, authenticated=False)
        self.token = data["accessToken"]

    def openapi(self) -> dict:
        if self.dubbo is not None:
            return {"paths": self.dubbo.available_paths(), "x-cloudmold-transport": "dubbo"}
        try:
            with urllib.request.urlopen(self.base_url + "/v3/api-docs", timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise ScenarioError(f"cannot read live OpenAPI: {exc}") from exc


def decimal(value: object) -> str:
    return f"{float(value):.6f}"


def request_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def resolve_catalog_sku(args: argparse.Namespace) -> tuple[str, str | None]:
    ledger_path = Path(args.catalog_ledger).expanduser().resolve() if args.catalog_ledger else None
    ledger_sku = None
    if ledger_path:
        if not ledger_path.is_file():
            raise ScenarioError(f"Catalog ledger does not exist: {ledger_path}")
        try:
            ledger = json.loads(ledger_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ScenarioError(f"cannot read Catalog ledger: {exc}") from exc
        if ledger.get("scenario") != "canonical-catalog-first-slice-v1":
            raise ScenarioError("Catalog ledger has an unexpected scenario")
        if ledger.get("tenant") != args.tenant:
            raise ScenarioError("Catalog ledger tenant does not match Inventory tenant")
        final = ledger.get("final") or {}
        if final.get("catalog_status") != "ACTIVE":
            raise ScenarioError("Catalog ledger does not prove an ACTIVE Catalog lifecycle")
        sku_ids = final.get("sku_ids")
        if not isinstance(sku_ids, list) or not sku_ids or not all(isinstance(item, str) and item for item in sku_ids):
            raise ScenarioError("Catalog ledger does not contain canonical SKU identities")
        ledger_sku = sorted(sku_ids)[0]
    if args.sku_id and ledger_sku and args.sku_id != ledger_sku:
        raise ScenarioError("--sku-id conflicts with the canonical SKU selected from --catalog-ledger")
    sku_id = args.sku_id or ledger_sku
    if not sku_id:
        raise ScenarioError("provide --catalog-ledger from an ACTIVE Catalog run or an explicit --sku-id")
    return sku_id, str(ledger_path) if ledger_path else None


def build_payloads(run_id: str, sku_id: str, warehouse_id: str, owner_id: str) -> list[dict]:
    seed_seconds = int(hashlib.sha256(run_id.encode()).hexdigest()[:8], 16) % (365 * 24 * 60 * 60)
    start = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=seed_seconds)
    payloads = []
    business_types = ("PURCHASE_RECEIPT", "ORDER", "SHIPMENT", "SALE_RETURN", "ORDER", "CANCEL")
    for index, ((operation, quantity, _), business_type) in enumerate(zip(STEPS, business_types), 1):
        payload = {
            "operation": operation, "idempotencyKey": f"{run_id}-{index}-{operation.lower()}",
            "ownerId": owner_id, "canonicalSkuId": sku_id, "warehouseId": warehouse_id,
            "stockStatus": "SELLABLE", "qualityStatus": "QUALIFIED", "uomCode": "PCS",
            "quantity": quantity, "businessType": business_type, "businessId": run_id,
            "businessItemId": f"line-{index}", "businessNo": f"CINV-{run_id}",
            "correlationId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:{run_id}:correlation:{index}")),
            "occurredAt": (start + dt.timedelta(seconds=index)).isoformat().replace("+00:00", "Z"),
        }
        if operation == "SHIP": payload["reservationId"] = "__FIRST_RESERVATION__"
        elif operation == "RELEASE": payload["reservationId"] = "__SECOND_RESERVATION__"
        payloads.append(payload)
    return payloads


def validate_result(result: dict, expected: tuple[str, str, str, int], operation: str) -> None:
    actual = (decimal(result["onHandQuantity"]), decimal(result["reservedQuantity"]),
              decimal(result["availableQuantity"]), result["aggregateVersion"])
    if actual != expected:
        raise ScenarioError(f"{operation} invariant mismatch: expected={expected} actual={actual}")


def execute(args: argparse.Namespace) -> dict:
    client = Client(args.base_url, args.tenant, args.token, args.timeout)
    if not client.token:
        if not args.username or not args.password:
            raise ScenarioError("set token or username/password through environment variables")
        client.login(args.username, args.password)
    sku_id, catalog_ledger = resolve_catalog_sku(args)
    payloads = build_payloads(args.run_id, sku_id, args.warehouse_id or f"scenario:{args.run_id}", args.owner_id)
    reservations: list[str] = []
    ledger = {"scenario": "canonical-inventory-first-slice-v1", "run_id": args.run_id,
              "environment": args.environment, "tenant": args.tenant,
              "canonical_sku_id": sku_id, "catalog_ledger": catalog_ledger, "steps": []}
    for index, (payload, (operation, _, expected)) in enumerate(zip(payloads, STEPS), 1):
        if payload.get("reservationId") == "__FIRST_RESERVATION__": payload["reservationId"] = reservations[0]
        elif payload.get("reservationId") == "__SECOND_RESERVATION__": payload["reservationId"] = reservations[1]
        result = client.request("POST", ROUTE, payload)
        validate_result(result, expected, operation)
        if operation == "RESERVE": reservations.append(result["reservationId"])
        ledger["steps"].append({"step": index, "operation": operation,
                                "request_hash": request_hash(payload), "result": result})
    replay = client.request("POST", ROUTE, payloads[0])
    if not replay.get("duplicate") or replay.get("aggregateVersion") != 1:
        raise ScenarioError("idempotent replay did not return the immutable first result")
    ledger["replay"] = {"request_hash": request_hash(payloads[0]), "result": replay}
    ledger["final"] = ledger["steps"][-1]["result"]
    run_root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    output = run_root / "inventory" / args.run_id / "ledger.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        suffix = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = output.parent / f"replay-ledger-{suffix}.json"
    output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
    return {"status": "succeeded", "run_id": args.run_id, "ledger": str(output),
            "canonical_sku_id": sku_id, "final": ledger["final"], "replay_duplicate": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "dry-run", "execute"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", default="local")
    parser.add_argument("--base-url", default=os.getenv("CLOUDMOLD_ERP_BASE_URL", "http://127.0.0.1:48080"))
    parser.add_argument("--tenant", type=int, default=int(os.getenv("CLOUDMOLD_TENANT_ID", "1")))
    parser.add_argument("--token", default=os.getenv("CLOUDMOLD_ADMIN_TOKEN"))
    parser.add_argument("--username", default=os.getenv("CLOUDMOLD_ADMIN_USERNAME"))
    parser.add_argument("--password", default=os.getenv("CLOUDMOLD_ADMIN_PASSWORD"))
    parser.add_argument("--sku-id")
    parser.add_argument("--catalog-ledger")
    parser.add_argument("--warehouse-id")
    parser.add_argument("--owner-id", default="internal-company")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        if args.mode == "plan":
            sku_id, catalog_ledger = resolve_catalog_sku(args)
            result = {"scenario": "canonical-inventory-first-slice-v1", "run_id": args.run_id,
                      "canonical_sku_id": sku_id, "catalog_ledger": catalog_ledger,
                      "steps": [step[0] for step in STEPS],
                      "final_expected": ["8.000000", "0.000000", "8.000000"], "side_effects": False}
        elif args.mode == "dry-run":
            sku_id, catalog_ledger = resolve_catalog_sku(args)
            paths = Client(args.base_url, args.tenant, args.token, args.timeout).openapi().get("paths", {})
            if ROUTE not in paths or "post" not in paths[ROUTE]:
                raise ScenarioError(f"live OpenAPI is missing {ROUTE}")
            result = {"status": "ready", "route": ROUTE, "canonical_sku_id": sku_id,
                      "catalog_ledger": catalog_ledger, "side_effects": False}
        else:
            result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ScenarioError as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
