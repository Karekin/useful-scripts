#!/usr/bin/env python3
"""Prove durable physical Listing unpublish after Merchant/Shop ineligibility."""

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
import urllib.error
import urllib.parse
import urllib.request
import uuid


MERCHANT_ROUTE = "/admin-api/cloudmold/merchant/command"
LISTING_ROUTE = "/admin-api/cloudmold/listing/command"
OFFER_ROUTE = "/admin-api/cloudmold/listing/offer/validate"
SAGA_ROUTE = "/admin-api/cloudmold/listing-unpublish-saga/get"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{5,31}$")


class ScenarioError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ScenarioError(message)


def request_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def scenario_context(run_id: str) -> tuple[str, dt.datetime]:
    digest = hashlib.sha256(run_id.encode()).hexdigest()
    correlation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:sales-eligibility:{run_id}"))
    seconds = int(digest[:8], 16) % (365 * 24 * 60 * 60)
    return correlation_id, dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=seconds)


def iso_time(value: dt.datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def load_master_ledger(path_value: str | None, tenant: int) -> dict:
    require(bool(path_value), "execute requires --master-ledger from a SUCCEEDED canonical master run")
    path = Path(path_value).expanduser().resolve()
    require(path.is_file(), f"master ledger does not exist: {path}")
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenarioError(f"cannot read master ledger: {exc}") from exc
    require(ledger.get("scenario") == "canonical-merchant-warehouse-first-slice-v1",
            "master ledger has an unexpected scenario")
    require(ledger.get("status") == "SUCCEEDED", "master ledger is not SUCCEEDED")
    require(ledger.get("tenant") == tenant, "master ledger tenant does not match")
    final = ledger.get("final") or {}
    require(final.get("merchant_status") == "ACTIVE", "master ledger Merchant is not ACTIVE")
    require(final.get("shop_status") == "ACTIVE", "master ledger Shop is not ACTIVE")
    require(final.get("listing_status") == "PUBLISHED", "master ledger Listing is not PUBLISHED")
    create_steps = [step for step in ledger.get("steps", [])
                    if step.get("domain") == "listing" and step.get("operation") == "CREATE_DRAFT"]
    require(len(create_steps) == 1, "master ledger must contain exactly one Listing CREATE_DRAFT")
    offers = (create_steps[0].get("result") or {}).get("offers") or []
    enabled = [offer for offer in offers if offer.get("enabled") is True]
    require(len(enabled) == 1, "master ledger must contain exactly one enabled Listing offer")
    offer = enabled[0]
    required = ("principal_id", "merchant_id", "shop_id", "listing_id", "canonical_sku_id")
    require(all(isinstance(final.get(key), str) and final.get(key) for key in required),
            "master ledger is missing canonical identifiers")
    require(isinstance(offer.get("listingOfferId"), str) and offer.get("listingOfferId"),
            "master ledger offer has no canonical ID")
    return {
        "path": str(path), "principal_id": final["principal_id"],
        "merchant_id": final["merchant_id"], "shop_id": final["shop_id"],
        "listing_id": final["listing_id"], "listing_offer_id": offer["listingOfferId"],
        "canonical_sku_id": final["canonical_sku_id"], "price_minor": offer["priceMinor"],
        "currency_code": offer["currencyCode"],
    }


def load_prior_versions(path_value: str | None, master: dict, tenant: int) -> tuple[int, int, str | None]:
    if not path_value:
        return 2, 2, None
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
    require(refs.get("merchant_id") == master["merchant_id"] and refs.get("shop_id") == master["shop_id"],
            "prior eligibility ledger belongs to a different Merchant or Shop")
    final = ledger.get("final") or {}
    merchant_version, shop_version = final.get("merchant_version"), final.get("shop_version")
    require(isinstance(merchant_version, int) and merchant_version >= 2,
            "prior eligibility ledger has no valid Merchant version")
    require(isinstance(shop_version, int) and shop_version >= 2,
            "prior eligibility ledger has no valid Shop version")
    require(final.get("merchant_status") == "ACTIVE" and final.get("shop_status") == "ACTIVE",
            "prior eligibility ledger did not leave Merchant and Shop ACTIVE")
    return merchant_version, shop_version, str(path)


class Client:
    def __init__(self, base_url: str, tenant: int, token: str | None, timeout: int):
        self.base_url, self.tenant, self.token, self.timeout = base_url.rstrip("/"), tenant, token, timeout

    def envelope(self, method: str, path: str, payload: dict | None = None,
                 authenticated: bool = True) -> dict:
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json", "tenant-id": str(self.tenant)}
        if authenticated:
            require(bool(self.token), "authenticated request requires a token")
            headers["Authorization"] = "Bearer " + self.token
        request = urllib.request.Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode()
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
        except urllib.error.URLError as exc:
            raise ScenarioError(f"request failed for {method} {path}: {exc}") from exc
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ScenarioError(f"invalid API result for {method} {path}: {raw[:500]}") from exc
        require(isinstance(result, dict), f"API returned no result envelope for {method} {path}")
        return result

    def request(self, method: str, path: str, payload: dict | None = None,
                authenticated: bool = True) -> dict:
        result = self.envelope(method, path, payload, authenticated)
        require(result.get("code") == 0,
                f"API rejected {method} {path}: {result.get('code')} {result.get('msg')}")
        return result.get("data") if isinstance(result.get("data"), dict) else {"value": result.get("data")}

    def expect_rejected(self, path: str, payload: dict) -> dict:
        result = self.envelope("POST", path, payload)
        require(result.get("code") not in (None, 0), "expected fail-closed offer rejection")
        return {"code": result.get("code"), "rejected": True}

    def login(self, username: str, password: str) -> None:
        data = self.request("POST", "/admin-api/system/auth/login",
                            {"username": username, "password": password}, authenticated=False)
        require(isinstance(data.get("accessToken"), str) and data.get("accessToken"),
                "login response has no access token")
        self.token = data["accessToken"]

    def openapi(self) -> dict:
        try:
            with urllib.request.urlopen(self.base_url + "/v3/api-docs", timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise ScenarioError(f"cannot read live OpenAPI: {exc}") from exc


class Ledger:
    def __init__(self, args: argparse.Namespace, master: dict):
        root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
        directory = root / "merchant-sales-eligibility" / args.run_id
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "ledger.json"
        if target.exists():
            target = directory / ("replay-ledger-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
        self.path = target
        self.value = {
            "scenario": "canonical-merchant-sales-eligibility-v1", "run_id": args.run_id,
            "environment": args.environment, "tenant": args.tenant, "master_ledger": master["path"],
            "prior_eligibility_ledger": args.prior_eligibility_ledger,
            "canonical_refs": {key: master[key] for key in
                               ("principal_id", "merchant_id", "shop_id", "listing_id",
                                "listing_offer_id", "canonical_sku_id")},
            "steps": [], "status": "STARTED",
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


def lifecycle_command(operation: str, run_id: str, index: int, correlation_id: str,
                      occurred_at: dt.datetime, **values: object) -> dict:
    payload = {
        "operation": operation,
        "idempotencyKey": f"{run_id}-{index:02d}-{operation.lower().replace('_', '-')}",
        "runId": run_id, "sourceSystem": "cloudmold-erp-operator",
        "traceId": f"canonical-merchant-sales-eligibility:{run_id}",
        "correlationId": correlation_id, "occurredAt": iso_time(occurred_at + dt.timedelta(seconds=index)),
    }
    payload.update(values)
    return payload


def execute(args: argparse.Namespace) -> dict:
    master = load_master_ledger(args.master_ledger, args.tenant)
    merchant_version, shop_version, prior_path = load_prior_versions(
        args.prior_eligibility_ledger, master, args.tenant)
    args.prior_eligibility_ledger = prior_path
    client = Client(args.base_url, args.tenant, args.token, args.timeout)
    if not client.token:
        require(bool(args.username) and bool(args.password),
                "set token or username/password through environment variables")
        client.login(args.username, args.password)
    ledger = Ledger(args, master)
    correlation_id, occurred_at = scenario_context(args.run_id)
    offer_payload = {
        "listingId": master["listing_id"], "listingOfferId": master["listing_offer_id"],
        "canonicalSkuId": master["canonical_sku_id"], "expectedPriceMinor": master["price_minor"],
        "currencyCode": master["currency_code"],
    }
    issued: list[tuple[str, str, dict, dict]] = []

    def validate(label: str) -> None:
        result = client.request("POST", OFFER_ROUTE, offer_payload)
        require(result.get("merchantId") == master["merchant_id"], f"{label}: Merchant mismatch")
        require(result.get("shopId") == master["shop_id"], f"{label}: Shop mismatch")
        require(result.get("listingOfferId") == master["listing_offer_id"], f"{label}: Offer mismatch")
        ledger.append("offer_gate", label, offer_payload, {"sellable": True})

    def reject(label: str) -> None:
        ledger.append("offer_gate", label, offer_payload, client.expect_rejected(OFFER_ROUTE, offer_payload))

    def issue_merchant(operation: str, index: int, **values: object) -> dict:
        payload = lifecycle_command(operation, args.run_id, index, correlation_id, occurred_at, **values)
        result = client.request("POST", MERCHANT_ROUTE, payload)
        ledger.append("merchant_command", operation, payload, result)
        issued.append((MERCHANT_ROUTE, operation, payload, result))
        return result

    def publish(index: int, expected_version: int, cause: str) -> dict:
        payload = {
            "operation": "PUBLISH",
            "idempotencyKey": f"{args.run_id}-{index:02d}-publish-listing",
            "runId": args.run_id,
            "listingId": master["listing_id"],
            "expectedVersion": expected_version,
            "sourceSystem": "cloudmold-erp-operator",
            "publisherRef": master["principal_id"],
            "reason": cause,
            "correlationId": correlation_id,
            "occurredAt": iso_time(occurred_at + dt.timedelta(seconds=index)),
        }
        result = client.request("POST", LISTING_ROUTE, payload)
        require(result.get("currentStatus") == "PUBLISHED", "manual Listing republish did not succeed")
        ledger.append("listing_command", "PUBLISH", payload, result)
        issued.append((LISTING_ROUTE, "PUBLISH", payload, result))
        return result

    def wait_saga(saga_id: str, label: str) -> dict:
        require(isinstance(saga_id, str) and saga_id, f"{label}: lifecycle result has no Saga ID")
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            path = SAGA_ROUTE + "?sagaId=" + urllib.parse.quote(saga_id, safe="")
            result = client.request("GET", path)
            status = result.get("status")
            if status == "COMPLETED":
                require(result.get("expectedListingCount") == result.get("unpublishedListingCount", 0)
                        + result.get("skippedListingCount", 0), f"{label}: frozen Listing count is incomplete")
                target = [item for item in result.get("items", [])
                          if item.get("listingId") == master["listing_id"]]
                require(len(target) == 1, f"{label}: exact master Listing is not in the frozen workset")
                require(target[0].get("status") == "UNPUBLISHED",
                        f"{label}: exact master Listing was not physically unpublished")
                require(isinstance(target[0].get("finalListingVersion"), int),
                        f"{label}: terminal Listing version is missing")
                ledger.append("saga_query", label, {"sagaId": saga_id}, result)
                return result
            require(status != "MANUAL_REVIEW", f"{label}: Saga requires manual review")
            time.sleep(0.25)
        raise ScenarioError(f"{label}: timed out waiting for Listing unpublish Saga")

    validate("INITIAL_ACTIVE")
    suspended = issue_merchant("SUSPEND_MERCHANT", 1, merchantId=master["merchant_id"],
                               expectedVersion=merchant_version,
                               reason="physical Listing unpublish runtime proof")
    require((suspended.get("merchantStatus"), suspended.get("merchantVersion"))
            == ("SUSPENDED", merchant_version + 1), "Merchant did not reach SUSPENDED")
    try:
        merchant_saga = wait_saga(suspended.get("listingUnpublishSagaId"), "MERCHANT_SUSPENDED_SAGA")
        reject("MERCHANT_SUSPENDED")
    finally:
        resumed_merchant = issue_merchant("RESUME_MERCHANT", 2, merchantId=master["merchant_id"],
                                          expectedVersion=merchant_version + 1)
    require((resumed_merchant.get("merchantStatus"), resumed_merchant.get("merchantVersion"))
            == ("ACTIVE", merchant_version + 2), "Merchant did not return to ACTIVE")
    reject("MERCHANT_RESUMED_NO_AUTO_REPUBLISH")
    merchant_item = next(item for item in merchant_saga["items"] if item["listingId"] == master["listing_id"])
    merchant_publish = publish(3, merchant_item["finalListingVersion"], "manual review after Merchant resume")
    validate("MERCHANT_RESUMED_MANUALLY_REPUBLISHED")
    paused = issue_merchant("PAUSE_SHOP", 4, shopId=master["shop_id"], expectedVersion=shop_version,
                            reason="physical Listing unpublish runtime proof")
    require((paused.get("shopStatus"), paused.get("shopVersion")) == ("PAUSED", shop_version + 1),
            "Shop did not reach PAUSED")
    try:
        shop_saga = wait_saga(paused.get("listingUnpublishSagaId"), "SHOP_PAUSED_SAGA")
        reject("SHOP_PAUSED")
    finally:
        resumed_shop = issue_merchant("RESUME_SHOP", 5, shopId=master["shop_id"],
                                      expectedVersion=shop_version + 1)
    require((resumed_shop.get("shopStatus"), resumed_shop.get("shopVersion"))
            == ("ACTIVE", shop_version + 2), "Shop did not return to ACTIVE")
    reject("SHOP_RESUMED_NO_AUTO_REPUBLISH")
    shop_item = next(item for item in shop_saga["items"] if item["listingId"] == master["listing_id"])
    shop_publish = publish(6, shop_item["finalListingVersion"], "manual review after Shop resume")
    validate("SHOP_RESUMED_MANUALLY_REPUBLISHED")

    replay = []
    for route, operation, payload, first in issued:
        result = client.request("POST", route, payload)
        require(result.get("duplicate") is True, f"{operation} replay was not duplicate")
        require({k: v for k, v in result.items() if k != "duplicate"}
                == {k: v for k, v in first.items() if k != "duplicate"},
                f"{operation} replay changed the immutable result")
        replay.append({"operation": operation, "duplicate": True})
    final = {"merchant_status": "ACTIVE", "merchant_version": merchant_version + 2,
             "shop_status": "ACTIVE", "shop_version": shop_version + 2,
             "listing_status": "PUBLISHED", "listing_version": shop_publish["aggregateVersion"],
             "merchant_unpublish_saga_id": merchant_saga["sagaId"],
             "shop_unpublish_saga_id": shop_saga["sagaId"],
             "merchant_republish_version": merchant_publish["aggregateVersion"],
             "offer_sellable": True, "resume_auto_republish": False,
             "write_command_count": len(issued),
             "all_replay_duplicate": len(replay) == len(issued)}
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
            result = {"scenario": "canonical-merchant-sales-eligibility-v1", "run_id": args.run_id,
                      "flow": ["suspend Merchant, wait for exact frozen Listing workset to be physically unpublished",
                               "resume Merchant without automatic republish, then manually publish",
                               "pause Shop, wait for physical unpublish, resume without automatic republish",
                               "manually publish and replay all six writes as immutable duplicates"],
                      "side_effects": False}
        elif args.mode == "dry-run":
            paths = Client(args.base_url, args.tenant, args.token, args.timeout).openapi().get("paths", {})
            required = {MERCHANT_ROUTE: "post", LISTING_ROUTE: "post", OFFER_ROUTE: "post", SAGA_ROUTE: "get"}
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
