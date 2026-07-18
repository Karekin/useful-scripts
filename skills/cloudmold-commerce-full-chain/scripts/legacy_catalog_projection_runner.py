#!/usr/bin/env python3
"""Plan replayable Mall, ERP, and WMS snapshots from an ACTIVE Catalog run."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys

from canonical_catalog_runner import Client, ScenarioError


ROUTE = "/admin-api/cloudmold/integration/yudao/catalog/plan"
TARGETS = ["MALL", "ERP", "WMS"]


def load_catalog_ledger(path: str, tenant: int) -> tuple[dict, Path]:
    ledger_path = Path(path).expanduser().resolve()
    if not ledger_path.is_file():
        raise ScenarioError(f"Catalog ledger does not exist: {ledger_path}")
    try:
        ledger = json.loads(ledger_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenarioError(f"cannot read Catalog ledger: {exc}") from exc
    if ledger.get("scenario") != "canonical-catalog-first-slice-v1" or ledger.get("tenant") != tenant:
        raise ScenarioError("Catalog ledger scenario or tenant does not match")
    final = ledger.get("final") or {}
    sku_ids = final.get("sku_ids")
    if final.get("catalog_status") != "ACTIVE" or not isinstance(sku_ids, list) or len(sku_ids) != 6:
        raise ScenarioError("Catalog ledger must prove one ACTIVE six-SKU matrix")
    return ledger, ledger_path


def execute(args: argparse.Namespace) -> dict:
    catalog, catalog_path = load_catalog_ledger(args.catalog_ledger, args.tenant)
    client = Client(args.base_url, args.tenant, args.token, args.timeout)
    if not client.token:
        if not args.username or not args.password:
            raise ScenarioError("set token or username/password through environment variables")
        client.login(args.username, args.password)
    steps = []
    changed_count = 0
    for index, sku_id in enumerate(sorted(catalog["final"]["sku_ids"]), 1):
        payload = {"canonicalSkuId": sku_id, "targets": TARGETS}
        result = client.request("POST", ROUTE, payload)
        projections = result.get("projections")
        if result.get("canonicalSkuId") != sku_id or not isinstance(projections, list) or len(projections) != 3:
            raise ScenarioError(f"legacy projection result mismatch for SKU {sku_id}")
        if {item.get("targetSystem") for item in projections} != set(TARGETS):
            raise ScenarioError(f"legacy projection targets are incomplete for SKU {sku_id}")
        if any(item.get("state") != "PENDING" or not item.get("projectionId")
               or not item.get("payloadHash") for item in projections):
            raise ScenarioError(f"legacy projection evidence is incomplete for SKU {sku_id}")
        changed_count += sum(bool(item.get("changed")) for item in projections)
        steps.append({"step": index, "canonical_sku_id": sku_id,
                      "request_hash": hashlib.sha256(json.dumps(
                          payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                      "result": result})
    ledger = {
        "scenario": "canonical-catalog-legacy-projection-plan-v1",
        "run_id": args.run_id,
        "environment": args.environment,
        "tenant": args.tenant,
        "catalog_ledger": str(catalog_path),
        "steps": steps,
        "final": {"sku_count": 6, "projection_count": 18, "changed_count": changed_count,
                  "targets": TARGETS, "state": "PENDING"},
    }
    run_root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    output = run_root / "projection" / args.run_id / "ledger.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        suffix = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = output.parent / f"replay-ledger-{suffix}.json"
    output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
    return {"status": "succeeded", "run_id": args.run_id, "ledger": str(output), **ledger["final"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "dry-run", "execute"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--catalog-ledger")
    parser.add_argument("--environment", default="local")
    parser.add_argument("--base-url", default=os.getenv("CLOUDMOLD_ERP_BASE_URL", "http://127.0.0.1:48080"))
    parser.add_argument("--tenant", type=int, default=int(os.getenv("CLOUDMOLD_TENANT_ID", "1")))
    parser.add_argument("--token", default=os.getenv("CLOUDMOLD_ADMIN_TOKEN"))
    parser.add_argument("--username", default=os.getenv("CLOUDMOLD_ADMIN_USERNAME"))
    parser.add_argument("--password", default=os.getenv("CLOUDMOLD_ADMIN_PASSWORD"))
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        if args.mode == "plan":
            result = {"scenario": "canonical-catalog-legacy-projection-plan-v1", "run_id": args.run_id,
                      "targets": TARGETS, "side_effects": False}
        elif args.mode == "dry-run":
            paths = Client(args.base_url, args.tenant, args.token, args.timeout).openapi().get("paths", {})
            if ROUTE not in paths or "post" not in paths[ROUTE]:
                raise ScenarioError(f"live OpenAPI is missing {ROUTE}")
            result = {"status": "ready", "route": ROUTE, "targets": TARGETS, "side_effects": False}
        else:
            if not args.catalog_ledger:
                raise ScenarioError("--catalog-ledger is required for execute")
            result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ScenarioError as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
