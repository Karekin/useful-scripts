#!/usr/bin/env python3
"""Plan and validate the governed CloudMold admin-to-UniApp Agent scenario.

This tool intentionally does not invent business success.  It produces a deterministic
plan, gates execute authority for local/demo/test, and accepts terminal evidence only
when every stage, replay invariant, and lakehouse reconciliation is present.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
DEFAULT_SCENARIO = ROOT / "contracts" / "cross-channel-agent-scenario-v1.json"
DEFAULT_BINDINGS = ROOT / "contracts" / "cross-channel-app-facade-bindings-v1.json"
DEFAULT_RECONCILIATION = (
    ROOT
    / "yml"
    / "yshopping-lakehouse"
    / "contracts"
    / "yshopping-cross-channel-agent-reconciliation-v1.json"
)
RUN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{5,63}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
EXECUTE_ENVIRONMENTS = {"local", "demo", "test"}
TERMINAL_SCOPES = {"LOCAL_TEST", "DEMO_TEST", "TEST"}
EXECUTABLE_AVAILABILITY = "IMPLEMENTED_AND_TESTED"


class CrossChannelAgentError(RuntimeError):
    """Fail-closed contract, approval, or evidence error."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CrossChannelAgentError(f"cannot load JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CrossChannelAgentError(f"JSON root must be an object: {path}")
    return value


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def stable_idempotency_key(run_id: str, stage_id: str) -> str:
    suffix = hashlib.sha256(f"{run_id}:{stage_id}".encode("utf-8")).hexdigest()[:24]
    return f"cca:{run_id}:{suffix}"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CrossChannelAgentError(message)


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _parse_time(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise CrossChannelAgentError(f"{field} must be ISO-8601") from error
    _require(parsed.tzinfo is not None, f"{field} must include timezone")
    return parsed.astimezone(timezone.utc)


def approval_digest(approval: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in approval.items() if key != "approvalDigest"}
    return digest(unsigned)


def validate_approval(
    approval: dict[str, Any],
    run_id: str,
    environment: str,
    required_scope: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    _require(approval.get("schema_version") == 1, "approval schema_version must be 1")
    _require(
        approval.get("approvalType") == "LOCAL_TEST_HUMAN_APPROVAL",
        "approvalType must be LOCAL_TEST_HUMAN_APPROVAL",
    )
    _require(approval.get("approved") is True, "approval must be explicitly approved")
    _require(approval.get("runId") == run_id, "approval runId mismatch")
    _require(approval.get("environment") == environment, "approval environment mismatch")
    _require(environment in EXECUTE_ENVIRONMENTS, "execute environment is not allowed")
    _require(_has_value(approval.get("approvalId")), "approvalId is required")
    _require(_has_value(approval.get("approvedBy")), "approvedBy is required")
    scopes = approval.get("scopes")
    _require(isinstance(scopes, list), "approval scopes must be a list")
    _require(required_scope in scopes, f"approval scope {required_scope} is required")
    approved_at = _parse_time(approval.get("approvedAt"), "approvedAt")
    expires_at = _parse_time(approval.get("expiresAt"), "expiresAt")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    _require(approved_at <= current, "approval is not active yet")
    _require(expires_at > current, "approval has expired")
    expected = approval_digest(approval)
    _require(approval.get("approvalDigest") == expected, "approvalDigest mismatch")
    return {
        "approvalId": approval["approvalId"],
        "approvedBy": approval["approvedBy"],
        "approvalDigest": expected,
        "expiresAt": approval["expiresAt"],
    }


def validate_contracts(
    scenario_path: Path = DEFAULT_SCENARIO,
    bindings_path: Path = DEFAULT_BINDINGS,
    reconciliation_path: Path = DEFAULT_RECONCILIATION,
) -> dict[str, Any]:
    scenario = load_json(scenario_path)
    bindings = load_json(bindings_path)
    reconciliation = load_json(reconciliation_path)

    _require(scenario.get("schema_version") == 1, "scenario schema_version must be 1")
    _require(
        scenario.get("default_mode") == "plan",
        "scenario default_mode must remain plan",
    )
    _require(
        set(scenario.get("allowed_execute_environments", [])) == EXECUTE_ENVIRONMENTS,
        "allowed execute environments must be local/demo/test",
    )
    forbidden = set(scenario.get("forbidden_execute_environments", []))
    _require("production" in forbidden, "production must be explicitly forbidden")
    _require(
        scenario.get("approval", {}).get("required_for_execute") is True,
        "execute must require approval",
    )

    stages = scenario.get("stages")
    _require(isinstance(stages, list) and stages, "scenario stages are required")
    stage_ids = [stage.get("id") for stage in stages]
    _require(all(_has_value(stage_id) for stage_id in stage_ids), "stage id is required")
    _require(len(stage_ids) == len(set(stage_ids)), "stage ids must be unique")
    seen: set[str] = set()
    for stage in stages:
        stage_id = stage["id"]
        _require(
            stage.get("executor") in {"http", "external_evidence"},
            f"{stage_id}: unsupported executor",
        )
        _require(
            stage.get("operation") in {"READ", "WRITE", "ASSERT"},
            f"{stage_id}: unsupported operation",
        )
        dependencies = stage.get("depends_on")
        _require(isinstance(dependencies, list), f"{stage_id}: depends_on must be a list")
        unknown = [dependency for dependency in dependencies if dependency not in seen]
        _require(not unknown, f"{stage_id}: dependency must precede stage: {unknown}")
        evidence = stage.get("required_evidence")
        _require(
            isinstance(evidence, list) and evidence,
            f"{stage_id}: required_evidence is required",
        )
        seen.add(stage_id)

    _require(bindings.get("schema_version") == 1, "bindings schema_version must be 1")
    http_bindings = bindings.get("bindings")
    external_bindings = bindings.get("external_evidence_bindings")
    _require(isinstance(http_bindings, dict), "HTTP bindings are required")
    _require(isinstance(external_bindings, dict), "external bindings are required")
    blockers: list[dict[str, str]] = []
    for stage in stages:
        table = http_bindings if stage["executor"] == "http" else external_bindings
        binding = table.get(stage["binding_id"])
        _require(binding is not None, f"{stage['id']}: missing binding")
        _require(
            binding.get("executor", stage["executor"]) == stage["executor"],
            f"{stage['id']}: executor mismatch",
        )
        if stage["executor"] == "http":
            path = binding.get("path", "")
            _require(
                path.startswith("/app-api/cloudmold/"),
                f"{stage['id']}: HTTP path must stay under /app-api/cloudmold",
            )
            _require(
                binding.get("method") in {"GET", "POST"},
                f"{stage['id']}: HTTP method must be GET or POST",
            )
        if binding.get("availability") != EXECUTABLE_AVAILABILITY:
            blockers.append(
                {
                    "stageId": stage["id"],
                    "availability": binding.get("availability", "MISSING"),
                }
            )

    _require(
        reconciliation.get("schema_version") == 1,
        "reconciliation schema_version must be 1",
    )
    model_root = reconciliation_path.parents[1]
    missing_models: list[str] = []
    for relative_path in reconciliation.get("required_models", {}).values():
        if not (model_root / relative_path).is_file():
            missing_models.append(relative_path)
    _require(not missing_models, f"reconciliation model files missing: {missing_models}")
    _require(
        reconciliation.get("acceptance", {}).get("simulated") is False,
        "reconciliation must forbid simulated evidence",
    )
    _require(
        reconciliation.get("acceptance", {}).get("production_credit") is False,
        "local scenario must not claim production credit",
    )
    return {
        "scenario": scenario,
        "bindings": bindings,
        "reconciliation": reconciliation,
        "scenarioDigest": digest(scenario),
        "bindingsDigest": digest(bindings),
        "reconciliationDigest": digest(reconciliation),
        "stageCount": len(stages),
        "blockers": blockers,
    }


def build_plan(
    run_id: str,
    environment: str,
    contracts: dict[str, Any],
) -> dict[str, Any]:
    _require(RUN_ID_PATTERN.fullmatch(run_id) is not None, "invalid run_id")
    _require(environment in EXECUTE_ENVIRONMENTS, "environment must be local/demo/test")
    blockers = {item["stageId"]: item["availability"] for item in contracts["blockers"]}
    steps = []
    for stage in contracts["scenario"]["stages"]:
        stage_id = stage["id"]
        steps.append(
            {
                "stageId": stage_id,
                "phase": stage["phase"],
                "executor": stage["executor"],
                "operation": stage["operation"],
                "dependsOn": stage["depends_on"],
                "idempotencyKey": stable_idempotency_key(run_id, stage_id),
                "status": "BLOCKED_DEPENDENCY" if stage_id in blockers else "PLANNED",
                "blocker": blockers.get(stage_id),
                "requiredEvidence": stage["required_evidence"],
            }
        )
    return {
        "schema_version": 1,
        "scenarioId": contracts["scenario"]["scenario_id"],
        "scenarioVersion": contracts["scenario"]["scenario_version"],
        "mode": "PLAN",
        "runId": run_id,
        "environment": environment,
        "status": "BLOCKED_DEPENDENCY" if blockers else "READY_FOR_APPROVED_EXECUTE",
        "simulated": False,
        "scenarioDigest": contracts["scenarioDigest"],
        "bindingsDigest": contracts["bindingsDigest"],
        "reconciliationDigest": contracts["reconciliationDigest"],
        "steps": steps,
    }


def build_execute_gate(
    run_id: str,
    environment: str,
    approval: dict[str, Any],
    contracts: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    plan = build_plan(run_id, environment, contracts)
    approval_evidence = validate_approval(
        approval,
        run_id,
        environment,
        contracts["scenario"]["approval"]["required_scope"],
        now=now,
    )
    _require(
        not contracts["blockers"],
        "execute blocked by unavailable bindings: "
        + ", ".join(
            f"{item['stageId']}={item['availability']}"
            for item in contracts["blockers"]
        ),
    )
    return {
        **plan,
        "mode": "EXECUTE_GATE",
        "status": "AUTHORIZED",
        "approval": approval_evidence,
        "guardrails": {
            "environment": environment,
            "productionForbidden": True,
            "terminalEvidenceRequired": True,
            "immutableReplayRequired": True,
            "zeroMismatchRequired": True,
        },
    }


def _validate_step_evidence(
    ledger: dict[str, Any],
    scenario: dict[str, Any],
    run_id: str,
) -> None:
    steps = ledger.get("steps")
    _require(isinstance(steps, list), "ledger steps must be a list")
    expected_stages = scenario["stages"]
    expected_ids = [stage["id"] for stage in expected_stages]
    actual_ids = [step.get("stageId") for step in steps]
    _require(actual_ids == expected_ids, "ledger steps must match scenario order exactly")
    for stage, step in zip(expected_stages, steps):
        stage_id = stage["id"]
        _require(
            step.get("status") in {"SUCCEEDED", "DUPLICATE"},
            f"{stage_id}: terminal step status is required",
        )
        _require(
            step.get("idempotencyKey") == stable_idempotency_key(run_id, stage_id),
            f"{stage_id}: idempotency key mismatch",
        )
        _require(
            SHA256_PATTERN.fullmatch(step.get("responseSha256", "")) is not None,
            f"{stage_id}: responseSha256 is required",
        )
        if stage["operation"] == "WRITE":
            _require(
                SHA256_PATTERN.fullmatch(step.get("requestSha256", "")) is not None,
                f"{stage_id}: requestSha256 is required",
            )
            _require(
                SHA256_PATTERN.fullmatch(step.get("effectSha256", "")) is not None,
                f"{stage_id}: effectSha256 is required",
            )
            _require(
                isinstance(step.get("eventIds"), list) and step["eventIds"],
                f"{stage_id}: non-empty eventIds are required",
            )
        evidence = step.get("evidence")
        _require(isinstance(evidence, dict), f"{stage_id}: evidence object is required")
        missing = [
            field
            for field in stage["required_evidence"]
            if not _has_value(evidence.get(field))
        ]
        _require(not missing, f"{stage_id}: missing evidence fields {missing}")
        behavior_types = {
            "app.behavior.search_requested": "SEARCH_REQUESTED",
            "app.behavior.search_exposed": "SEARCH_RESULT_EXPOSED",
            "app.behavior.search_clicked": "SEARCH_RESULT_CLICKED",
            "app.behavior.pdp": "PDP_VIEWED",
            "app.behavior.cart_added": "CART_ADDED",
            "app.behavior.checkout": "CHECKOUT_STARTED",
        }
        if stage_id in behavior_types:
            _same(
                evidence.get("behaviorType"),
                behavior_types[stage_id],
                f"{stage_id} behaviorType",
            )


def _same(value: Any, expected: Any, name: str) -> None:
    _require(value == expected, f"{name} mismatch")


def _positive_integer(value: Any, name: str) -> int:
    _require(isinstance(value, int) and value > 0, f"{name} must be a positive integer")
    return value


def validate_terminal_ledger(
    ledger: dict[str, Any],
    contracts: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    scenario = contracts["scenario"]
    _require(
        not contracts["blockers"],
        "terminal evidence cannot be accepted while execute bindings are unavailable",
    )
    _require(ledger.get("schema_version") == 1, "ledger schema_version must be 1")
    _require(ledger.get("scenarioId") == scenario["scenario_id"], "scenarioId mismatch")
    _require(
        ledger.get("scenarioVersion") == scenario["scenario_version"],
        "scenarioVersion mismatch",
    )
    _require(ledger.get("mode") == "EXECUTE", "terminal ledger mode must be EXECUTE")
    _require(ledger.get("status") == "SUCCEEDED", "terminal ledger must be SUCCEEDED")
    _require(ledger.get("simulated") is False, "simulated evidence is forbidden")
    _require(
        ledger.get("evidenceScope") in TERMINAL_SCOPES,
        "terminal evidence scope must be LOCAL_TEST/DEMO_TEST/TEST",
    )
    run_id = ledger.get("runId", "")
    environment = ledger.get("environment", "")
    _require(RUN_ID_PATTERN.fullmatch(run_id) is not None, "invalid ledger runId")
    _require(environment in EXECUTE_ENVIRONMENTS, "invalid ledger environment")
    _same(ledger.get("scenarioDigest"), contracts["scenarioDigest"], "scenarioDigest")
    _same(ledger.get("bindingsDigest"), contracts["bindingsDigest"], "bindingsDigest")
    _same(
        ledger.get("reconciliationDigest"),
        contracts["reconciliationDigest"],
        "reconciliationDigest",
    )
    validate_approval(
        ledger.get("approval", {}),
        run_id,
        environment,
        scenario["approval"]["required_scope"],
        now=now,
    )
    _validate_step_evidence(ledger, scenario, run_id)

    terminal = ledger.get("terminalEvidence")
    _require(isinstance(terminal, dict), "terminalEvidence is required")
    _same(
        ledger.get("terminalEvidenceSha256"),
        digest(terminal),
        "terminalEvidenceSha256",
    )
    sections = [
        "identity",
        "product",
        "checkout",
        "order",
        "payment",
        "fulfillment",
        "afterSale",
        "customerService",
        "behavior",
        "inventory",
        "states",
        "lakehouse",
        "replay",
    ]
    for section in sections:
        _require(isinstance(terminal.get(section), dict), f"{section} evidence is required")

    identity = terminal["identity"]
    product = terminal["product"]
    checkout = terminal["checkout"]
    order = terminal["order"]
    payment = terminal["payment"]
    fulfillment = terminal["fulfillment"]
    after_sale = terminal["afterSale"]
    customer_service = terminal["customerService"]
    behavior = terminal["behavior"]
    inventory = terminal["inventory"]

    principal_id = identity.get("principalId")
    _require(_has_value(principal_id), "principalId is required")
    for actual, name in (
        (checkout.get("principalId"), "checkout principalId"),
        (order.get("buyerPrincipalId"), "Order buyerPrincipalId"),
        (behavior.get("principalId"), "behavior principalId"),
    ):
        _same(actual, principal_id, name)

    for field in ("listingId", "listingOfferId", "canonicalSkuId"):
        expected = product.get(field)
        _require(_has_value(expected), f"product {field} is required")
        _same(checkout.get(field), expected, f"checkout {field}")
        _same(order.get(field), expected, f"Order {field}")
        _same(fulfillment.get(field), expected, f"Fulfillment {field}")
        _same(after_sale.get(field), expected, f"AfterSale {field}")
    _same(checkout.get("canonicalSpuId"), product.get("canonicalSpuId"), "canonicalSpuId")

    order_id = order.get("orderId")
    _require(_has_value(order_id), "orderId is required")
    _same(payment.get("orderId"), order_id, "Payment orderId")
    _same(fulfillment.get("orderId"), order_id, "Fulfillment orderId")
    _same(after_sale.get("orderId"), order_id, "AfterSale orderId")
    _same(customer_service.get("referenceId"), after_sale.get("afterSaleId"), "ticket reference")
    _same(customer_service.get("referenceType"), "AFTER_SALE", "ticket referenceType")

    amounts = {
        "checkout payable": checkout.get("payableAmountMinor"),
        "Order payable": order.get("payableAmountMinor"),
        "captured": payment.get("capturedAmountMinor"),
        "refunded": after_sale.get("refundedAmountMinor"),
    }
    first_amount = _positive_integer(next(iter(amounts.values())), next(iter(amounts)))
    for name, value in amounts.items():
        _same(_positive_integer(value, name), first_amount, name)
    currency = product.get("currencyCode")
    _require(_has_value(currency), "currencyCode is required")
    for section_name, section in (
        ("checkout", checkout),
        ("Order", order),
        ("Payment", payment),
        ("AfterSale", after_sale),
    ):
        _same(section.get("currencyCode"), currency, f"{section_name} currencyCode")

    ordered = _positive_integer(order.get("quantity"), "ordered quantity")
    _same(_positive_integer(after_sale.get("returnedQuantity"), "returned quantity"), ordered, "returned quantity")
    _same(_positive_integer(inventory.get("restockedQuantity"), "restocked quantity"), ordered, "restocked quantity")
    _same(
        inventory.get("availableQuantityAfter"),
        inventory.get("availableQuantityBefore"),
        "restored available quantity",
    )
    _require(
        inventory.get("availableQuantityBefore", 0) >= ordered,
        "initial available quantity is insufficient",
    )
    _same(product.get("qualityStatus"), "QUALIFIED", "product qualityStatus")
    _require(product.get("inStock") is True, "product must be in stock")

    behavior_types = set(behavior.get("eventTypes", []))
    required_behavior = set(scenario["terminal_evidence"]["required_behavior_types"])
    _require(
        required_behavior.issubset(behavior_types),
        f"missing behavior events: {sorted(required_behavior - behavior_types)}",
    )
    _same(behavior.get("sessionId"), identity.get("sessionId"), "sessionId")

    step_evidence = {
        step["stageId"]: step["evidence"] for step in ledger["steps"]
    }
    _same(
        step_evidence["app.identity.me"].get("principalId"),
        principal_id,
        "identity step principalId",
    )
    _same(
        step_evidence["app.session.start"].get("sessionId"),
        behavior.get("sessionId"),
        "session start receipt",
    )
    for stage_id in (
        "app.behavior.search_requested",
        "app.behavior.search_exposed",
        "app.behavior.search_clicked",
        "app.behavior.pdp",
        "app.behavior.cart_added",
        "app.behavior.checkout",
    ):
        _same(
            step_evidence[stage_id].get("sessionId"),
            behavior.get("sessionId"),
            f"{stage_id} sessionId",
        )
    for field in ("listingId", "canonicalSpuId"):
        _same(
            step_evidence["app.product.detail"].get(field),
            product.get(field),
            f"product detail receipt {field}",
        )
    for field in ("listingOfferId", "canonicalSkuId"):
        product_skus = step_evidence["app.product.detail"].get("skus")
        _require(isinstance(product_skus, list) and product_skus, "product detail skus must be non-empty")
        matching = [
            sku for sku in product_skus
            if isinstance(sku, dict) and sku.get(field) == product.get(field)
        ]
        _require(matching, f"product detail receipt missing selected {field}")
    receipt_links = {
        "app.checkout.preview": {
            "principalId": principal_id,
            "listingId": product.get("listingId"),
            "listingOfferId": product.get("listingOfferId"),
            "canonicalSkuId": product.get("canonicalSkuId"),
            "payableAmountMinor": checkout.get("payableAmountMinor"),
        },
        "app.order.create": {
            "orderId": order_id,
            "buyerPrincipalId": principal_id,
            "listingId": product.get("listingId"),
            "listingOfferId": product.get("listingOfferId"),
            "canonicalSkuId": product.get("canonicalSkuId"),
            "payableAmountMinor": order.get("payableAmountMinor"),
        },
        "app.payment.capture": {
            "paymentId": payment.get("paymentId"),
            "capturedAmountMinor": payment.get("capturedAmountMinor"),
        },
        "app.fulfillment.by_order": {
            "orderId": order_id,
            "fulfillmentId": fulfillment.get("fulfillmentId"),
            "shipmentId": fulfillment.get("shipmentId"),
        },
        "app.after_sale.get": {
            "afterSaleId": after_sale.get("afterSaleId"),
            "orderId": order_id,
        },
        "app.customer_service.ticket_get": {
            "ticketId": customer_service.get("ticketId"),
            "referenceType": customer_service.get("referenceType"),
            "referenceId": customer_service.get("referenceId"),
        },
    }
    for stage_id, fields in receipt_links.items():
        for field, expected in fields.items():
            _same(
                step_evidence[stage_id].get(field),
                expected,
                f"{stage_id} receipt {field}",
            )

    required_states = scenario["terminal_evidence"]["required_states"]
    for state_name, expected in required_states.items():
        _same(terminal["states"].get(state_name), expected, state_name)

    lakehouse = terminal["lakehouse"]
    _require(
        lakehouse.get("outboxCdcCheckpointSucceeded") is True,
        "Outbox CDC checkpoint must succeed",
    )
    _require(lakehouse.get("fullDenominator") is True, "full denominator is required")
    _require(lakehouse.get("nonempty") is True, "lakehouse evidence must be non-empty")
    for count_name in (
        "sourceToFactMismatchCount",
        "factToProjectionMismatchCount",
        "crossTenantLinkCount",
        "identityLinkMismatchCount",
        "productLinkMismatchCount",
        "orderPaymentMoneyMismatchCount",
        "returnQuantityMismatchCount",
        "dqcViolationCount",
    ):
        _same(lakehouse.get(count_name), 0, count_name)
    for model, expected in scenario["terminal_evidence"][
        "required_lakehouse_results"
    ].items():
        _same(lakehouse.get("modelResults", {}).get(model), expected, model)

    replay = terminal["replay"]
    _require(replay.get("verified") is True, "immutable replay must be verified")
    _require(replay.get("effectHashMatch") is True, "replay effect hash must match")
    _require(
        SHA256_PATTERN.fullmatch(replay.get("originalLedgerSha256", "")) is not None,
        "originalLedgerSha256 is required",
    )
    write_ids = {
        stage["id"] for stage in scenario["stages"] if stage["operation"] == "WRITE"
    }
    duplicate_ids = set(replay.get("duplicateStageIds", []))
    _require(
        write_ids.issubset(duplicate_ids),
        f"replay missing write stages: {sorted(write_ids - duplicate_ids)}",
    )

    return {
        "status": "valid",
        "scenarioId": scenario["scenario_id"],
        "runId": run_id,
        "environment": environment,
        "stageCount": len(scenario["stages"]),
        "terminalEvidenceSha256": ledger["terminalEvidenceSha256"],
        "productionCredit": False,
    }


def _write_result(result: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    parser.add_argument("--bindings", type=Path, default=DEFAULT_BINDINGS)
    parser.add_argument("--reconciliation", type=Path, default=DEFAULT_RECONCILIATION)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate-contracts")

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--run-id", required=True)
    plan_parser.add_argument("--environment", choices=sorted(EXECUTE_ENVIRONMENTS), default="local")
    plan_parser.add_argument("--output", type=Path)

    gate_parser = subparsers.add_parser("gate-execute")
    gate_parser.add_argument("--run-id", required=True)
    gate_parser.add_argument("--environment", choices=sorted(EXECUTE_ENVIRONMENTS), required=True)
    gate_parser.add_argument("--approval", type=Path, required=True)
    gate_parser.add_argument("--output", type=Path)

    ledger_parser = subparsers.add_parser("validate-ledger")
    ledger_parser.add_argument("--ledger", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        contracts = validate_contracts(
            args.scenario.resolve(),
            args.bindings.resolve(),
            args.reconciliation.resolve(),
        )
        if args.command == "validate-contracts":
            result = {
                "status": "valid",
                "scenarioId": contracts["scenario"]["scenario_id"],
                "stageCount": contracts["stageCount"],
                "scenarioDigest": contracts["scenarioDigest"],
                "bindingsDigest": contracts["bindingsDigest"],
                "reconciliationDigest": contracts["reconciliationDigest"],
                "executeBlockers": contracts["blockers"],
            }
            _write_result(result, None)
        elif args.command == "plan":
            _write_result(
                build_plan(args.run_id, args.environment, contracts),
                args.output,
            )
        elif args.command == "gate-execute":
            result = build_execute_gate(
                args.run_id,
                args.environment,
                load_json(args.approval.resolve()),
                contracts,
            )
            _write_result(result, args.output)
        elif args.command == "validate-ledger":
            _write_result(
                validate_terminal_ledger(load_json(args.ledger.resolve()), contracts),
                None,
            )
        return 0
    except CrossChannelAgentError as error:
        print(
            json.dumps(
                {"status": "blocked", "error": str(error)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
