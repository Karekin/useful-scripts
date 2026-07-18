#!/usr/bin/env python3
"""Compose the canonical Catalog and Inventory slices into one governed vertical run."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{5,19}$")
SKILL_DIR = Path(__file__).resolve().parent.parent
CATALOG_RUNNER = SKILL_DIR / "scripts" / "canonical_catalog_runner.py"
INVENTORY_RUNNER = SKILL_DIR / "scripts" / "canonical_inventory_runner.py"
PROJECTION_RUNNER = SKILL_DIR / "scripts" / "legacy_catalog_projection_runner.py"


class ScenarioError(RuntimeError):
    pass


def run_json(command: list[str]) -> dict:
    completed = subprocess.run(command, text=True, capture_output=True, env=os.environ.copy())
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise ScenarioError(f"child runner failed: {detail[-1000:]}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ScenarioError(f"child runner returned non-JSON output: {completed.stdout[-1000:]}") from exc
    if result.get("status") == "failed":
        raise ScenarioError(f"child runner rejected the scenario: {result.get('error')}")
    return result


def reconcile_with_retry(command: list[str], timeout: int, interval: int) -> str:
    deadline = time.monotonic() + timeout
    last_output = ""
    while True:
        completed = subprocess.run(command, text=True, capture_output=True, env=os.environ.copy())
        last_output = (completed.stdout + completed.stderr).strip()
        if completed.returncode == 0:
            return completed.stdout
        if time.monotonic() >= deadline:
            raise ScenarioError(f"lakehouse reconciliation timed out: {last_output[-1500:]}")
        time.sleep(interval)


def child_common(args: argparse.Namespace, run_id: str) -> list[str]:
    return ["--mode", args.mode, "--run-id", run_id, "--environment", args.environment,
            "--base-url", args.base_url, "--tenant", str(args.tenant), "--timeout", str(args.http_timeout)]


def write_ledger(args: argparse.Namespace, ledger: dict) -> Path:
    run_root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    output = run_root / "yshopping" / args.run_id / "ledger.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        suffix = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = output.parent / f"replay-ledger-{suffix}.json"
    output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
    return output


def execute(args: argparse.Namespace) -> dict:
    catalog_run_id = f"{args.run_id}-cat"
    projection_run_id = f"{args.run_id}-proj"
    inventory_run_id = f"{args.run_id}-inv"
    catalog = run_json([sys.executable, str(CATALOG_RUNNER), *child_common(args, catalog_run_id)])
    projection = run_json([sys.executable, str(PROJECTION_RUNNER),
                           *child_common(args, projection_run_id), "--catalog-ledger", catalog["ledger"]])
    inventory = run_json([sys.executable, str(INVENTORY_RUNNER), *child_common(args, inventory_run_id),
                          "--catalog-ledger", catalog["ledger"]])

    lakehousectl = Path(args.workspace) / "useful-scripts" / "yml" / "yshopping-lakehouse" / "scripts" / "lakehousectl"
    if not lakehousectl.is_file():
        raise ScenarioError(f"lakehousectl does not exist: {lakehousectl}")
    catalog_reconcile = reconcile_with_retry(
        [str(lakehousectl), "reconcile-canonical-catalog", "--tenant", str(args.tenant),
         "--run-id", catalog_run_id], args.cdc_timeout, args.poll_interval)
    inventory_reconcile = reconcile_with_retry(
        [str(lakehousectl), "reconcile-canonical-inventory", "--tenant", str(args.tenant),
         "--run-id", inventory_run_id], args.cdc_timeout, args.poll_interval)

    final = inventory["final"]
    if (str(final.get("onHandQuantity")) not in {"8", "8.0", "8.000000"}
            or str(final.get("reservedQuantity")) not in {"0", "0.0", "0.000000"}
            or str(final.get("availableQuantity")) not in {"8", "8.0", "8.000000"}
            or final.get("aggregateVersion") != 6):
        raise ScenarioError(f"vertical Inventory terminal invariant failed: {final}")
    ledger = {
        "scenario": "yshopping-catalog-inventory-vertical-v1",
        "run_id": args.run_id,
        "environment": args.environment,
        "tenant": args.tenant,
        "catalog_run_id": catalog_run_id,
        "projection_run_id": projection_run_id,
        "inventory_run_id": inventory_run_id,
        "catalog": catalog,
        "projection": projection,
        "inventory": inventory,
        "lakehouse": {
            "catalog_reconcile": catalog_reconcile,
            "inventory_reconcile": inventory_reconcile,
        },
        "final": {
            "catalog_status": catalog["catalog_status"],
            "projection_count": projection["projection_count"],
            "canonical_sku_id": inventory["canonical_sku_id"],
            "inventory": final,
            "lakehouse_reconciled": True,
        },
    }
    output = write_ledger(args, ledger)
    return {"status": "succeeded", "run_id": args.run_id, "ledger": str(output), **ledger["final"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "dry-run", "execute"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", default="local")
    parser.add_argument("--base-url", default=os.getenv("CLOUDMOLD_ERP_BASE_URL", "http://127.0.0.1:48080"))
    parser.add_argument("--tenant", type=int, default=int(os.getenv("CLOUDMOLD_TENANT_ID", "1")))
    parser.add_argument("--workspace", default=os.getenv(
        "CLOUDMOLD_WORKSPACE", "/Users/karekin/Downloads/coding/project/CloudMold"))
    parser.add_argument("--http-timeout", type=int, default=20)
    parser.add_argument("--cdc-timeout", type=int, default=90)
    parser.add_argument("--poll-interval", type=int, default=5)
    args = parser.parse_args()
    try:
        if not RUN_ID_PATTERN.fullmatch(args.run_id):
            raise ScenarioError("run_id must be 6-20 characters using letters, digits, dot, underscore, or hyphen")
        if args.environment not in {"local", "demo", "test"}:
            raise ScenarioError("the vertical runner is restricted to local, demo, or test")
        if args.cdc_timeout < 1 or args.poll_interval < 1:
            raise ScenarioError("CDC timeout and poll interval must be positive")
        if args.mode == "plan":
            result = {
                "scenario": "yshopping-catalog-inventory-vertical-v1",
                "run_id": args.run_id,
                "flow": ["Catalog define", "Catalog lifecycle ACTIVE", "Mall/ERP/WMS projection plan",
                         "Inventory 6-step flow", "Catalog CDC reconcile",
                         "Inventory CDC reconcile", "all DQC"],
                "side_effects": False,
            }
        elif args.mode == "dry-run":
            catalog = run_json([sys.executable, str(CATALOG_RUNNER), *child_common(args, f"{args.run_id}-cat")])
            projection = run_json([sys.executable, str(PROJECTION_RUNNER),
                                   *child_common(args, f"{args.run_id}-proj")])
            inventory = run_json([sys.executable, str(INVENTORY_RUNNER),
                                  *child_common(args, f"{args.run_id}-inv"), "--sku-id", "dry-run-canonical-sku"])
            result = {"status": "ready", "run_id": args.run_id,
                      "catalog_routes": catalog.get("routes"), "projection_route": projection.get("route"),
                      "inventory_route": inventory.get("route"),
                      "side_effects": False}
        else:
            result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ScenarioError as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
