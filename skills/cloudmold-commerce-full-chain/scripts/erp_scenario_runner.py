#!/usr/bin/env python3
"""Deterministic CloudMold ERP scenario runner using only the Python stdlib."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any


PROCESS = 10
APPROVE = 20
PURCHASE_IN = 70
PURCHASE_IN_CANCEL = 71
SCENARIO = "purchase-to-stock-v1"


class ScenarioError(RuntimeError):
    pass


def decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


def local_time(offset_minutes: int = 0) -> str:
    value = dt.datetime.now().astimezone().replace(microsecond=0) + dt.timedelta(minutes=offset_minutes)
    return value.replace(tzinfo=None).isoformat()


def request_hash(method: str, path: str, payload: Any) -> str:
    raw = json.dumps([method, path, payload], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


class Ledger:
    def __init__(self, path: Path, metadata: dict[str, Any] | None = None):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {"metadata": metadata or {}, "resources": {}, "entries": [], "reconciliation": {}}
            self.save()

    def save(self) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        temp.replace(self.path)

    def record(self, action: str, method: str, path: str, payload: Any, response: Any) -> None:
        self.data["entries"].append({
            "at": utc_now(), "action": action, "method": method, "path": path,
            "request_sha256": request_hash(method, path, payload), "response": response,
        })
        self.save()

    def resource(self, name: str, resource_id: int) -> int:
        self.data["resources"][name] = resource_id
        self.save()
        return resource_id


class ErpClient:
    def __init__(self, base_url: str, tenant_id: str, token: str | None = None, timeout: int = 20):
        self.base_url = base_url.rstrip("/")
        self.tenant_id = tenant_id
        self.token = token
        self.timeout = timeout

    def _request(self, method: str, path: str, *, payload: Any = None,
                 query: dict[str, Any] | None = None, authenticated: bool = True) -> Any:
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query, doseq=True)
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
        headers = {"Accept": "application/json", "tenant-id": self.tenant_id}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if authenticated:
            if not self.token:
                raise ScenarioError("authenticated request requires a token")
            headers["Authorization"] = "Bearer " + self.token
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode()
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            raise ScenarioError(f"HTTP {exc.code} {method} {path}: {raw[:500]}") from exc
        except urllib.error.URLError as exc:
            raise ScenarioError(f"cannot reach {self.base_url}: {exc.reason}") from exc
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ScenarioError(f"non-JSON response from {method} {path}") from exc
        if not isinstance(result, dict) or result.get("code") != 0:
            raise ScenarioError(f"API rejected {method} {path}: code={result.get('code')} msg={result.get('msg')}")
        return result.get("data")

    def login(self, username: str, password: str) -> None:
        data = self._request("POST", "/admin-api/system/auth/login",
                             payload={"username": username, "password": password}, authenticated=False)
        self.token = data["accessToken"]

    def openapi(self) -> dict[str, Any]:
        url = self.base_url + "/v3/api-docs"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                result = json.loads(response.read().decode())
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise ScenarioError(f"cannot read live OpenAPI from {url}: {exc}") from exc
        if not isinstance(result, dict) or not isinstance(result.get("paths"), dict):
            raise ScenarioError("live OpenAPI does not contain a paths object")
        return result

    def get(self, path: str, query: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, query=query)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request("POST", path, payload=payload)

    def put(self, path: str, query: dict[str, Any]) -> Any:
        return self._request("PUT", path, query=query)

    def delete(self, path: str, query: dict[str, Any]) -> Any:
        return self._request("DELETE", path, query=query)


def source_commit(repo: str | None) -> str | None:
    if not repo:
        return None
    try:
        return subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def scenario_plan(run_id: str) -> list[dict[str, str]]:
    return [
        {"step": "preflight", "effect": "verify source commit, live OpenAPI, tenant and operator"},
        {"step": "fixtures", "effect": "create unit, category, product, supplier, warehouse and account"},
        {"step": "purchase_order", "effect": "create, read back and approve 10 -> 20"},
        {"step": "purchase_receipt", "effect": "create draft; verify order inCount and unchanged stock"},
        {"step": "stock", "effect": "approve receipt; verify stock and biz_type=70 movement"},
        {"step": "cleanup", "effect": "explicit only: reverse receipt, verify biz_type=71, then logical-delete ledger resources"},
        {"step": "identity", "effect": f"embed run_id={run_id} in every fixture"},
    ]


def require_run_id(value: str | None) -> str:
    value = value or dt.datetime.now().strftime("%Y%m%d%H%M%S")
    if not re.fullmatch(r"[A-Za-z0-9-]{6,32}", value):
        raise ScenarioError("run_id must be 6-32 ASCII letters, digits or hyphens")
    return value


def api(client: ErpClient, ledger: Ledger, action: str, method: str, path: str,
        payload: dict[str, Any] | None = None, query: dict[str, Any] | None = None) -> Any:
    if method == "GET":
        result = client.get(path, query)
    elif method == "POST":
        result = client.post(path, payload or {})
    elif method == "PUT":
        result = client.put(path, query or {})
    elif method == "DELETE":
        result = client.delete(path, query or {})
    else:
        raise ScenarioError(f"unsupported method {method}")
    ledger.record(action, method, path, payload if payload is not None else query, result)
    return result


def assert_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ScenarioError(f"{label}: expected {expected!r}, got {actual!r}")


def verify_openapi(document: dict[str, Any]) -> str:
    required = {
        "/admin-api/erp/purchase-order/create": "post",
        "/admin-api/erp/purchase-order/get": "get",
        "/admin-api/erp/purchase-order/update-status": "put",
        "/admin-api/erp/purchase-order/delete": "delete",
        "/admin-api/erp/purchase-in/create": "post",
        "/admin-api/erp/purchase-in/get": "get",
        "/admin-api/erp/purchase-in/update-status": "put",
        "/admin-api/erp/purchase-in/delete": "delete",
        "/admin-api/erp/stock/get": "get",
        "/admin-api/erp/stock-record/page": "get",
    }
    paths = document["paths"]
    missing = [f"{method.upper()} {path}" for path, method in required.items()
               if path not in paths or method not in paths[path]]
    if missing:
        raise ScenarioError("live OpenAPI route drift: " + ", ".join(missing))
    canonical = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def execute(client: ErpClient, ledger: Ledger, run_id: str, quantity: Decimal) -> None:
    prefix = f"CM-{run_id}"
    enabled = 0
    unit = ledger.resource("unit", int(api(client, ledger, "create_unit", "POST", "/admin-api/erp/product-unit/create",
        {"name": f"{prefix}-件", "status": enabled})))
    category = ledger.resource("category", int(api(client, ledger, "create_category", "POST", "/admin-api/erp/product-category/create",
        {"parentId": 0, "name": f"{prefix}-服饰", "code": f"{prefix}-APPAREL", "sort": 1, "status": enabled})))
    product = ledger.resource("product", int(api(client, ledger, "create_product", "POST", "/admin-api/erp/product/create", {
        "name": f"{prefix}-测试款", "barCode": f"{prefix}-BLACK-M", "categoryId": category, "unitId": unit,
        "status": enabled, "standard": "黑色/M", "remark": f"run_id={run_id}", "weight": "0.50",
        "purchasePrice": "100.00", "salePrice": "159.00", "minPrice": "100.00",
    })))
    supplier = ledger.resource("supplier", int(api(client, ledger, "create_supplier", "POST", "/admin-api/erp/supplier/create",
        {"name": f"{prefix}-供应商", "status": enabled, "sort": 1, "remark": f"run_id={run_id}", "taxPercent": "0"})))
    warehouse = ledger.resource("warehouse", int(api(client, ledger, "create_warehouse", "POST", "/admin-api/erp/warehouse/create",
        {"name": f"{prefix}-仓库", "sort": 1, "status": enabled, "remark": f"run_id={run_id}", "warehousePrice": "0", "truckagePrice": "0"})))
    account = ledger.resource("account", int(api(client, ledger, "create_account", "POST", "/admin-api/erp/account/create",
        {"name": f"{prefix}-结算账户", "no": f"{prefix}-ACCOUNT", "status": enabled, "sort": 1, "remark": f"run_id={run_id}"})))

    for name, path, rid in [
        ("unit", "/admin-api/erp/product-unit/get", unit), ("category", "/admin-api/erp/product-category/get", category),
        ("product", "/admin-api/erp/product/get", product), ("supplier", "/admin-api/erp/supplier/get", supplier),
        ("warehouse", "/admin-api/erp/warehouse/get", warehouse), ("account", "/admin-api/erp/account/get", account),
    ]:
        found = api(client, ledger, f"verify_{name}", "GET", path, query={"id": rid})
        assert_equal(int(found["id"]), rid, f"{name} readback")
        if found.get("status") is not None:
            assert_equal(found["status"], enabled, f"{name} enabled status")

    baseline = decimal(api(client, ledger, "read_stock_baseline", "GET", "/admin-api/erp/stock/get-count", query={"productId": product}))
    order_payload = {
        "supplierId": supplier, "accountId": account, "orderTime": local_time(), "discountPercent": "0",
        "depositPrice": "0", "remark": f"run_id={run_id}", "items": [{"productId": product,
        "productUnitId": unit, "productPrice": "100.00", "count": str(quantity), "taxPercent": "0", "remark": f"run_id={run_id}"}],
    }
    order = ledger.resource("purchase_order", int(api(client, ledger, "create_purchase_order", "POST", "/admin-api/erp/purchase-order/create", order_payload)))
    order_data = api(client, ledger, "verify_purchase_order_draft", "GET", "/admin-api/erp/purchase-order/get", query={"id": order})
    assert_equal(order_data["status"], PROCESS, "purchase order draft status")
    assert_equal(decimal(order_data["totalCount"]), quantity, "purchase order total count")
    if len(order_data.get("items", [])) != 1:
        raise ScenarioError("purchase order must contain exactly one server-side item")
    order_item = ledger.resource("purchase_order_item", int(order_data["items"][0]["id"]))
    assert_equal(int(order_data["items"][0]["productId"]), product, "order item product")
    api(client, ledger, "approve_purchase_order", "PUT", "/admin-api/erp/purchase-order/update-status", query={"id": order, "status": APPROVE})
    order_data = api(client, ledger, "verify_purchase_order_approved", "GET", "/admin-api/erp/purchase-order/get", query={"id": order})
    assert_equal(order_data["status"], APPROVE, "purchase order approved status")

    receipt_payload = {
        "accountId": account, "inTime": local_time(1), "orderId": order, "discountPercent": "0", "otherPrice": "0",
        "remark": f"run_id={run_id}", "items": [{"orderItemId": order_item, "warehouseId": warehouse,
        "productId": product, "productUnitId": unit, "productPrice": "100.00", "count": str(quantity),
        "taxPercent": "0", "remark": f"run_id={run_id}"}],
    }
    receipt = ledger.resource("purchase_receipt", int(api(client, ledger, "create_purchase_receipt", "POST", "/admin-api/erp/purchase-in/create", receipt_payload)))
    receipt_data = api(client, ledger, "verify_purchase_receipt_draft", "GET", "/admin-api/erp/purchase-in/get", query={"id": receipt})
    assert_equal(receipt_data["status"], PROCESS, "purchase receipt draft status")
    if len(receipt_data.get("items", [])) != 1:
        raise ScenarioError("purchase receipt must contain exactly one server-side item")
    receipt_item = ledger.resource("purchase_receipt_item", int(receipt_data["items"][0]["id"]))
    assert_equal(int(receipt_data["items"][0]["orderItemId"]), order_item, "receipt order item ownership")
    assert_equal(int(receipt_data["items"][0]["warehouseId"]), warehouse, "receipt warehouse")
    assert_equal(decimal(api(client, ledger, "verify_draft_stock_unchanged", "GET", "/admin-api/erp/stock/get-count", query={"productId": product})), baseline, "draft stock")
    order_data = api(client, ledger, "verify_order_received_count", "GET", "/admin-api/erp/purchase-order/get", query={"id": order})
    assert_equal(decimal(order_data["inCount"]), quantity, "purchase order received count")

    api(client, ledger, "approve_purchase_receipt", "PUT", "/admin-api/erp/purchase-in/update-status", query={"id": receipt, "status": APPROVE})
    receipt_data = api(client, ledger, "verify_purchase_receipt_approved", "GET", "/admin-api/erp/purchase-in/get", query={"id": receipt})
    assert_equal(receipt_data["status"], APPROVE, "purchase receipt approved status")
    expected_stock = baseline + quantity
    stock = api(client, ledger, "reconcile_stock", "GET", "/admin-api/erp/stock/get", query={"productId": product, "warehouseId": warehouse})
    assert_equal(decimal(stock["count"]), expected_stock, "warehouse stock")
    records = api(client, ledger, "reconcile_purchase_movement", "GET", "/admin-api/erp/stock-record/page",
                  query={"pageNo": 1, "pageSize": 100, "productId": product, "warehouseId": warehouse, "bizNo": receipt_data["no"]})
    matches = [row for row in records["list"] if row.get("bizType") == PURCHASE_IN and int(row.get("bizId")) == receipt]
    if len(matches) != 1:
        raise ScenarioError(f"expected one purchase-in movement, got {len(matches)}")
    movement = matches[0]
    assert_equal(int(movement["bizItemId"]), receipt_item, "movement receipt item")
    assert_equal(decimal(movement["count"]), quantity, "movement quantity")
    assert_equal(decimal(movement["totalCount"]), expected_stock, "movement after quantity")
    ledger.data["reconciliation"] = {"baseline": str(baseline), "delta": str(quantity), "after": str(expected_stock),
        "receipt_no": receipt_data["no"], "movement_id": movement["id"], "status": "passed"}
    ledger.data["metadata"]["state"] = "executed"
    ledger.save()


def cleanup(client: ErpClient, ledger: Ledger) -> None:
    resources = ledger.data.get("resources", {})
    required = {"purchase_receipt", "purchase_order", "product", "warehouse"}
    missing = sorted(required - resources.keys())
    if missing:
        raise ScenarioError(f"ledger lacks cleanup resources: {', '.join(missing)}")
    receipt = int(resources["purchase_receipt"])
    order = int(resources["purchase_order"])
    product = int(resources["product"])
    warehouse = int(resources["warehouse"])
    baseline = decimal(ledger.data.get("reconciliation", {}).get("baseline"))
    receipt_data = api(client, ledger, "inspect_receipt_before_cleanup", "GET", "/admin-api/erp/purchase-in/get", query={"id": receipt})
    if receipt_data and receipt_data["status"] == APPROVE:
        api(client, ledger, "reverse_purchase_receipt", "PUT", "/admin-api/erp/purchase-in/update-status", query={"id": receipt, "status": PROCESS})
    stock = api(client, ledger, "verify_compensated_stock", "GET", "/admin-api/erp/stock/get", query={"productId": product, "warehouseId": warehouse})
    assert_equal(decimal(stock["count"] if stock else 0), baseline, "compensated stock")
    records = api(client, ledger, "verify_compensating_movement", "GET", "/admin-api/erp/stock-record/page",
                  query={"pageNo": 1, "pageSize": 100, "productId": product, "warehouseId": warehouse,
                         "bizNo": receipt_data["no"]})
    cancel_matches = [row for row in records["list"]
                      if row.get("bizType") == PURCHASE_IN_CANCEL and int(row.get("bizId")) == receipt]
    if len(cancel_matches) != 1:
        raise ScenarioError(f"expected one purchase-in cancellation movement, got {len(cancel_matches)}")
    delta = decimal(ledger.data.get("reconciliation", {}).get("delta"))
    assert_equal(decimal(cancel_matches[0]["count"]), -delta, "compensating movement quantity")
    assert_equal(decimal(cancel_matches[0]["totalCount"]), baseline, "compensating movement after quantity")
    api(client, ledger, "delete_purchase_receipt", "DELETE", "/admin-api/erp/purchase-in/delete", query={"ids": receipt})
    order_data = api(client, ledger, "verify_order_count_after_receipt_delete", "GET", "/admin-api/erp/purchase-order/get", query={"id": order})
    assert_equal(decimal(order_data["inCount"]), Decimal(0), "purchase order received count after cleanup")
    if order_data["status"] == APPROVE:
        api(client, ledger, "reverse_purchase_order", "PUT", "/admin-api/erp/purchase-order/update-status", query={"id": order, "status": PROCESS})
    api(client, ledger, "delete_purchase_order", "DELETE", "/admin-api/erp/purchase-order/delete", query={"ids": order})
    for name, path in [
        ("product", "/admin-api/erp/product/delete"), ("category", "/admin-api/erp/product-category/delete"),
        ("unit", "/admin-api/erp/product-unit/delete"), ("supplier", "/admin-api/erp/supplier/delete"),
        ("warehouse", "/admin-api/erp/warehouse/delete"), ("account", "/admin-api/erp/account/delete"),
    ]:
        if name in resources:
            api(client, ledger, f"delete_{name}", "DELETE", path, query={"id": resources[name]})
    ledger.data["metadata"]["state"] = "compensated"
    ledger.data["metadata"]["residuals"] = ["immutable stock audit records", "zero-balance stock row"]
    ledger.save()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a governed CloudMold ERP scenario")
    parser.add_argument("--mode", choices=["plan", "inspect", "dry-run", "execute", "cleanup"], default="plan")
    parser.add_argument("--scenario", choices=[SCENARIO], default=SCENARIO)
    parser.add_argument("--run-id")
    parser.add_argument("--base-url", default=os.getenv("CLOUDMOLD_ERP_BASE_URL", "http://127.0.0.1:48080"))
    parser.add_argument("--tenant-id", default=os.getenv("CLOUDMOLD_TENANT_ID", "1"))
    parser.add_argument("--token", default=os.getenv("CLOUDMOLD_ADMIN_TOKEN"))
    parser.add_argument("--username", default=os.getenv("CLOUDMOLD_ADMIN_USERNAME"))
    parser.add_argument("--password", default=os.getenv("CLOUDMOLD_ADMIN_PASSWORD"))
    parser.add_argument("--repo", default=os.getenv("CLOUDMOLD_YUDAO_REPO"))
    parser.add_argument("--run-dir", default=os.getenv("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    parser.add_argument("--ledger", help="existing ledger path; required for cleanup when run-id is omitted")
    parser.add_argument("--quantity", default="10.00")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_id = require_run_id(args.run_id or (Path(args.ledger).parent.name if args.ledger else None))
    quantity = decimal(args.quantity)
    if quantity <= 0:
        raise ScenarioError("quantity must be positive")
    if args.mode == "plan":
        print(json.dumps({"scenario": SCENARIO, "mode": "plan", "run_id": run_id, "steps": scenario_plan(run_id)}, ensure_ascii=False, indent=2))
        return 0
    ledger_path = Path(args.ledger) if args.ledger else Path(args.run_dir) / "erp" / run_id / "ledger.json"
    metadata = {"scenario": SCENARIO, "run_id": run_id, "tenant_id": str(args.tenant_id), "base_url": args.base_url,
                "source_commit": source_commit(args.repo), "created_at": utc_now(), "state": "planned"}
    ledger = Ledger(ledger_path, metadata)
    client = ErpClient(args.base_url, str(args.tenant_id), args.token)
    if not client.token:
        if not args.username or not args.password:
            raise ScenarioError("set CLOUDMOLD_ADMIN_TOKEN or both CLOUDMOLD_ADMIN_USERNAME and CLOUDMOLD_ADMIN_PASSWORD")
        client.login(args.username, args.password)
    openapi_fingerprint = verify_openapi(client.openapi())
    ledger.data["metadata"]["openapi_sha256"] = openapi_fingerprint
    ledger.save()
    permission = client.get("/admin-api/system/auth/get-permission-info")
    if not permission or not permission.get("user"):
        raise ScenarioError("operator identity readback failed")
    if args.mode in {"inspect", "dry-run"}:
        result = {"scenario": SCENARIO, "mode": args.mode, "run_id": run_id, "tenant_id": str(args.tenant_id),
                  "operator_id": permission["user"]["id"], "source_commit": metadata["source_commit"],
                  "openapi_sha256": openapi_fingerprint,
                  "checks": ["authentication", "tenant header", "operator readback", "live OpenAPI routes", "local payload invariants"],
                  "writes_performed": False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.mode == "execute":
        if ledger.data.get("metadata", {}).get("state") != "planned":
            raise ScenarioError("execute requires a fresh planned ledger; use a new run_id")
        execute(client, ledger, run_id, quantity)
    else:
        cleanup(client, ledger)
    print(json.dumps({"scenario": SCENARIO, "mode": args.mode, "run_id": run_id,
                      "ledger": str(ledger.path), "state": ledger.data["metadata"]["state"],
                      "reconciliation": ledger.data.get("reconciliation", {})}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScenarioError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
