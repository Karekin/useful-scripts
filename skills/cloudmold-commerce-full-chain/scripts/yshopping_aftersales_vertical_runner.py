#!/usr/bin/env python3
"""Compose Catalog, projections, governed AfterSale, and read-only lakehouse evidence."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

from aftersales_runner_core import (
    AtomicRunLedger,
    endpoint_fingerprint,
    load_endpoint_manifest,
    sha256_json,
    source_commit,
)
from canonical_inventory_runner import ScenarioError
from canonical_listing_fulfillment_runner import require


RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{5,19}$")
SKILL_DIR = Path(__file__).resolve().parent.parent
CATALOG_RUNNER = SKILL_DIR / "scripts" / "canonical_catalog_runner.py"
PROJECTION_RUNNER = SKILL_DIR / "scripts" / "legacy_catalog_projection_runner.py"
MASTER_RUNNER = SKILL_DIR / "scripts" / "canonical_merchant_warehouse_runner.py"
AFTERSALES_RUNNER = SKILL_DIR / "scripts" / "canonical_aftersales_runner.py"
DEFAULT_MANIFEST = SKILL_DIR / "references" / "scenarios" / "aftersales-endpoints-v1.json"
SCENARIO_FILE = SKILL_DIR / "references" / "scenarios" / "yshopping-aftersales-vertical-v1.json"
REQUIRED_LAKEHOUSE_COMMANDS = (
    "config-check",
    "contract-test",
    "submit-event-cdc",
    "apply-models",
    "test",
    "reconcile-canonical-catalog",
    "reconcile-canonical-merchant",
    "reconcile-canonical-warehouse-network",
    "reconcile-canonical-aftersales",
)
EVENT_CDC_JOB_NAME = "CloudMold Domain Event Outbox to StarRocks ODS"


def run_json(command: list[str]) -> dict:
    completed = subprocess.run(command, text=True, capture_output=True, env=os.environ.copy())
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise ScenarioError(f"child runner failed: {detail[-2000:]}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ScenarioError(
            f"child runner returned non-JSON output: {completed.stdout[-1000:]}") from exc
    if result.get("status") == "failed":
        raise ScenarioError(f"child runner rejected the scenario: {result.get('error')}")
    return result


def parse_lakehouse_capabilities(output: str) -> set[str]:
    return {command for command in REQUIRED_LAKEHOUSE_COMMANDS if command in output}


def require_lakehouse_capabilities(path: Path) -> set[str]:
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ScenarioError(f"lakehousectl is missing or not executable: {path}")
    completed = subprocess.run([str(path)], text=True, capture_output=True, env=os.environ.copy())
    capabilities = parse_lakehouse_capabilities(completed.stdout + completed.stderr)
    missing = sorted(set(REQUIRED_LAKEHOUSE_COMMANDS) - capabilities)
    require(not missing,
            "lakehousectl is missing required after-sales command(s): " + ", ".join(missing))
    return capabilities


def run_lakehouse(path: Path, command: str) -> str:
    completed = subprocess.run([str(path), command], text=True, capture_output=True,
                               env=os.environ.copy())
    if completed.returncode != 0:
        detail = (completed.stdout + completed.stderr).strip()
        raise ScenarioError(f"lakehouse {command} failed: {detail[-2000:]}")
    return completed.stdout


def fetch_json(url: str, timeout: int = 5) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ScenarioError(f"cannot inspect Flink CDC state at {url}: {exc}") from exc


def ensure_event_cdc(path: Path, rest_url: str, timeout: int, interval: int) -> dict:
    """Ensure one event-outbox CDC job is RUNNING with a completed checkpoint."""
    deadline = time.monotonic() + timeout
    submitted = False
    last_state = "MISSING"
    while True:
        overview = fetch_json(f"{rest_url.rstrip('/')}/jobs/overview")
        matching = [job for job in overview.get("jobs", [])
                    if job.get("name") == EVENT_CDC_JOB_NAME
                    and job.get("state") not in {"FAILED", "CANCELED", "FINISHED"}]
        require(len(matching) <= 1,
                "multiple active CloudMold event CDC jobs detected; refuse duplicate ingestion")
        if matching:
            job = matching[0]
            last_state = str(job.get("state"))
            if last_state == "RUNNING":
                job_id = str(job.get("jid"))
                checkpoints = fetch_json(
                    f"{rest_url.rstrip('/')}/jobs/{job_id}/checkpoints")
                completed = int((checkpoints.get("counts") or {}).get("completed", 0))
                if completed > 0:
                    return {
                        "job_id": job_id,
                        "job_name": EVENT_CDC_JOB_NAME,
                        "state": last_state,
                        "completed_checkpoints": completed,
                        "submitted_by_runner": submitted,
                    }
        elif not submitted:
            run_lakehouse(path, "submit-event-cdc")
            submitted = True
            last_state = "SUBMITTED"
        if time.monotonic() >= deadline:
            raise ScenarioError(
                "event CDC did not become RUNNING with a completed checkpoint "
                f"within {timeout}s; last state={last_state}")
        time.sleep(interval)


def reconcile_read_only(command: list[str], timeout: int, interval: int) -> str:
    deadline = time.monotonic() + timeout
    last_output = ""
    while True:
        completed = subprocess.run(command, text=True, capture_output=True, env=os.environ.copy())
        last_output = (completed.stdout + completed.stderr).strip()
        if completed.returncode == 0:
            return completed.stdout
        if time.monotonic() >= deadline:
            raise ScenarioError(
                "read-only CDC reconciliation timed out; business writes will not be retried: "
                f"{last_output[-2000:]}")
        time.sleep(interval)


def child_run_ids(parent_run_id: str) -> dict[str, str]:
    return {
        "catalog": f"{parent_run_id}-cat",
        "projection": f"{parent_run_id}-proj",
        "master": f"{parent_run_id}-master",
        "aftersales": f"{parent_run_id}-aftersale",
    }


def child_common(args: argparse.Namespace, run_id: str) -> list[str]:
    return [
        "--mode", args.mode,
        "--run-id", run_id,
        "--environment", args.environment,
        "--base-url", args.base_url,
        "--tenant", str(args.tenant),
        "--timeout", str(args.http_timeout),
    ]


def lakehousectl_path(args: argparse.Namespace) -> Path:
    return (Path(args.workspace).expanduser().resolve() / "useful-scripts" / "yml"
            / "yshopping-lakehouse" / "scripts" / "lakehousectl")


def parent_ledger_path(args: argparse.Namespace) -> Path:
    root = Path(os.environ.get(
        "CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    return root / "yshopping-aftersales" / args.run_id / "ledger.json"


def record_child(ledger: AtomicRunLedger, domain: str, command: list[str]) -> dict:
    safe_command = [value for value in command]
    step = ledger.before_request(domain, safe_command[1], {
        "operation": "RUN_CHILD",
        "runner": safe_command[1],
        "arguments": safe_command[2:],
    })
    result = run_json(command)
    ledger.after_request(step, result)
    return result


def scenario_plan() -> list[str]:
    return [
        "atomically create the parent run ledger before any child or model write",
        "verify lakehouse configuration/contracts and ensure event CDC is RUNNING with a completed checkpoint",
        "apply models and run DQC against populated CDC facts before any business write",
        "Catalog: define and activate one Style/SPU plus six apparel SKU",
        "compatibility: create or replay 18 Mall/ERP/WMS PENDING identity projections",
        "master data: link one real Principal and activate its Merchant, Shop, and Warehouse network",
        "authority: pass the canonical Merchant, Shop, Principal, and Warehouse ledger into commerce",
        "commerce: execute governed Listing/Fulfillment steps 1-19 to Order COMPLETED",
        "after-sales: request, approve, hand over, move in transit, receive, and accept inspection",
        "resolution: poll the backend-owned Saga; Agent issues no participant write",
        "idempotency: replay all 25 client writes as immutable duplicates",
        "lakehouse: perform only read-only Catalog and after-sales reconciliation after CDC",
        "retain all refund, return, Outbox, CDC, lakehouse, and ledger evidence",
    ]


def execute(args: argparse.Namespace, manifest: dict) -> dict:
    run_ids = child_run_ids(args.run_id)
    scenario = json.loads(SCENARIO_FILE.read_text(encoding="utf-8"))
    ledger = AtomicRunLedger(parent_ledger_path(args), {
        "scenario": "yshopping-aftersales-vertical-v1",
        "run_id": args.run_id,
        "environment": args.environment,
        "tenant": args.tenant,
        "source_commit": source_commit(args.workspace),
        "endpoint_manifest_hash": endpoint_fingerprint(manifest),
        "scenario_contract_hash": sha256_json(scenario),
        "child_run_ids": run_ids,
    })
    lakehousectl = lakehousectl_path(args)
    try:
        capabilities = require_lakehouse_capabilities(lakehousectl)
        preflight = {}
        for command in ("config-check", "contract-test"):
            step = ledger.before_request("lakehouse", str(lakehousectl), {
                "operation": command,
                "mode": "governed-preflight",
            })
            result = run_lakehouse(lakehousectl, command)
            ledger.after_request(step, {"status": "succeeded", "output": result})
            preflight[command] = result

        step = ledger.before_request("lakehouse", str(lakehousectl), {
            "operation": "ensure-event-cdc",
            "mode": "governed-preflight",
            "flink_rest_url": args.flink_rest_url,
        })
        cdc_preflight = ensure_event_cdc(
            lakehousectl, args.flink_rest_url, args.cdc_timeout, args.cdc_poll_interval)
        ledger.after_request(step, cdc_preflight)
        preflight["ensure-event-cdc"] = cdc_preflight

        for command in ("apply-models", "test"):
            step = ledger.before_request("lakehouse", str(lakehousectl), {
                "operation": command,
                "mode": "governed-preflight",
            })
            result = run_lakehouse(lakehousectl, command)
            ledger.after_request(step, {"status": "succeeded", "output": result})
            preflight[command] = result

        catalog = record_child(ledger, "catalog", [
            sys.executable, str(CATALOG_RUNNER), *child_common(args, run_ids["catalog"])
        ])
        projection = record_child(ledger, "projection", [
            sys.executable, str(PROJECTION_RUNNER), *child_common(args, run_ids["projection"]),
            "--catalog-ledger", catalog["ledger"],
        ])
        master = record_child(ledger, "master", [
            sys.executable, str(MASTER_RUNNER), *child_common(args, run_ids["master"]),
            "--system-admin-source-id", args.system_admin_source_id,
            "--erp-warehouse-source-id", args.erp_warehouse_source_id,
            "--catalog-ledger", catalog["ledger"],
            "--listing-mode", "defer",
        ])
        aftersales = record_child(ledger, "aftersales", [
            sys.executable, str(AFTERSALES_RUNNER), *child_common(args, run_ids["aftersales"]),
            "--workspace", args.workspace,
            "--endpoint-manifest", args.endpoint_manifest,
            "--catalog-ledger", catalog["ledger"],
            "--master-ledger", master["ledger"],
            "--saga-timeout", str(args.saga_timeout),
            "--poll-interval", str(args.poll_interval),
        ])

        require(catalog.get("catalog_status") == "ACTIVE" and catalog.get("sku_count") == 6,
                f"Catalog terminal invariant failed: {catalog}")
        require(projection.get("projection_count") == 18,
                f"projection terminal invariant failed: {projection}")
        require(master.get("merchant_status") == "ACTIVE"
                and master.get("shop_status") == "ACTIVE"
                and master.get("warehouse_status") == "ACTIVE"
                and master.get("all_replay_duplicate") is True
                and master.get("listing_status") == "DEFERRED_TO_COMMERCE"
                and master.get("write_command_count") in (6, 7, 14, 15),
                f"canonical master-data invariant failed: {master}")
        require(aftersales.get("master_identity", {}).get("merchant_id") == master["merchant_id"]
                and aftersales.get("master_identity", {}).get("shop_id") == master["shop_id"]
                and aftersales.get("master_identity", {}).get("principal_id") == master["principal_id"]
                and aftersales.get("master_identity", {}).get("warehouse_id") == master["warehouse_id"],
                "commerce did not preserve the exact canonical master identities")
        require(aftersales.get("all_replay_duplicate") is True
                and aftersales.get("client_command_count") == 25,
                f"after-sales idempotency invariant failed: {aftersales}")

        catalog_reconcile = reconcile_read_only([
            str(lakehousectl), "reconcile-canonical-catalog", "--tenant", str(args.tenant),
            "--run-id", run_ids["catalog"],
        ], args.cdc_timeout, args.cdc_poll_interval)
        merchant_reconcile = reconcile_read_only([
            str(lakehousectl), "reconcile-canonical-merchant", "--tenant", str(args.tenant),
            "--merchant-id", master["merchant_id"], "--source-system", "SYSTEM",
            "--source-type", "SYSTEM_ADMIN_USER", "--source-id", args.system_admin_source_id,
        ], args.cdc_timeout, args.cdc_poll_interval)
        warehouse_reconcile = reconcile_read_only([
            str(lakehousectl), "reconcile-canonical-warehouse-network", "--tenant", str(args.tenant),
            "--warehouse-id", master["warehouse_id"], "--source-system", "ERP",
            "--source-type", "WAREHOUSE", "--source-id", args.erp_warehouse_source_id,
        ], args.cdc_timeout, args.cdc_poll_interval)
        aftersales_reconcile = reconcile_read_only([
            str(lakehousectl), "reconcile-canonical-aftersales", "--tenant", str(args.tenant),
            "--run-id", run_ids["aftersales"],
        ], args.cdc_timeout, args.cdc_poll_interval)

        final = {
            "catalog_status": "ACTIVE",
            "projection_count": 18,
            "principal_id": master["principal_id"],
            "merchant_id": master["merchant_id"],
            "shop_id": master["shop_id"],
            "warehouse_id": master["warehouse_id"],
            "canonical_sku_id": aftersales["canonical_sku_id"],
            "aftersales_id": aftersales["aftersales_id"],
            "aftersales": aftersales["aftersales"],
            "all_replay_duplicate": True,
            "lakehouse_reconciled": True,
            "cleanup_policy": "retain; never delete refunded business evidence",
        }
        ledger.data["children"] = {
            "catalog": catalog,
            "projection": projection,
            "master": master,
            "aftersales": aftersales,
        }
        ledger.data["lakehouse"] = {
            "capabilities": sorted(capabilities),
            "preflight": preflight,
            "catalog_reconcile": catalog_reconcile,
            "merchant_reconcile": merchant_reconcile,
            "warehouse_reconcile": warehouse_reconcile,
            "aftersales_reconcile": aftersales_reconcile,
            "post_timeout_policy": "read-only reconcile; no business write",
        }
        ledger.finish("SUCCEEDED", final)
        return {"status": "succeeded", "run_id": args.run_id, "ledger": str(ledger.path), **final}
    except Exception as exc:
        ledger.finish("FAILED", error=str(exc))
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "dry-run", "execute"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", default="local")
    parser.add_argument("--base-url", default=os.getenv(
        "CLOUDMOLD_ERP_BASE_URL", "http://127.0.0.1:48080"))
    parser.add_argument("--tenant", type=int, default=int(os.getenv("CLOUDMOLD_TENANT_ID", "1")))
    parser.add_argument("--workspace", default=os.getenv(
        "CLOUDMOLD_WORKSPACE", "/Users/karekin/Downloads/coding/project/CloudMold"))
    parser.add_argument("--endpoint-manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--system-admin-source-id", default=os.getenv(
        "CLOUDMOLD_SYSTEM_ADMIN_SOURCE_ID"))
    parser.add_argument("--erp-warehouse-source-id", default=os.getenv(
        "CLOUDMOLD_ERP_WAREHOUSE_SOURCE_ID"))
    parser.add_argument("--http-timeout", type=int, default=20)
    parser.add_argument("--saga-timeout", type=float, default=120)
    parser.add_argument("--poll-interval", type=float, default=1)
    parser.add_argument("--cdc-timeout", type=int, default=120)
    parser.add_argument("--cdc-poll-interval", type=int, default=5)
    parser.add_argument("--flink-rest-url", default=os.getenv(
        "CLOUDMOLD_FLINK_REST_URL", "http://127.0.0.1:8081"))
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    try:
        require(bool(RUN_ID_PATTERN.fullmatch(args.run_id)),
                "run_id must be 6-20 characters using letters, digits, dot, underscore, or hyphen")
        require(args.environment in {"local", "demo", "test"},
                "the Y-Shopping after-sales runner is restricted to local, demo, or test")
        require(args.cdc_timeout > 0 and args.cdc_poll_interval > 0
                and args.saga_timeout > 0 and args.poll_interval > 0,
                "polling timeouts and intervals must be positive")
        if args.mode == "execute":
            require(bool(args.system_admin_source_id),
                    "execute requires --system-admin-source-id for canonical master data")
            require(bool(args.erp_warehouse_source_id),
                    "execute requires --erp-warehouse-source-id for canonical master data")
        manifest = load_endpoint_manifest(args.endpoint_manifest)
        run_ids = child_run_ids(args.run_id)
        if args.mode == "plan":
            result = {
                "scenario": "yshopping-aftersales-vertical-v1",
                "run_id": args.run_id,
                "child_run_ids": run_ids,
                "flow": scenario_plan(),
                "required_lakehouse_commands": list(REQUIRED_LAKEHOUSE_COMMANDS),
                "side_effects": False,
            }
        elif args.mode == "dry-run":
            capabilities = require_lakehouse_capabilities(lakehousectl_path(args))
            catalog = run_json([
                sys.executable, str(CATALOG_RUNNER), *child_common(args, run_ids["catalog"])
            ])
            projection = run_json([
                sys.executable, str(PROJECTION_RUNNER), *child_common(args, run_ids["projection"])
            ])
            master = run_json([
                sys.executable, str(MASTER_RUNNER), *child_common(args, run_ids["master"])
            ])
            aftersales = run_json([
                sys.executable, str(AFTERSALES_RUNNER), *child_common(args, run_ids["aftersales"]),
                "--workspace", args.workspace,
                "--endpoint-manifest", args.endpoint_manifest,
                "--sku-id", "dry-run-canonical-sku",
                "--spu-id", "dry-run-canonical-spu",
            ])
            result = {
                "status": "ready",
                "run_id": args.run_id,
                "catalog_routes": catalog.get("routes"),
                "projection_route": projection.get("route"),
                "master_routes": master.get("routes"),
                "aftersales_routes": aftersales.get("routes"),
                "lakehouse_capabilities": sorted(capabilities),
                "side_effects": False,
            }
        else:
            result = execute(args, manifest)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ScenarioError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
