#!/usr/bin/env python3
"""Compose Catalog, compatibility projection, Listing/Fulfillment, and lakehouse v2 evidence."""

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
PROJECTION_RUNNER = SKILL_DIR / "scripts" / "legacy_catalog_projection_runner.py"
COMMERCE_V2_RUNNER = SKILL_DIR / "scripts" / "canonical_listing_fulfillment_runner.py"
REQUIRED_LAKEHOUSE_COMMANDS = (
    "config-check",
    "contract-test",
    "apply-models",
    "test",
    "reconcile-canonical-catalog",
    "reconcile-canonical-commerce-v2",
)


class ScenarioError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ScenarioError(message)


def run_json(command: list[str]) -> dict:
    completed = subprocess.run(command, text=True, capture_output=True, env=os.environ.copy())
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise ScenarioError(f"child runner failed: {detail[-1500:]}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ScenarioError(f"child runner returned non-JSON output: {completed.stdout[-1000:]}") from exc
    if result.get("status") == "failed":
        raise ScenarioError(f"child runner rejected the scenario: {result.get('error')}")
    return result


def parse_lakehouse_capabilities(output: str) -> set[str]:
    return {command for command in REQUIRED_LAKEHOUSE_COMMANDS if command in output}


def require_lakehouse_capabilities(lakehousectl: Path) -> set[str]:
    if not lakehousectl.is_file():
        raise ScenarioError(f"lakehousectl does not exist: {lakehousectl}")
    if not os.access(lakehousectl, os.X_OK):
        raise ScenarioError(f"lakehousectl is not executable: {lakehousectl}")
    completed = subprocess.run([str(lakehousectl)], text=True, capture_output=True, env=os.environ.copy())
    output = completed.stdout + completed.stderr
    capabilities = parse_lakehouse_capabilities(output)
    missing = sorted(set(REQUIRED_LAKEHOUSE_COMMANDS) - capabilities)
    if missing:
        raise ScenarioError(
            "lakehousectl is missing required command(s) for Listing/Fulfillment vertical: "
            + ", ".join(missing))
    return capabilities


def run_lakehouse(lakehousectl: Path, command: str) -> str:
    completed = subprocess.run([str(lakehousectl), command], text=True, capture_output=True,
                               env=os.environ.copy())
    if completed.returncode != 0:
        detail = (completed.stdout + completed.stderr).strip()
        raise ScenarioError(f"lakehouse {command} failed: {detail[-2000:]}")
    return completed.stdout


def reconcile_with_retry(command: list[str], timeout: int, interval: int) -> str:
    deadline = time.monotonic() + timeout
    last_output = ""
    while True:
        completed = subprocess.run(command, text=True, capture_output=True, env=os.environ.copy())
        last_output = (completed.stdout + completed.stderr).strip()
        if completed.returncode == 0:
            return completed.stdout
        if time.monotonic() >= deadline:
            raise ScenarioError(
                f"lakehouse reconciliation command {command[1]} timed out: {last_output[-2000:]}")
        time.sleep(interval)


def child_common(args: argparse.Namespace, run_id: str) -> list[str]:
    return ["--mode", args.mode, "--run-id", run_id, "--environment", args.environment,
            "--base-url", args.base_url, "--tenant", str(args.tenant),
            "--timeout", str(args.http_timeout)]


def child_run_ids(run_id: str) -> dict[str, str]:
    return {"catalog": f"{run_id}-cat", "projection": f"{run_id}-proj",
            "commerce_v2": f"{run_id}-commerce-v2"}


def scenario_plan() -> list[str]:
    return [
        "verify lakehousectl exposes config, contract, model, DQC, Catalog reconcile, and commerce-v2 reconcile",
        "Catalog: define and activate one Style/SPU plus six apparel SKU",
        "compatibility: create or replay 18 Mall/ERP/WMS PENDING identity projections",
        "commerce-v2: publish Listing, place from exact offer, reserve and pay",
        "commerce-v2: create fulfillment, ship, track, deliver, refund, and return",
        "commerce-v2: immediately replay all 23 business commands as immutable duplicates",
        "lakehouse: config-check, contract-test, apply-models, and test",
        "lakehouse: reconcile canonical Catalog and canonical commerce-v2 by child run_id",
    ]


def write_ledger(args: argparse.Namespace, ledger: dict) -> Path:
    run_root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    output = run_root / "yshopping-listing-fulfillment" / args.run_id / "ledger.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        suffix = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = output.parent / f"replay-ledger-{suffix}.json"
    output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def lakehousectl_path(args: argparse.Namespace) -> Path:
    return (Path(args.workspace) / "useful-scripts" / "yml" / "yshopping-lakehouse"
            / "scripts" / "lakehousectl")


def execute(args: argparse.Namespace) -> dict:
    run_ids = child_run_ids(args.run_id)
    lakehousectl = lakehousectl_path(args)
    capabilities = require_lakehouse_capabilities(lakehousectl)

    # Fail on configuration, contract, model, or DQC readiness before writing business fixtures.
    lakehouse_preflight = {
        command: run_lakehouse(lakehousectl, command)
        for command in ("config-check", "contract-test", "apply-models", "test")
    }

    catalog = run_json([sys.executable, str(CATALOG_RUNNER),
                        *child_common(args, run_ids["catalog"])])
    projection = run_json([sys.executable, str(PROJECTION_RUNNER),
                           *child_common(args, run_ids["projection"]),
                           "--catalog-ledger", catalog["ledger"]])
    commerce = run_json([sys.executable, str(COMMERCE_V2_RUNNER),
                         *child_common(args, run_ids["commerce_v2"]),
                         "--catalog-ledger", catalog["ledger"]])

    catalog_reconcile = reconcile_with_retry(
        [str(lakehousectl), "reconcile-canonical-catalog", "--tenant", str(args.tenant),
         "--run-id", run_ids["catalog"]], args.cdc_timeout, args.poll_interval)
    commerce_reconcile = reconcile_with_retry(
        [str(lakehousectl), "reconcile-canonical-commerce-v2", "--tenant", str(args.tenant),
         "--run-id", run_ids["commerce_v2"]], args.cdc_timeout, args.poll_interval)

    listing, order = commerce["listing"], commerce["order"]
    payment, fulfillment, inventory = commerce["payment"], commerce["fulfillment"], commerce["inventory"]
    require(catalog.get("catalog_status") == "ACTIVE" and catalog.get("sku_count") == 6,
            f"vertical Catalog terminal invariant failed: {catalog}")
    require(projection.get("projection_count") == 18,
            f"vertical projection count invariant failed: {projection}")
    require(listing.get("currentStatus") == "PUBLISHED" and listing.get("aggregateVersion") == 6,
            f"vertical Listing terminal invariant failed: {listing}")
    require(order.get("currentStatus") == "RETURNED" and order.get("aggregateVersion") == 7,
            f"vertical Order terminal invariant failed: {order}")
    require(payment.get("currentStatus") == "REFUNDED" and payment.get("aggregateVersion") == 2,
            f"vertical Payment terminal invariant failed: {payment}")
    require(fulfillment.get("currentStatus") == "DELIVERED" and fulfillment.get("aggregateVersion") == 4,
            f"vertical Fulfillment terminal invariant failed: {fulfillment}")
    require(str(inventory.get("onHandQuantity")) in {"10", "10.0", "10.000000"}
            and str(inventory.get("reservedQuantity")) in {"0", "0.0", "0.000000"}
            and str(inventory.get("availableQuantity")) in {"10", "10.0", "10.000000"}
            and inventory.get("aggregateVersion") == 4,
            f"vertical Inventory terminal invariant failed: {inventory}")
    require(commerce.get("all_replay_duplicate") is True,
            "commerce-v2 child did not prove complete immediate replay idempotency")

    replay_evidence = {
        "commerce_v2_all_23_commands_duplicate": True,
        "catalog_child_run_id": run_ids["catalog"],
        "projection_changed_count": projection.get("changed_count"),
        "parent_replay_expectation": (
            "same parent run_id reuses Catalog operation results, reports projection changed_count=0, "
            "and keeps all commerce-v2 command results duplicate"),
    }
    ledger = {
        "scenario": "yshopping-listing-fulfillment-vertical-v1",
        "run_id": args.run_id,
        "environment": args.environment,
        "tenant": args.tenant,
        "child_run_ids": run_ids,
        "catalog": catalog,
        "projection": projection,
        "commerce_v2": commerce,
        "replay_evidence": replay_evidence,
        "lakehouse": {"capabilities": sorted(capabilities), "preflight": lakehouse_preflight,
                      "catalog_reconcile": catalog_reconcile,
                      "commerce_v2_reconcile": commerce_reconcile},
        "final": {
            "catalog_status": "ACTIVE",
            "projection_count": 18,
            "canonical_sku_id": commerce["canonical_sku_id"],
            "listing": listing,
            "order": order,
            "payment": payment,
            "fulfillment": fulfillment,
            "inventory": inventory,
            "all_replay_duplicate": True,
            "lakehouse_reconciled": True,
        },
    }
    output = write_ledger(args, ledger)
    return {"status": "succeeded", "run_id": args.run_id, "ledger": str(output),
            "replay_evidence": replay_evidence, **ledger["final"]}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "dry-run", "execute"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", default="local")
    parser.add_argument("--base-url", default=os.getenv("CLOUDMOLD_ERP_BASE_URL", "http://127.0.0.1:48080"))
    parser.add_argument("--tenant", type=int, default=int(os.getenv("CLOUDMOLD_TENANT_ID", "1")))
    parser.add_argument("--workspace", default=os.getenv(
        "CLOUDMOLD_WORKSPACE", "/Users/karekin/Downloads/coding/project/CloudMold"))
    parser.add_argument("--http-timeout", type=int, default=20)
    parser.add_argument("--cdc-timeout", type=int, default=120)
    parser.add_argument("--poll-interval", type=int, default=5)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    try:
        require(bool(RUN_ID_PATTERN.fullmatch(args.run_id)),
                "run_id must be 6-20 characters using letters, digits, dot, underscore, or hyphen")
        require(args.environment in {"local", "demo", "test"},
                "the vertical runner is restricted to local, demo, or test")
        require(args.cdc_timeout > 0 and args.poll_interval > 0,
                "CDC timeout and poll interval must be positive")
        run_ids = child_run_ids(args.run_id)
        if args.mode == "plan":
            result = {"scenario": "yshopping-listing-fulfillment-vertical-v1",
                      "run_id": args.run_id, "child_run_ids": run_ids,
                      "flow": scenario_plan(), "required_lakehouse_commands": list(REQUIRED_LAKEHOUSE_COMMANDS),
                      "side_effects": False}
        elif args.mode == "dry-run":
            capabilities = require_lakehouse_capabilities(lakehousectl_path(args))
            catalog = run_json([sys.executable, str(CATALOG_RUNNER),
                                *child_common(args, run_ids["catalog"])])
            projection = run_json([sys.executable, str(PROJECTION_RUNNER),
                                   *child_common(args, run_ids["projection"])])
            commerce = run_json([sys.executable, str(COMMERCE_V2_RUNNER),
                                 *child_common(args, run_ids["commerce_v2"]),
                                 "--sku-id", "dry-run-canonical-sku",
                                 "--spu-id", "dry-run-canonical-spu"])
            result = {"status": "ready", "run_id": args.run_id,
                      "catalog_routes": catalog.get("routes"),
                      "projection_route": projection.get("route"),
                      "commerce_v2_routes": commerce.get("routes"),
                      "lakehouse_capabilities": sorted(capabilities), "side_effects": False}
        else:
            result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ScenarioError as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
