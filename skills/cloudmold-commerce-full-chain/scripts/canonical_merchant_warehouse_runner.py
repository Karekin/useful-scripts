#!/usr/bin/env python3
"""Run the canonical Identity, Merchant, and single-warehouse master-data slice."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid


IDENTITY_ROUTE = "/admin-api/cloudmold/identity/source/link"
IDENTITY_RESOLVE_ROUTE = "/admin-api/cloudmold/identity/source/resolve"
MERCHANT_ROUTE = "/admin-api/cloudmold/merchant/command"
WAREHOUSE_ROUTE = "/admin-api/cloudmold/warehouse/command"
WAREHOUSE_RESOLVE_ROUTE = "/admin-api/cloudmold/warehouse/source/resolve-network"
LISTING_ROUTE = "/admin-api/cloudmold/listing/command"
ERP_WAREHOUSE_ROUTE = "/admin-api/erp/warehouse/get"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{5,31}$")
SOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class ScenarioError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ScenarioError(message)


def request_hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def scenario_context(run_id: str) -> tuple[str, dt.datetime]:
    digest = hashlib.sha256(run_id.encode()).hexdigest()
    correlation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:master-data:{run_id}"))
    seconds = int(digest[:8], 16) % (365 * 24 * 60 * 60)
    # Keep effective-dated OWNER/source assignments deterministic and already active.
    # A current-year base can make the run-id hash land in the future, causing an
    # ACTIVE assignment to fail the valid_from authorization gate.
    occurred_at = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=seconds)
    return correlation_id, occurred_at


def load_catalog_identity(path_value: str | None, tenant: int) -> tuple[str, str, str]:
    require(bool(path_value), "execute requires --catalog-ledger from an ACTIVE canonical Catalog run")
    path = Path(path_value).expanduser().resolve()
    require(path.is_file(), f"Catalog ledger does not exist: {path}")
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenarioError(f"cannot read Catalog ledger: {exc}") from exc
    require(ledger.get("scenario") == "canonical-catalog-first-slice-v1",
            "Catalog ledger has an unexpected scenario")
    require(ledger.get("tenant") == tenant, "Catalog ledger tenant does not match scenario tenant")
    final = ledger.get("final") or {}
    require(final.get("catalog_status") == "ACTIVE", "Catalog ledger does not prove ACTIVE lifecycle")
    sku_ids = final.get("sku_ids")
    require(isinstance(sku_ids, list) and sku_ids, "Catalog ledger has no canonical SKU identities")
    spu_id = final.get("spu_id")
    require(isinstance(spu_id, str) and spu_id, "Catalog ledger has no canonical SPU identity")
    return sorted(sku_ids)[0], spu_id, str(path)


def iso_time(value: dt.datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class Client:
    def __init__(self, base_url: str, tenant: int, token: str | None, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.tenant = tenant
        self.token = token
        self.timeout = timeout
        self.dubbo = None
        transport = os.getenv("CLOUDMOLD_INTERNAL_TRANSPORT", "dubbo").lower()
        if transport != "dubbo":
            raise ScenarioError("cloudmold-commerce-full-chain forbids REST/OpenAPI transport")
        if transport == "dubbo":
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
                data = self.dubbo.request(method, path, payload)
            except RuntimeError as exc:
                raise ScenarioError(str(exc)) from exc
            return data if isinstance(data, dict) else {"value": data}
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
        data = result.get("data")
        return data if isinstance(data, dict) else {"value": data}

    def login(self, username: str, password: str) -> None:
        if self.dubbo is not None:
            return
        data = self.request("POST", "/admin-api/system/auth/login",
                            {"username": username, "password": password}, authenticated=False)
        token = data.get("accessToken")
        require(isinstance(token, str) and token, "login response has no access token")
        self.token = token

    def openapi(self) -> dict:
        if self.dubbo is not None:
            return {"paths": self.dubbo.available_paths(), "x-cloudmold-transport": "dubbo"}
        try:
            with urllib.request.urlopen(self.base_url + "/v3/api-docs", timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise ScenarioError(f"cannot read live OpenAPI: {exc}") from exc


class Ledger:
    def __init__(self, args: argparse.Namespace):
        root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
        directory = root / "merchant-warehouse" / args.run_id
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "ledger.json"
        if target.exists():
            suffix = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            target = directory / f"replay-ledger-{suffix}.json"
        self.path = target
        self.value = {
            "scenario": "canonical-merchant-warehouse-first-slice-v1",
            "run_id": args.run_id,
            "environment": args.environment,
            "tenant": args.tenant,
            "source_refs": {
                "system": {"source_type": "SYSTEM_ADMIN_USER", "source_id": args.system_admin_source_id},
                "erp": {"source_type": "WAREHOUSE", "source_id": args.erp_warehouse_source_id},
            },
            "steps": [],
            "status": "STARTED",
        }
        self.flush()

    def flush(self) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def append(self, domain: str, operation: str, payload: dict, result: dict) -> None:
        self.value["steps"].append({
            "domain": domain,
            "operation": operation,
            "request_hash": request_hash(payload),
            "result": result,
        })
        self.flush()


def base_command(operation: str, run_id: str, index: int, correlation_id: str,
                 occurred_at: dt.datetime) -> dict:
    readable_source_event_id = f"{run_id}:{index:02d}:{operation}"
    source_event_id = (readable_source_event_id if len(readable_source_event_id) <= 36 else
                       str(uuid.uuid5(
                           uuid.NAMESPACE_URL,
                           f"cloudmold:warehouse:{run_id}:{index:02d}:{operation}",
                       )))
    return {
        "operation": operation,
        "idempotencyKey": f"{run_id}-{index:02d}-{operation.lower().replace('_', '-')}",
        "sourceEventId": source_event_id,
        "correlationId": correlation_id,
        "occurredAt": iso_time(occurred_at + dt.timedelta(seconds=index)),
    }


def merchant_command(operation: str, run_id: str, index: int, correlation_id: str,
                     occurred_at: dt.datetime, **values: object) -> dict:
    payload = {
        "operation": operation,
        "idempotencyKey": f"{run_id}-merchant-{index:02d}-{operation.lower().replace('_', '-')}",
        "runId": run_id,
        "sourceSystem": "CLOUDMOLD_AGENT_TEST",
        "traceId": f"canonical-merchant-warehouse:{run_id}",
        "correlationId": correlation_id,
        "occurredAt": iso_time(occurred_at + dt.timedelta(seconds=100 + index)),
    }
    payload.update(values)
    return payload


def execute(args: argparse.Namespace) -> dict:
    client = Client(args.base_url, args.tenant, args.token, args.timeout)
    if not client.token:
        if not args.username or not args.password:
            raise ScenarioError("set token or username/password through environment variables")
        client.login(args.username, args.password)
    correlation_id, occurred_at = scenario_context(args.run_id)
    canonical_sku_id, canonical_spu_id, catalog_ledger = load_catalog_identity(
        args.catalog_ledger, args.tenant
    )
    ledger = Ledger(args)
    issued: list[tuple[str, str, dict, dict]] = []

    def issue(domain: str, operation: str, route: str, payload: dict) -> dict:
        result = client.request("POST", route, payload)
        ledger.append(domain, operation, payload, result)
        issued.append((domain, operation, payload, result))
        return result

    source_path = ERP_WAREHOUSE_ROUTE + "?" + urllib.parse.urlencode(
        {"id": args.erp_warehouse_source_id}
    )
    source = client.request("GET", source_path)
    require(str(source.get("id")) == args.erp_warehouse_source_id,
            "ERP warehouse read did not return the requested source ID")
    require(source.get("status") in (0, "0", None), "ERP warehouse source is not enabled")
    ledger.value["source_refs"]["erp"]["validated"] = True
    ledger.flush()

    identity_reference = {
        "sourceSystem": "SYSTEM",
        "sourceType": "SYSTEM_ADMIN_USER",
        "sourceId": args.system_admin_source_id,
    }
    identity_reused = False
    try:
        identity = client.request("POST", IDENTITY_RESOLVE_ROUTE, identity_reference)
        ledger.append("identity", "RESOLVE_ACTIVE_SOURCE", identity_reference, identity)
        identity_reused = True
    except ScenarioError:
        identity = None

    identity_payload = {
        "idempotencyKey": f"{args.run_id}-identity-system-admin",
        "runId": args.run_id,
        "principalType": "PLATFORM_OPERATOR",
        "sourceSystem": "SYSTEM",
        "sourceType": "SYSTEM_ADMIN_USER",
        "sourceId": args.system_admin_source_id,
        "correlationId": correlation_id,
        "occurredAt": iso_time(occurred_at),
    }
    if identity is None:
        identity = issue("identity", "LINK_SOURCE", IDENTITY_ROUTE, identity_payload)
    principal_id = identity.get("principalId")
    require(isinstance(principal_id, str) and principal_id != args.system_admin_source_id,
            "canonical Principal must exist and differ from the System source ID")
    principal_version = identity.get("principalVersion", identity.get("aggregateVersion"))
    require(identity.get("principalStatus") == "ACTIVE" and principal_version == 1,
            "canonical Principal did not resolve as ACTIVE/v1")

    digest = hashlib.sha256(args.run_id.encode()).hexdigest()
    commands: list[dict] = []
    commands.append(merchant_command(
        "CREATE_ONBOARDING_DRAFT", args.run_id, 1, correlation_id, occurred_at,
        legalName=f"Y-Shopping internal fixture {args.run_id}",
        registrationHashToken="sha256:" + digest,
        businessLicenseToken="token:" + args.run_id,
        ownerPrincipalId=principal_id,
        channelCode="YSHOPPING_INTERNAL",
        externalShopId=f"YS-{args.run_id}",
    ))
    draft = issue("merchant", "CREATE_ONBOARDING_DRAFT", MERCHANT_ROUTE, commands[-1])
    application_id = draft.get("applicationId")
    require(draft.get("onboardingStatus") == "DRAFT" and draft.get("applicationVersion") == 1,
            "merchant onboarding did not start DRAFT/v1")
    for index, (operation, expected_version, expected_status) in enumerate((
        ("SUBMIT_ONBOARDING", 1, "SUBMITTED"),
        ("START_ONBOARDING_REVIEW", 2, "UNDER_REVIEW"),
        ("APPROVE_ONBOARDING", 3, "APPROVED"),
    ), 2):
        commands.append(merchant_command(
            operation, args.run_id, index, correlation_id, occurred_at,
            applicationId=application_id, expectedVersion=expected_version,
        ))
        result = issue("merchant", operation, MERCHANT_ROUTE, commands[-1])
        require(result.get("onboardingStatus") == expected_status
                and result.get("applicationVersion") == expected_version + 1,
                f"merchant onboarding {operation} invariant failed")
    approved = result
    merchant_id = approved.get("merchantId")
    shop_id = approved.get("shopId")
    legal_entity_id = approved.get("legalEntityId")
    require(all(isinstance(value, str) for value in (merchant_id, shop_id, legal_entity_id)),
            "approved onboarding did not create canonical entity IDs")
    require(len({principal_id, merchant_id, shop_id, legal_entity_id}) == 4,
            "Principal, Merchant, Shop, and LegalEntity IDs must be distinct")
    commands.append(merchant_command(
        "ACTIVATE_MERCHANT", args.run_id, 5, correlation_id, occurred_at,
        merchantId=merchant_id, expectedVersion=1,
    ))
    merchant = issue("merchant", "ACTIVATE_MERCHANT", MERCHANT_ROUTE, commands[-1])
    require(merchant.get("merchantStatus") == "ACTIVE" and merchant.get("merchantVersion") == 2,
            "Merchant did not reach ACTIVE/v2")
    commands.append(merchant_command(
        "ACTIVATE_SHOP", args.run_id, 6, correlation_id, occurred_at,
        shopId=shop_id, expectedVersion=1,
    ))
    shop = issue("merchant", "ACTIVATE_SHOP", MERCHANT_ROUTE, commands[-1])
    require(shop.get("shopStatus") == "ACTIVE" and shop.get("shopVersion") == 2,
            "Shop did not reach ACTIVE/v2")

    listing_id = None
    listing_status = "DEFERRED_TO_COMMERCE"
    if args.listing_mode == "proof":
        listing_payload = {
            "operation": "CREATE_DRAFT",
            "idempotencyKey": f"{args.run_id}-listing-01-create-draft",
            "runId": args.run_id,
            "merchantId": merchant_id,
            "channelCode": "YSHOPPING_INTERNAL",
            "shopId": shop_id,
            "canonicalSpuId": canonical_spu_id,
            "title": f"Y-Shopping authorized listing {args.run_id}",
            "categoryRef": "INTERNAL:CATEGORY:DRESS",
            "brandRef": "INTERNAL:BRAND:YSHOPPING",
            "sourceSystem": "cloudmold-erp-operator",
            "publisherRef": principal_id,
            "publishStartAt": "2026-06-30T00:00:00Z",
            "offers": [{
                "canonicalSkuId": canonical_sku_id,
                "priceMinor": 19900,
                "currencyCode": "CNY",
                "enabled": True,
                "externalOfferId": f"authorized-offer:{args.run_id}",
            }],
            "reason": "canonical merchant authorization first slice",
            "correlationId": correlation_id,
            "occurredAt": iso_time(occurred_at + dt.timedelta(seconds=200)),
        }
        listing = issue("listing", "CREATE_DRAFT", LISTING_ROUTE, listing_payload)
        listing_id = listing.get("listingId")
        require(listing.get("currentStatus") == "DRAFT" and listing.get("aggregateVersion") == 1,
                "authorized Listing did not start DRAFT/v1")
        for index, (operation, expected_status) in enumerate((
            ("SUBMIT", "SUBMITTED"),
            ("PASS_COMPLETION", "COMPLETION_PASSED"),
            ("APPROVE_BUSINESS", "BUSINESS_APPROVED"),
            ("APPROVE_RISK", "RISK_APPROVED"),
            ("PUBLISH", "PUBLISHED"),
        ), 2):
            payload = {
                "operation": operation,
                "idempotencyKey": f"{args.run_id}-listing-{index:02d}-{operation.lower().replace('_', '-')}",
                "runId": args.run_id,
                "listingId": listing_id,
                "expectedVersion": index - 1,
                "reason": f"canonical merchant authorization {operation.lower()}",
                "correlationId": correlation_id,
                "occurredAt": iso_time(occurred_at + dt.timedelta(seconds=199 + index)),
            }
            if operation == "PUBLISH":
                payload["publisherRef"] = principal_id
            listing = issue("listing", operation, LISTING_ROUTE, payload)
            require(listing.get("currentStatus") == expected_status
                    and listing.get("aggregateVersion") == index,
                    f"authorized Listing {operation} invariant failed")
        listing_status = "PUBLISHED"

    warehouse_reference = {
        "sourceSystem": "ERP", "sourceType": "WAREHOUSE",
        "sourceId": args.erp_warehouse_source_id,
    }
    warehouse_network_reused = False
    try:
        network = client.request("POST", WAREHOUSE_RESOLVE_ROUTE, warehouse_reference)
        ledger.append("warehouse", "RESOLVE_READY_NETWORK", warehouse_reference, network)
        warehouse_network_reused = True
    except ScenarioError:
        network = None

    if network is not None:
        warehouse_id = network.get("warehouseId")
        zone_id = network.get("zoneId")
        location_id = network.get("locationId")
        require(network.get("warehouseStatus") == "ACTIVE"
                and network.get("zoneStatus") == "ACTIVE"
                and network.get("locationStatus") == "ACTIVE"
                and all(isinstance(value, str) and value
                        for value in (warehouse_id, zone_id, location_id)),
                "resolved canonical Warehouse network is not ready")
    else:
        warehouse_commands: list[dict] = []
        warehouse_commands.append(base_command(
            "DEFINE_WAREHOUSE", args.run_id, 1, correlation_id, occurred_at))
        warehouse_commands[-1]["warehouse"] = {
            "warehouseCode": "CM-" + digest[:12].upper(),
            "name": f"Y-Shopping run-scoped warehouse {args.run_id}",
            "warehouseType": "FULFILLMENT", "timezone": "Asia/Shanghai",
        }
        warehouse = issue("warehouse", "DEFINE_WAREHOUSE", WAREHOUSE_ROUTE, warehouse_commands[-1])
        warehouse_id = warehouse.get("warehouseId")
        require(isinstance(warehouse_id, str) and warehouse_id != args.erp_warehouse_source_id,
                "canonical Warehouse must differ from the ERP source ID")
        warehouse_commands.append(base_command(
            "CHANGE_WAREHOUSE_STATUS", args.run_id, 2, correlation_id, occurred_at))
        warehouse_commands[-1]["warehouse"] = {
            "warehouseId": warehouse_id, "status": "ACTIVE", "expectedVersion": 1,
        }
        warehouse = issue("warehouse", "CHANGE_WAREHOUSE_STATUS", WAREHOUSE_ROUTE,
                          warehouse_commands[-1])
        require(warehouse.get("status") == "ACTIVE" and warehouse.get("aggregateVersion") == 2,
                "Warehouse did not reach ACTIVE/v2")

        warehouse_commands.append(base_command(
            "DEFINE_ZONE", args.run_id, 3, correlation_id, occurred_at))
        warehouse_commands[-1]["zone"] = {
            "warehouseId": warehouse_id, "zoneCode": "PICK-01", "name": "Pick zone 01",
            "zoneType": "PICKING",
        }
        zone = issue("warehouse", "DEFINE_ZONE", WAREHOUSE_ROUTE, warehouse_commands[-1])
        zone_id = zone.get("zoneId")
        warehouse_commands.append(base_command(
            "CHANGE_ZONE_STATUS", args.run_id, 4, correlation_id, occurred_at))
        warehouse_commands[-1]["zone"] = {
            "zoneId": zone_id, "status": "ACTIVE", "expectedVersion": 1,
        }
        zone = issue("warehouse", "CHANGE_ZONE_STATUS", WAREHOUSE_ROUTE, warehouse_commands[-1])
        require(zone.get("status") == "ACTIVE" and zone.get("aggregateVersion") == 2,
                "Zone did not reach ACTIVE/v2")

        warehouse_commands.append(base_command(
            "DEFINE_LOCATION", args.run_id, 5, correlation_id, occurred_at))
        warehouse_commands[-1]["location"] = {
            "warehouseId": warehouse_id, "zoneId": zone_id,
            "locationCode": "A01-R01-B01-L01", "name": "A01 R01 B01 L01",
            "locationType": "PICK_FACE", "aisleCode": "A01", "rackCode": "R01",
            "bayCode": "B01", "levelCode": "L01", "allowItemMixing": False,
            "allowLotMixing": False, "capacityQuantity": "1000", "capacityUomCode": "PCS",
        }
        location = issue("warehouse", "DEFINE_LOCATION", WAREHOUSE_ROUTE,
                         warehouse_commands[-1])
        location_id = location.get("locationId")
        warehouse_commands.append(base_command(
            "CHANGE_LOCATION_STATUS", args.run_id, 6, correlation_id, occurred_at))
        warehouse_commands[-1]["location"] = {
            "locationId": location_id, "status": "ACTIVE", "expectedVersion": 1,
        }
        location = issue("warehouse", "CHANGE_LOCATION_STATUS", WAREHOUSE_ROUTE,
                         warehouse_commands[-1])
        require(location.get("status") == "ACTIVE" and location.get("aggregateVersion") == 2,
                "Location did not reach ACTIVE/v2")

        warehouse_commands.append(base_command(
            "LINK_SOURCE", args.run_id, 7, correlation_id, occurred_at))
        warehouse_commands[-1]["sourceMapping"] = {
            "sourceSystem": "ERP", "sourceType": "WAREHOUSE",
            "sourceId": args.erp_warehouse_source_id, "targetType": "WAREHOUSE",
            "warehouseId": warehouse_id, "validFrom": iso_time(occurred_at),
            "verificationRef": f"erp_warehouse:{args.erp_warehouse_source_id}:admin-rest:{args.run_id}",
        }
        mapping = issue("warehouse", "LINK_SOURCE", WAREHOUSE_ROUTE, warehouse_commands[-1])
        require(mapping.get("status") == "ACTIVE" and mapping.get("warehouseId") == warehouse_id,
                "ERP warehouse source mapping is not ACTIVE or targets the wrong Warehouse")

        warehouse_commands.append(base_command(
            "ASSIGN_OPERATOR", args.run_id, 8, correlation_id, occurred_at))
        warehouse_commands[-1]["operatorAssignment"] = {
            "warehouseId": warehouse_id, "zoneId": zone_id, "locationId": location_id,
            "principalId": principal_id, "roleCode": "OWNER", "shiftCode": "DAY",
            "validFrom": iso_time(occurred_at),
        }
        assignment = issue("warehouse", "ASSIGN_OPERATOR", WAREHOUSE_ROUTE,
                           warehouse_commands[-1])
        require(assignment.get("status") == "ACTIVE"
                and assignment.get("warehouseId") == warehouse_id,
                "warehouse operator assignment is not ACTIVE")

    replay_results = []
    for domain, operation, payload, first in issued:
        route = {"identity": IDENTITY_ROUTE, "merchant": MERCHANT_ROUTE,
                 "listing": LISTING_ROUTE, "warehouse": WAREHOUSE_ROUTE}[domain]
        replay = client.request("POST", route, payload)
        require(replay.get("duplicate") is True, f"{domain} {operation} replay was not duplicate")
        expected = {key: value for key, value in first.items() if key != "duplicate"}
        actual = {key: value for key, value in replay.items() if key != "duplicate"}
        require(actual == expected, f"{domain} {operation} replay changed the immutable result")
        replay_results.append({"domain": domain, "operation": operation, "duplicate": True})

    final = {
        "principal_id": principal_id,
        "merchant_id": merchant_id,
        "shop_id": shop_id,
        "legal_entity_id": legal_entity_id,
        "warehouse_id": warehouse_id,
        "zone_id": zone_id,
        "location_id": location_id,
        "source_identity": {"source_system": "SYSTEM", "source_type": "SYSTEM_ADMIN_USER",
                            "source_id": args.system_admin_source_id},
        "source_identity_reused": identity_reused,
        "warehouse_source": {"source_system": "ERP", "source_type": "WAREHOUSE",
                             "source_id": args.erp_warehouse_source_id},
        "warehouse_network_reused": warehouse_network_reused,
        "merchant_status": "ACTIVE",
        "shop_status": "ACTIVE",
        "warehouse_status": "ACTIVE",
        "listing_id": listing_id,
        "listing_status": listing_status,
        "listing_mode": args.listing_mode,
        "canonical_sku_id": canonical_sku_id,
        "canonical_spu_id": canonical_spu_id,
        "catalog_ledger": catalog_ledger,
        "all_replay_duplicate": len(replay_results) == len(issued),
        "write_command_count": len(issued),
    }
    expected_writes = (21 - int(identity_reused) - (8 if warehouse_network_reused else 0)
                       - (6 if args.listing_mode == "defer" else 0))
    require(final["write_command_count"] == expected_writes,
            f"scenario must issue exactly {expected_writes} public write commands")
    ledger.value["replay"] = replay_results
    ledger.value["final"] = final
    ledger.value["status"] = "SUCCEEDED"
    ledger.flush()
    return {"status": "succeeded", "run_id": args.run_id, "ledger": str(ledger.path), **final}


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
    parser.add_argument("--system-admin-source-id", default=os.getenv("CLOUDMOLD_SYSTEM_ADMIN_SOURCE_ID"))
    parser.add_argument("--erp-warehouse-source-id", default=os.getenv("CLOUDMOLD_ERP_WAREHOUSE_SOURCE_ID"))
    parser.add_argument("--catalog-ledger", default=os.getenv("CLOUDMOLD_CATALOG_LEDGER"))
    parser.add_argument("--listing-mode", choices=("proof", "defer"), default="proof")
    parser.add_argument("--timeout", type=int, default=20)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        require(bool(RUN_ID_PATTERN.fullmatch(args.run_id)),
                "run_id must be 6-32 characters using letters, digits, dot, underscore, or hyphen")
        require(args.environment in {"local", "demo", "test"},
                "the runner is restricted to local, demo, or test")
        if args.mode == "plan":
            result = {
                "scenario": "canonical-merchant-warehouse-first-slice-v1",
                "run_id": args.run_id,
                "flow": [
                    "validate real System admin and ERP warehouse source references",
                    "link System account to a distinct canonical Principal",
                    "reuse an existing ACTIVE source link or create it once when absent",
                    "approve and activate one Merchant/Shop with exact OWNER assignment",
                    "publish one Listing through the exact canonical Principal and OWNER assignment",
                    "define and activate one Warehouse/Zone/Location",
                    "reuse an existing ready canonical Warehouse network or create it once when absent",
                    "map the exact ERP warehouse and assign the canonical Principal",
                    "replay all 12, 13, 20, or 21 public writes as immutable duplicates, depending on safe master-data reuse",
                ],
                "side_effects": False,
            }
        elif args.mode == "dry-run":
            paths = Client(args.base_url, args.tenant, args.token, args.timeout).openapi().get("paths", {})
            required = {
                IDENTITY_ROUTE: "post", IDENTITY_RESOLVE_ROUTE: "post",
                MERCHANT_ROUTE: "post", LISTING_ROUTE: "post",
                WAREHOUSE_ROUTE: "post", WAREHOUSE_RESOLVE_ROUTE: "post",
                ERP_WAREHOUSE_ROUTE: "get",
            }
            missing = [f"{method.upper()} {path}" for path, method in required.items()
                       if method not in paths.get(path, {})]
            require(not missing, "live OpenAPI is missing " + ", ".join(missing))
            result = {"status": "ready", "routes": required, "side_effects": False}
        else:
            require(args.tenant > 0, "tenant must be positive")
            require(bool(args.system_admin_source_id)
                    and bool(SOURCE_ID_PATTERN.fullmatch(args.system_admin_source_id)),
                    "execute requires a safe --system-admin-source-id")
            require(bool(args.erp_warehouse_source_id)
                    and bool(SOURCE_ID_PATTERN.fullmatch(args.erp_warehouse_source_id)),
                    "execute requires a safe --erp-warehouse-source-id")
            result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ScenarioError as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
