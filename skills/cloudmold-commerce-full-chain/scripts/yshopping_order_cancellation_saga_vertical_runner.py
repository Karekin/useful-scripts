#!/usr/bin/env python3
"""Compose Catalog, compatibility projection, durable cancellation Saga, and lakehouse evidence."""

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
CANCELLATION_SAGA_RUNNER = SKILL_DIR / "scripts" / "canonical_order_cancellation_saga_runner.py"
REQUIRED_LAKEHOUSE_COMMANDS = (
    "config-check",
    "contract-test",
    "apply-models",
    "test",
    "reconcile-canonical-catalog",
    "reconcile-canonical-cancellation-saga",
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
    capabilities = parse_lakehouse_capabilities(completed.stdout + completed.stderr)
    missing = sorted(set(REQUIRED_LAKEHOUSE_COMMANDS) - capabilities)
    if missing:
        raise ScenarioError(
            "lakehousectl is missing required durable cancellation Saga command(s): " + ", ".join(missing))
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
            "cancellation_saga": f"{run_id}-csaga"}


def scenario_plan() -> list[str]:
    return [
        "verify lakehousectl exposes contract, model, DQC, Catalog, and cancellation Saga reconciliation",
        "Catalog: define and activate one Style/SPU plus six apparel SKU",
        "compatibility: create or replay 18 Mall/ERP/WMS PENDING identity projections",
        "commerce: publish Listing, place from exact offer, and reserve Inventory",
        "cancellation: START durable Saga, poll COMPLETED, and prove RELEASE/FINALIZE duplicate",
        "cancellation: replay all 11 client-issued commands and prove zero Payment/Fulfillment",
        "lakehouse: config-check, contract-test, apply-models, and test",
        "lakehouse: reconcile canonical Catalog and durable cancellation Saga by child run_id",
    ]


def write_ledger(args: argparse.Namespace, ledger: dict) -> Path:
    run_root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    output = run_root / "yshopping-order-cancellation-saga" / args.run_id / "ledger.json"
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
    lakehouse_preflight = {
        command: run_lakehouse(lakehousectl, command)
        for command in ("config-check", "contract-test", "apply-models", "test")
    }

    catalog = run_json([sys.executable, str(CATALOG_RUNNER),
                        *child_common(args, run_ids["catalog"])])
    projection = run_json([sys.executable, str(PROJECTION_RUNNER),
                           *child_common(args, run_ids["projection"]),
                           "--catalog-ledger", catalog["ledger"]])
    cancellation = run_json([sys.executable, str(CANCELLATION_SAGA_RUNNER),
                             *child_common(args, run_ids["cancellation_saga"]),
                             "--catalog-ledger", catalog["ledger"],
                             "--saga-timeout", str(args.saga_timeout),
                             "--poll-interval", str(args.saga_poll_interval)])

    catalog_reconcile = reconcile_with_retry(
        [str(lakehousectl), "reconcile-canonical-catalog", "--tenant", str(args.tenant),
         "--run-id", run_ids["catalog"]], args.cdc_timeout, args.cdc_poll_interval)
    cancellation_reconcile = reconcile_with_retry(
        [str(lakehousectl), "reconcile-canonical-cancellation-saga", "--tenant", str(args.tenant),
         "--run-id", run_ids["cancellation_saga"]], args.cdc_timeout, args.cdc_poll_interval)

    require(catalog.get("catalog_status") == "ACTIVE" and catalog.get("sku_count") == 6,
            f"vertical Catalog terminal invariant failed: {catalog}")
    require(projection.get("projection_count") == 18,
            f"vertical projection count invariant failed: {projection}")
    require(cancellation.get("saga", {}).get("status") == "COMPLETED",
            f"vertical Saga terminal invariant failed: {cancellation}")
    require(cancellation.get("order", {}).get("currentStatus") == "CANCELLED"
            and cancellation.get("order", {}).get("aggregateVersion") == 4,
            f"vertical Order terminal invariant failed: {cancellation}")
    require(cancellation.get("all_replay_duplicate") is True,
            "cancellation child did not prove complete client-command replay idempotency")

    ledger = {
        "scenario": "yshopping-order-cancellation-saga-vertical-v1",
        "run_id": args.run_id,
        "environment": args.environment,
        "tenant": args.tenant,
        "child_run_ids": run_ids,
        "catalog": catalog,
        "projection": projection,
        "cancellation_saga": cancellation,
        "lakehouse": {"capabilities": sorted(capabilities), "preflight": lakehouse_preflight,
                      "catalog_reconcile": catalog_reconcile,
                      "cancellation_saga_reconcile": cancellation_reconcile},
        "final": {"catalog_status": "ACTIVE", "projection_count": 18,
                  "canonical_sku_id": cancellation["canonical_sku_id"],
                  "saga": cancellation["saga"], "order": cancellation["order"],
                  "inventory": cancellation["inventory"],
                  "absence_proof": cancellation["absence_proof"],
                  "all_replay_duplicate": True, "lakehouse_reconciled": True},
    }
    output = write_ledger(args, ledger)
    return {"status": "succeeded", "run_id": args.run_id, "ledger": str(output), **ledger["final"]}


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
    parser.add_argument("--saga-timeout", type=float, default=90)
    parser.add_argument("--saga-poll-interval", type=float, default=1)
    parser.add_argument("--cdc-timeout", type=int, default=120)
    parser.add_argument("--cdc-poll-interval", type=int, default=5)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    try:
        require(bool(RUN_ID_PATTERN.fullmatch(args.run_id)),
                "run_id must be 6-20 characters using letters, digits, dot, underscore, or hyphen")
        require(args.environment in {"local", "demo", "test"},
                "the durable cancellation vertical is restricted to local, demo, or test")
        require(args.saga_timeout > 0 and args.saga_poll_interval > 0
                and args.cdc_timeout > 0 and args.cdc_poll_interval > 0,
                "Saga and CDC timeout/poll intervals must be positive")
        run_ids = child_run_ids(args.run_id)
        if args.mode == "plan":
            result = {"scenario": "yshopping-order-cancellation-saga-vertical-v1",
                      "run_id": args.run_id, "child_run_ids": run_ids,
                      "flow": scenario_plan(),
                      "required_lakehouse_commands": list(REQUIRED_LAKEHOUSE_COMMANDS),
                      "side_effects": False}
        elif args.mode == "dry-run":
            capabilities = require_lakehouse_capabilities(lakehousectl_path(args))
            catalog = run_json([sys.executable, str(CATALOG_RUNNER),
                                *child_common(args, run_ids["catalog"])])
            projection = run_json([sys.executable, str(PROJECTION_RUNNER),
                                   *child_common(args, run_ids["projection"])])
            cancellation = run_json([sys.executable, str(CANCELLATION_SAGA_RUNNER),
                                     *child_common(args, run_ids["cancellation_saga"]),
                                     "--sku-id", "dry-run-canonical-sku",
                                     "--spu-id", "dry-run-canonical-spu"])
            result = {"status": "ready", "run_id": args.run_id,
                      "catalog_routes": catalog.get("routes"),
                      "projection_route": projection.get("route"),
                      "cancellation_saga_post_routes": cancellation.get("post_routes"),
                      "cancellation_saga_get_routes": cancellation.get("get_routes"),
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
