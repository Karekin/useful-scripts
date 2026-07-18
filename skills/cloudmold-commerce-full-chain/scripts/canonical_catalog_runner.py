#!/usr/bin/env python3
"""Deterministic Agent runner for the canonical apparel Catalog first slice."""

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


ROUTE = "/admin-api/cloudmold/catalog/sku/define"
LIFECYCLE_ROUTE = "/admin-api/cloudmold/catalog/lifecycle"
COLORS = (("BLACK", "黑色"), ("WHITE", "白色"))
SIZES = (("S", "S", 10), ("M", "M", 20), ("L", "L", 30))


class ScenarioError(RuntimeError):
    pass


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


def scenario_identity(run_id: str) -> tuple[str, str, dt.datetime]:
    digest = hashlib.sha256(run_id.encode()).hexdigest()
    style_code = "YS-" + digest[:8].upper()
    correlation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:catalog:{run_id}"))
    seconds = int(digest[8:16], 16) % (365 * 24 * 60 * 60)
    occurred_at = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=seconds)
    return style_code, correlation_id, occurred_at


def build_payloads(run_id: str) -> list[dict]:
    style_code, correlation_id, occurred_at = scenario_identity(run_id)
    payloads = []
    matrix = ((color, size) for color in COLORS for size in SIZES)
    for index, ((color_code, color_name), (size_code, size_name, size_sort)) in enumerate(matrix, 1):
        sku_code = f"{style_code}-{color_code}-{size_code}"
        payloads.append({
            "idempotencyKey": f"{run_id}-catalog-{color_code.lower()}-{size_code.lower()}",
            "styleCode": style_code, "styleName": f"语兴好物 {run_id} 连衣裙",
            "planningCategoryRef": "INTERNAL:CATEGORY:DRESS",
            "brandRef": "INTERNAL:BRAND:YSHOPPING", "planningYear": 2026,
            "seasonCode": "SUMMER", "waveCode": "WAVE-01", "spuCode": style_code,
            "productName": f"语兴好物 {run_id} 连衣裙",
            "salesCategoryRef": "INTERNAL:CATEGORY:DRESS", "skuCode": sku_code,
            "barcode": f"CM-{run_id}-{color_code}-{size_code}"[:64], "barcodeType": "CODE128",
            "colorCode": color_code, "colorName": color_name, "sizeGroupCode": "WOMEN_TOP",
            "sizeGroupName": "女装上衣尺码", "sizeCode": size_code, "sizeName": size_name,
            "sizeSort": size_sort, "baseUomCode": "PCS", "status": "DRAFT",
            "correlationId": correlation_id,
            "occurredAt": (occurred_at + dt.timedelta(seconds=index)).isoformat().replace("+00:00", "Z"),
        })
    return payloads


def request_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def remember_state(states: dict[str, tuple[str, int]], entity_id: str,
                   status: object, version: object, entity_type: str) -> None:
    if not isinstance(status, str) or not isinstance(version, int):
        raise ScenarioError(f"Catalog definition result is missing {entity_type} lifecycle state")
    value = (status, version)
    previous = states.setdefault(entity_id, value)
    if previous != value:
        raise ScenarioError(f"Catalog {entity_type} state changed during matrix definition")


def execute(args: argparse.Namespace) -> dict:
    client = Client(args.base_url, args.tenant, args.token, args.timeout)
    if not client.token:
        if not args.username or not args.password:
            raise ScenarioError("set token or username/password through environment variables")
        client.login(args.username, args.password)
    payloads = build_payloads(args.run_id)
    ledger = {"scenario": "canonical-catalog-first-slice-v1", "run_id": args.run_id,
              "environment": args.environment, "tenant": args.tenant, "steps": []}
    style_ids, spu_ids, sku_ids = set(), set(), set()
    color_ids, size_group_ids, size_ids = set(), set(), set()
    style_states, spu_states, sku_states = {}, {}, {}
    color_states, size_group_states, size_states = {}, {}, {}
    for index, payload in enumerate(payloads, 1):
        result = client.request("POST", ROUTE, payload)
        if result.get("aggregateVersion") != 1 or not (result.get("created") or result.get("duplicate")):
            raise ScenarioError(f"Catalog result invariant mismatch at step {index}: {result}")
        style_ids.add(result["canonicalStyleId"]); spu_ids.add(result["canonicalSpuId"])
        sku_ids.add(result["canonicalSkuId"])
        color_ids.add(result["colorId"]); size_group_ids.add(result["sizeGroupId"])
        size_ids.add(result["sizeId"])
        remember_state(style_states, result["canonicalStyleId"], result.get("styleStatus"),
                       result.get("styleVersion"), "Style")
        remember_state(spu_states, result["canonicalSpuId"], result.get("spuStatus"),
                       result.get("spuVersion"), "SPU")
        remember_state(sku_states, result["canonicalSkuId"], result.get("skuStatus"),
                       result.get("aggregateVersion"), "SKU")
        remember_state(color_states, result["colorId"], result.get("colorStatus"),
                       result.get("colorVersion"), "Color")
        remember_state(size_group_states, result["sizeGroupId"], result.get("sizeGroupStatus"),
                       result.get("sizeGroupVersion"), "SizeGroup")
        remember_state(size_states, result["sizeId"], result.get("sizeStatus"),
                       result.get("sizeVersion"), "Size")
        ledger["steps"].append({"step": index, "sku_code": payload["skuCode"],
                                "request_hash": request_hash(payload), "result": result})
    if len(style_ids) != 1 or len(spu_ids) != 1 or len(sku_ids) != 6:
        raise ScenarioError("2-color x 3-size matrix did not resolve to one Style, one SPU, and six SKUs")
    if len(color_ids) != 2 or len(size_group_ids) != 1 or len(size_ids) != 3:
        raise ScenarioError("Catalog color/size identity matrix is inconsistent")

    style_id, spu_id = next(iter(style_ids)), next(iter(spu_ids))
    lifecycle_specs = []

    def activate_drafts(entity_type: str, states: dict[str, tuple[str, int]]) -> None:
        for entity_id, (status, version) in sorted(states.items()):
            if status == "DRAFT":
                lifecycle_specs.append((entity_type, entity_id, "ACTIVATE", version))
            elif status != "ACTIVE":
                raise ScenarioError(f"shared Catalog {entity_type} must be DRAFT or ACTIVE, got {status}")

    activate_drafts("STYLE", style_states)
    activate_drafts("COLOR", color_states)
    activate_drafts("SIZE_GROUP", size_group_states)
    activate_drafts("SIZE", size_states)
    spu_status, spu_version = spu_states[spu_id]
    if spu_status != "DRAFT":
        raise ScenarioError(f"run-scoped Catalog SPU must start DRAFT, got {spu_status}")
    lifecycle_specs += [("SPU", spu_id, "SUBMIT", spu_version),
                        ("SPU", spu_id, "APPROVE", spu_version + 1)]
    activate_drafts("SKU", sku_states)
    lifecycle_specs += [("SPU", spu_id, "ACTIVATE", spu_version + 2)]
    lifecycle_results = []
    for index, (entity_type, entity_id, action, expected_version) in enumerate(lifecycle_specs, 1):
        lifecycle_payload = {
            "entityType": entity_type, "entityId": entity_id, "action": action,
            "expectedVersion": expected_version,
            "idempotencyKey": f"{args.run_id}-lifecycle-{index}-{entity_type.lower()}-{action.lower()}",
            "reason": f"canonical-catalog-first-slice-v1:{args.run_id}",
            "correlationId": payloads[0]["correlationId"],
            "occurredAt": (scenario_identity(args.run_id)[2] + dt.timedelta(seconds=100 + index))
                .isoformat().replace("+00:00", "Z"),
        }
        result = client.request("POST", LIFECYCLE_ROUTE, lifecycle_payload)
        if result.get("aggregateVersion") != expected_version + 1:
            raise ScenarioError(f"Catalog lifecycle version mismatch at step {index}: {result}")
        lifecycle_results.append({"step": index, "entity_type": entity_type, "action": action,
                                  "request_hash": request_hash(lifecycle_payload), "result": result})
    ledger["lifecycle"] = lifecycle_results
    ledger["final"] = {"style_id": next(iter(style_ids)), "spu_id": next(iter(spu_ids)),
                       "sku_ids": sorted(sku_ids), "style_code": payloads[0]["styleCode"],
                       "sku_count": 6, "color_count": 2, "size_count": 3,
                       "lifecycle_steps": len(lifecycle_specs), "catalog_status": "ACTIVE"}
    run_root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    output = run_root / "catalog" / args.run_id / "ledger.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        suffix = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = output.parent / f"replay-ledger-{suffix}.json"
    output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
    return {"status": "succeeded", "run_id": args.run_id, "ledger": str(output), **ledger["final"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "dry-run", "execute"), required=True)
    parser.add_argument("--run-id", required=True); parser.add_argument("--environment", default="local")
    parser.add_argument("--base-url", default=os.getenv("CLOUDMOLD_ERP_BASE_URL", "http://127.0.0.1:48080"))
    parser.add_argument("--tenant", type=int, default=int(os.getenv("CLOUDMOLD_TENANT_ID", "1")))
    parser.add_argument("--token", default=os.getenv("CLOUDMOLD_ADMIN_TOKEN"))
    parser.add_argument("--username", default=os.getenv("CLOUDMOLD_ADMIN_USERNAME"))
    parser.add_argument("--password", default=os.getenv("CLOUDMOLD_ADMIN_PASSWORD"))
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        if args.mode == "plan":
            result = {"scenario": "canonical-catalog-first-slice-v1", "run_id": args.run_id,
                      "matrix": {"colors": 2, "sizes": 3, "skus": 6}, "side_effects": False}
        elif args.mode == "dry-run":
            paths = Client(args.base_url, args.tenant, args.token, args.timeout).openapi().get("paths", {})
            missing = [route for route in (ROUTE, LIFECYCLE_ROUTE)
                       if route not in paths or "post" not in paths[route]]
            if missing:
                raise ScenarioError(f"live OpenAPI is missing {missing}")
            result = {"status": "ready", "routes": [ROUTE, LIFECYCLE_ROUTE], "side_effects": False}
        else:
            result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    except ScenarioError as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr); return 1


if __name__ == "__main__":
    raise SystemExit(main())
