#!/usr/bin/env python3
"""Prove the canonical Merchant deposit threshold and Listing safety workflow."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.parse
import uuid

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from canonical_merchant_sales_eligibility_runner import (
    Client,
    ScenarioError,
    iso_time,
    load_master_ledger,
    request_hash,
    require,
)


DEPOSIT_COMMAND_ROUTE = "/admin-api/cloudmold/merchant/deposit/command"
DEPOSIT_CURRENT_ROUTE = "/admin-api/cloudmold/merchant/deposit/current"
MERCHANT_ROUTE = "/admin-api/cloudmold/merchant/command"
LISTING_ROUTE = "/admin-api/cloudmold/listing/command"
OFFER_ROUTE = "/admin-api/cloudmold/listing/offer/validate"
SAGA_ROUTE = "/admin-api/cloudmold/listing-unpublish-saga/get"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{5,31}$")
SCENARIO = "canonical-merchant-deposit-v1"
POLICY_VERSION = "YS-DEPOSIT-2026-01"


def scenario_context(run_id: str) -> tuple[str, dt.datetime]:
    digest = hashlib.sha256(run_id.encode()).hexdigest()
    correlation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:merchant-deposit:{run_id}"))
    seconds = int(digest[:8], 16) % (365 * 24 * 60 * 60)
    return correlation_id, dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=seconds)


def load_prior_state(path_value: str | None, master: dict, tenant: int) -> dict:
    require(bool(path_value), "execute requires --prior-eligibility-ledger from a SUCCEEDED physical-unpublish run")
    path = Path(path_value).expanduser().resolve()
    require(path.is_file(), f"prior eligibility ledger does not exist: {path}")
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenarioError(f"cannot read prior eligibility ledger: {exc}") from exc
    require(ledger.get("scenario") == "canonical-merchant-sales-eligibility-v1",
            "prior eligibility ledger has an unexpected scenario")
    require(ledger.get("status") == "SUCCEEDED", "prior eligibility ledger is not SUCCEEDED")
    require(ledger.get("tenant") == tenant, "prior eligibility ledger tenant does not match")
    refs = ledger.get("canonical_refs") or {}
    require(all(refs.get(key) == master[key] for key in
                ("merchant_id", "shop_id", "listing_id", "listing_offer_id", "canonical_sku_id")),
            "prior eligibility ledger belongs to different canonical entities")
    final = ledger.get("final") or {}
    require(final.get("merchant_status") == "ACTIVE", "prior run did not leave Merchant ACTIVE")
    require(final.get("listing_status") == "PUBLISHED", "prior run did not leave Listing PUBLISHED")
    require(isinstance(final.get("merchant_version"), int) and final["merchant_version"] > 0,
            "prior run has no Merchant version")
    require(isinstance(final.get("listing_version"), int) and final["listing_version"] > 0,
            "prior run has no Listing version")
    return {"path": str(path), "merchant_version": final["merchant_version"],
            "listing_version": final["listing_version"]}


class Ledger:
    def __init__(self, args: argparse.Namespace, master: dict, prior: dict):
        root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
        directory = root / "merchant-deposit" / args.run_id
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "ledger.json"
        if target.exists():
            suffix = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            target = directory / f"replay-ledger-{suffix}.json"
        self.path = target
        self.value = {
            "scenario": SCENARIO,
            "run_id": args.run_id,
            "environment": args.environment,
            "tenant": args.tenant,
            "master_ledger": master["path"],
            "prior_eligibility_ledger": prior["path"],
            "policy_version": POLICY_VERSION,
            "canonical_refs": {key: master[key] for key in
                               ("principal_id", "merchant_id", "shop_id", "listing_id",
                                "listing_offer_id", "canonical_sku_id")},
            "steps": [],
            "status": "STARTED",
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
    master = load_master_ledger(args.master_ledger, args.tenant)
    prior = load_prior_state(args.prior_eligibility_ledger, master, args.tenant)
    client = Client(args.base_url, args.tenant, args.token, args.timeout)
    if not client.token:
        require(bool(args.username) and bool(args.password),
                "set token or username/password through environment variables")
        client.login(args.username, args.password)
    ledger = Ledger(args, master, prior)
    correlation_id, occurred_at = scenario_context(args.run_id)
    offer_payload = {
        "listingId": master["listing_id"], "listingOfferId": master["listing_offer_id"],
        "canonicalSkuId": master["canonical_sku_id"], "expectedPriceMinor": master["price_minor"],
        "currencyCode": master["currency_code"],
    }
    issued: list[tuple[str, str, dict, dict]] = []

    def validate_offer(label: str) -> None:
        result = client.request("POST", OFFER_ROUTE, offer_payload)
        require(result.get("merchantId") == master["merchant_id"], f"{label}: Merchant mismatch")
        require(result.get("listingOfferId") == master["listing_offer_id"], f"{label}: Offer mismatch")
        ledger.append("offer_gate", label, offer_payload, {"sellable": True})

    def reject_offer(label: str) -> None:
        ledger.append("offer_gate", label, offer_payload, client.expect_rejected(OFFER_ROUTE, offer_payload))

    def deposit(operation: str, index: int, version: int | None, amount: int | None,
                expected_coverage: str, expected_held: int, expected_frozen: int) -> dict:
        payload = {
            "operation": operation,
            "idempotencyKey": f"{args.run_id}-{index:02d}-{operation.lower().replace('_', '-')}",
            "runId": args.run_id,
            "merchantId": master["merchant_id"],
            "expectedAccountVersion": version,
            "amountMinor": amount,
            "currency": "CNY",
            "policyVersion": POLICY_VERSION,
            "businessReference": f"{args.run_id}:deposit:{index:02d}",
            "reasonCode": f"RUNTIME_{operation}",
            "evidenceRef": f"run:{args.run_id}/deposit/{index:02d}",
            "sourceSystem": "cloudmold-erp-operator",
            "traceId": f"canonical-merchant-deposit:{args.run_id}",
            "correlationId": correlation_id,
            "occurredAt": iso_time(occurred_at + dt.timedelta(seconds=index)),
        }
        result = client.request("POST", DEPOSIT_COMMAND_ROUTE, payload)
        expected_version = 1 if version is None else version + 1
        require(result.get("accountVersion") == expected_version,
                f"{operation}: account version mismatch")
        require(result.get("coverageStatus") == expected_coverage,
                f"{operation}: coverage status mismatch")
        require(result.get("heldAmountMinor") == expected_held,
                f"{operation}: held amount mismatch")
        require(result.get("frozenAmountMinor") == expected_frozen,
                f"{operation}: frozen amount mismatch")
        require(result.get("availableAmountMinor") == expected_held - expected_frozen,
                f"{operation}: available amount mismatch")
        ledger.append("deposit_command", operation, payload, result)
        issued.append((DEPOSIT_COMMAND_ROUTE, operation, payload, result))
        return result

    def resume_merchant(index: int, expected_version: int) -> dict:
        payload = {
            "operation": "RESUME_MERCHANT",
            "idempotencyKey": f"{args.run_id}-{index:02d}-resume-merchant",
            "runId": args.run_id,
            "merchantId": master["merchant_id"],
            "expectedVersion": expected_version,
            "sourceSystem": "cloudmold-erp-operator",
            "traceId": f"canonical-merchant-deposit:{args.run_id}",
            "correlationId": correlation_id,
            "occurredAt": iso_time(occurred_at + dt.timedelta(seconds=index)),
        }
        result = client.request("POST", MERCHANT_ROUTE, payload)
        require((result.get("merchantStatus"), result.get("merchantVersion"))
                == ("ACTIVE", expected_version + 1), "Merchant did not explicitly resume")
        ledger.append("merchant_command", "RESUME_MERCHANT", payload, result)
        issued.append((MERCHANT_ROUTE, "RESUME_MERCHANT", payload, result))
        return result

    def publish_listing(index: int, expected_version: int) -> dict:
        payload = {
            "operation": "PUBLISH",
            "idempotencyKey": f"{args.run_id}-{index:02d}-publish-listing",
            "runId": args.run_id,
            "listingId": master["listing_id"],
            "expectedVersion": expected_version,
            "sourceSystem": "cloudmold-erp-operator",
            "publisherRef": master["principal_id"],
            "reason": "manual review after deposit replenishment and Merchant resume",
            "correlationId": correlation_id,
            "occurredAt": iso_time(occurred_at + dt.timedelta(seconds=index)),
        }
        result = client.request("POST", LISTING_ROUTE, payload)
        require(result.get("currentStatus") == "PUBLISHED", "Listing did not explicitly republish")
        ledger.append("listing_command", "PUBLISH", payload, result)
        issued.append((LISTING_ROUTE, "PUBLISH", payload, result))
        return result

    def wait_saga(saga_id: str) -> dict:
        require(isinstance(saga_id, str) and saga_id, "deposit threshold crossing returned no Saga ID")
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            path = SAGA_ROUTE + "?sagaId=" + urllib.parse.quote(saga_id, safe="")
            result = client.request("GET", path)
            if result.get("status") == "COMPLETED":
                target = [item for item in result.get("items", [])
                          if item.get("listingId") == master["listing_id"]]
                require(len(target) == 1 and target[0].get("status") == "UNPUBLISHED",
                        "exact canonical Listing was not physically unpublished")
                require(isinstance(target[0].get("finalListingVersion"), int),
                        "Saga omitted terminal Listing version")
                ledger.append("saga_query", "DEPOSIT_SALES_BLOCKED_SAGA", {"sagaId": saga_id}, result)
                return result
            require(result.get("status") != "MANUAL_REVIEW", "deposit Saga requires manual review")
            time.sleep(0.25)
        raise ScenarioError("timed out waiting for deposit Listing unpublish Saga")

    validate_offer("INITIAL_ACTIVE")
    assessed = deposit("ASSESS_REQUIRED", 1, None, 10_000, "SALES_BLOCKED", 0, 0)
    require(assessed.get("enforcementStatus") == "SHADOW", "new deposit account is not SHADOW")
    paid = deposit("PAY", 2, 1, 10_000, "SUFFICIENT", 10_000, 0)
    activated = deposit("ACTIVATE_ENFORCEMENT", 3, 2, 0, "SUFFICIENT", 10_000, 0)
    require(activated.get("enforcementStatus") == "ENFORCED", "deposit enforcement did not activate")
    frozen = deposit("FREEZE", 4, 3, 1_000, "SUFFICIENT", 10_000, 1_000)
    require(frozen.get("availableAmountMinor") == 9_000, "freeze did not reduce available deposit")
    validate_offer("FROZEN_DEPOSIT_REMAINS_SELLABLE")
    deposit("UNFREEZE", 5, 4, 1_000, "SUFFICIENT", 10_000, 0)
    restricted = deposit("DEDUCT", 6, 5, 4_500, "BID_RESTRICTED", 5_500, 0)
    require((restricted.get("merchantStatus"), restricted.get("merchantVersion"))
            == ("ACTIVE", prior["merchant_version"]), "55 percent coverage incorrectly suspended Merchant")
    validate_offer("BID_RESTRICTED_STILL_SELLABLE")
    blocked = deposit("DEDUCT", 7, 6, 3_600, "SALES_BLOCKED", 1_900, 0)
    require((blocked.get("merchantStatus"), blocked.get("merchantVersion"))
            == ("SUSPENDED", prior["merchant_version"] + 1), "19 percent coverage did not suspend Merchant")
    saga = wait_saga(blocked.get("listingUnpublishSagaId"))
    reject_offer("SALES_BLOCKED_PHYSICALLY_UNPUBLISHED")
    replenished = deposit("PAY", 8, 7, 8_100, "SUFFICIENT", 10_000, 0)
    require((replenished.get("merchantStatus"), replenished.get("merchantVersion"))
            == ("SUSPENDED", prior["merchant_version"] + 1), "top-up incorrectly auto-resumed Merchant")
    reject_offer("TOP_UP_NO_AUTO_RESUME_OR_REPUBLISH")
    resumed = resume_merchant(9, prior["merchant_version"] + 1)
    reject_offer("RESUME_NO_AUTO_REPUBLISH")
    saga_item = next(item for item in saga["items"] if item["listingId"] == master["listing_id"])
    published = publish_listing(10, saga_item["finalListingVersion"])
    validate_offer("EXPLICIT_REVIEW_REPUBLISHED")

    current_path = DEPOSIT_CURRENT_ROUTE + "?" + urllib.parse.urlencode(
        {"merchantId": master["merchant_id"], "currency": "CNY"})
    current = client.request("GET", current_path)
    expected_current = {
        "accountVersion": 8, "requiredAmountMinor": 10_000, "heldAmountMinor": 10_000,
        "frozenAmountMinor": 0, "availableAmountMinor": 10_000, "paidAmountMinor": 18_100,
        "deductedAmountMinor": 8_100, "coverageStatus": "SUFFICIENT", "enforcementStatus": "ENFORCED",
    }
    require(all(current.get(key) == value for key, value in expected_current.items()),
            "current deposit projection does not match the conserved ledger")
    ledger.append("deposit_query", "CURRENT", {"merchantId": master["merchant_id"], "currency": "CNY"}, current)

    replay = []
    for route, operation, payload, first in issued:
        result = client.request("POST", route, payload)
        require(result.get("duplicate") is True, f"{operation} replay was not duplicate")
        require({key: value for key, value in result.items() if key != "duplicate"}
                == {key: value for key, value in first.items() if key != "duplicate"},
                f"{operation} replay changed its immutable result")
        replay.append({"operation": operation, "duplicate": True})

    final = {
        "merchant_status": resumed["merchantStatus"], "merchant_version": resumed["merchantVersion"],
        "listing_status": published["currentStatus"], "listing_version": published["aggregateVersion"],
        "deposit_account_version": current["accountVersion"], "coverage_status": current["coverageStatus"],
        "enforcement_status": current["enforcementStatus"], "held_amount_minor": current["heldAmountMinor"],
        "required_amount_minor": current["requiredAmountMinor"], "deposit_unpublish_saga_id": saga["sagaId"],
        "offer_sellable": True, "top_up_auto_resume": False, "resume_auto_republish": False,
        "deposit_write_count": 8, "total_write_count": len(issued),
        "all_replay_duplicate": len(replay) == len(issued),
    }
    ledger.value.update({"replay": replay, "final": final, "status": "SUCCEEDED"})
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
    parser.add_argument("--master-ledger", default=os.getenv("CLOUDMOLD_MASTER_LEDGER"))
    parser.add_argument("--prior-eligibility-ledger", default=os.getenv("CLOUDMOLD_PRIOR_ELIGIBILITY_LEDGER"))
    parser.add_argument("--timeout", type=int, default=30)
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
                "scenario": SCENARIO,
                "run_id": args.run_id,
                "flow": [
                    "assess 10000 minor units in SHADOW, pay in full, then explicitly activate enforcement",
                    "freeze and unfreeze 1000 while conserving held and available balances",
                    "deduct to 55 percent without suspension, then to 19 percent with causal Merchant suspension",
                    "wait for physical Listing unpublish; top-up and Merchant resume never auto-republish",
                    "explicitly republish after review and replay all ten writes as immutable duplicates",
                ],
                "side_effects": False,
            }
        elif args.mode == "dry-run":
            paths = Client(args.base_url, args.tenant, args.token, args.timeout).openapi().get("paths", {})
            required = {
                DEPOSIT_COMMAND_ROUTE: "post", DEPOSIT_CURRENT_ROUTE: "get", MERCHANT_ROUTE: "post",
                LISTING_ROUTE: "post", OFFER_ROUTE: "post", SAGA_ROUTE: "get",
            }
            missing = [f"{method.upper()} {path}" for path, method in required.items()
                       if method not in paths.get(path, {})]
            require(not missing, "live OpenAPI is missing " + ", ".join(missing))
            result = {"status": "ready", "routes": required, "side_effects": False}
        else:
            require(args.tenant > 0, "tenant must be positive")
            result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ScenarioError as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
