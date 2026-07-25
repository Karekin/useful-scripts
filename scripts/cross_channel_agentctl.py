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
DEFAULT_RUNTIME_ROOT = ROOT / "runs" / "cross-channel"
RUN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{5,63}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
EXECUTE_ENVIRONMENTS = {"local", "demo", "test"}
TERMINAL_SCOPES = {"LOCAL_TEST", "DEMO_TEST", "TEST"}
EXECUTABLE_AVAILABILITY = "IMPLEMENTED_AND_TESTED"
ALLOWED_BINDING_AVAILABILITY = {
    "CONTRACT_REQUIRED",
    "CONTRACT_FROZEN_NOT_DISCOVERED",
    "IMPLEMENTED_AND_TESTED",
    "BLOCKED_EXTERNAL_DEPENDENCY",
}
SUPPORTED_CONTRACT_SCHEMA_VERSIONS = {1, 2}
SUPPORTED_LEDGER_SCHEMA_VERSIONS = {1, 2}
TERMINAL_SIGNATURE_TYPE = "LOCAL_RUNTIME_ATTESTATION_V1"
RUNTIME_STEP_MAX_AGE_DAYS = 30
RECEIPT_STATUSES = {"SUCCEEDED", "DUPLICATE"}
RAW_DELIVERY_PII_FIELDS = {"receiverName", "receiverMobile", "receiverAddress"}
RESTRICTED_CONSUMER_FIELDS = {
    "inspectionTaskId",
    "qualityStandardVersion",
    "inspectionDecision",
    "evidenceToken",
    "qualityEvidence",
    "qualityEvidenceUri",
    "internalTaskId",
    "operatorTaskId",
}
QUALITY_RELEASE_OPERATIONS = [
    ("CREATE_STANDARD", "quality_standard", "DRAFT"),
    ("PUBLISH_STANDARD", "quality_standard", "PUBLISHED"),
    ("CERTIFY_AUTHENTICATOR", "authenticator_certification", "ACTIVE"),
    ("CREATE_INSPECTION_TASK", "inspection_task", "CREATED"),
    ("ASSIGN_INSPECTION_TASK", "inspection_task", "ASSIGNED"),
    ("START_INSPECTION_TASK", "inspection_task", "IN_PROGRESS"),
    ("DECIDE_INSPECTION_TASK", "inspection_task", "DECIDED"),
    ("COMPLETE_INSPECTION_TASK", "inspection_task", "COMPLETED"),
]
QUALITY_RELEASE_EVENT_TYPES = {
    "quality.standard.created",
    "quality.standard.published",
    "quality.authenticator.certified",
    "quality.inspection_task.created",
    "quality.inspection_task.status_changed",
}
LAKEHOUSE_RECONCILE_COMMANDS = [
    "reconcile-canonical-commerce-v2",
    "reconcile-canonical-aftersales",
    "test",
]
ZERO_CHECK_NAME_MAP = {
    "sourceToFactMismatchCount": "source_to_fact_mismatch_count",
    "factToProjectionMismatchCount": "fact_to_projection_mismatch_count",
    "crossTenantLinkCount": "cross_tenant_link_count",
    "identityLinkMismatchCount": "identity_link_mismatch_count",
    "productLinkMismatchCount": "product_link_mismatch_count",
    "orderPaymentMoneyMismatchCount": "order_payment_money_mismatch_count",
    "returnQuantityMismatchCount": "return_quantity_mismatch_count",
    "dqcViolationCount": "dqc_violation_count",
}


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


def _utc_now(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


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


def _validate_quality_release_binding(binding: dict[str, Any]) -> None:
    _require(
        binding.get("executor") == "external_evidence"
        and binding.get("adapter") == "admin_rest_sequence",
        "quality release must use the governed Admin REST sequence adapter",
    )
    _require(
        binding.get("path") == "/admin-api/cloudmold/quality/command"
        and binding.get("method") == "POST",
        "quality release must bind the real quality command endpoint",
    )
    _require(
        binding.get("permission") == "cloudmold:quality:command",
        "quality release permission contract is invalid",
    )
    for environment_name in ("base_url_env", "token_env", "tenant_env"):
        _require(
            _has_value(binding.get(environment_name)),
            f"quality release {environment_name} is required",
        )
    operations = binding.get("operations")
    _require(
        isinstance(operations, list) and len(operations) == len(QUALITY_RELEASE_OPERATIONS),
        "quality release must declare the complete eight-command sequence",
    )
    actual = [
        (
            item.get("operation"),
            item.get("aggregate_type"),
            item.get("expected_status"),
        )
        for item in operations
    ]
    _require(
        actual == QUALITY_RELEASE_OPERATIONS,
        "quality release operation order or terminal status is invalid",
    )
    _require(
        operations[6].get("required_decision") == "PASS",
        "quality release must require a PASS decision",
    )
    response_contract = binding.get("response_contract", {})
    _require(
        response_contract.get("common_result_code") == 0
        and response_contract.get("immutable_replay_required") is True,
        "quality release must require a successful immutable command receipt",
    )
    _require(
        {
            "operationId",
            "duplicate",
            "aggregateType",
            "aggregateId",
            "aggregateVersion",
            "status",
        }
        == set(response_contract.get("required_fields", [])),
        "quality release response receipt contract is incomplete",
    )
    event_evidence = binding.get("event_evidence", {})
    _require(
        event_evidence.get("source") == "cloudmold_domain_outbox"
        and event_evidence.get("source_system") == "cloudmold-quality"
        and event_evidence.get("destination") == "lakehouse"
        and event_evidence.get("delivery_status") == 20
        and event_evidence.get("same_tenant_run_and_task_required") is True,
        "quality release must require delivered, same-lineage Outbox evidence",
    )
    _require(
        set(event_evidence.get("required_event_types", []))
        == QUALITY_RELEASE_EVENT_TYPES,
        "quality release Outbox event denominator is incomplete",
    )
    mapping = binding.get("evidence_mapping", {})
    _require(
        mapping.get("qualityStatus") == "QUALIFIED"
        and mapping.get("inspectionDecision") == "PASS"
        and mapping.get("inspectionTaskId") == "COMPLETE_INSPECTION_TASK.aggregateId",
        "quality release evidence mapping is invalid",
    )
    _require(
        len(binding.get("request_invariants", [])) >= 8
        and len(binding.get("fail_closed", [])) >= 7,
        "quality release invariants and failure policy are required",
    )


def _validate_lakehouse_binding(
    binding: dict[str, Any],
    scenario: dict[str, Any],
    reconciliation: dict[str, Any],
) -> None:
    _require(
        binding.get("executor") == "external_evidence"
        and binding.get("adapter") == "lakehousectl_sequence",
        "lakehouse reconciliation must use the governed lakehousectl sequence adapter",
    )
    executable = binding.get("executable", "")
    _require(
        executable == "yml/yshopping-lakehouse/scripts/lakehousectl",
        "lakehouse reconciliation executable is not the governed lakehousectl",
    )
    executable_path = ROOT / executable
    _require(executable_path.is_file(), "governed lakehousectl executable is missing")
    commands = binding.get("commands")
    _require(
        isinstance(commands, list)
        and [item.get("command") for item in commands] == LAKEHOUSE_RECONCILE_COMMANDS,
        "lakehouse reconciliation command order is invalid",
    )
    source = executable_path.read_text(encoding="utf-8")
    for command in LAKEHOUSE_RECONCILE_COMMANDS:
        marker = f"  {command})"
        _require(
            marker in source,
            f"lakehousectl command is not implemented: {command}",
        )
    _require(
        commands[0].get("arguments")
        == ["--tenant", "{tenantId}", "--run-id", "{runId}"],
        "commerce v2 reconciliation arguments are invalid",
    )
    _require(
        commands[1].get("arguments")
        == [
            "--tenant",
            "{tenantId}",
            "--run-id",
            "{runId}",
            "--after-sale-id",
            "{afterSaleId}",
        ],
        "after-sales reconciliation arguments are invalid",
    )
    _require(
        set(binding.get("required_nonempty_models", []))
        == set(reconciliation.get("required_models", {})),
        "lakehouse non-empty model denominator differs from the reconciliation contract",
    )
    _require(
        set(binding.get("required_behavior_types", []))
        == set(reconciliation.get("required_behavior_types", [])),
        "lakehouse behavior denominator differs from the reconciliation contract",
    )
    _require(
        binding.get("required_model_results")
        == scenario.get("terminal_evidence", {}).get("required_lakehouse_results"),
        "lakehouse required model results differ from the terminal scenario",
    )
    zero_checks = binding.get("required_zero_checks", [])
    _require(
        set(zero_checks) == set(ZERO_CHECK_NAME_MAP),
        "lakehouse zero-check denominator is incomplete",
    )
    _require(
        {ZERO_CHECK_NAME_MAP[name] for name in zero_checks}
        == set(reconciliation.get("required_zero_checks", [])),
        "lakehouse zero checks differ from the reconciliation contract",
    )
    _require(
        binding.get("acceptance") == reconciliation.get("acceptance"),
        "lakehouse acceptance policy differs from the reconciliation contract",
    )
    _require(
        len(binding.get("exact_grain_parameters", [])) >= 9
        and len(binding.get("fail_closed", [])) >= 7,
        "lakehouse exact grain and failure policy are required",
    )


def external_invocation_spec(
    stage_id: str,
    binding: dict[str, Any],
) -> dict[str, Any]:
    """Return the real, non-secret invocation contract for an external stage."""
    adapter = binding.get("adapter")
    if adapter == "admin_rest_sequence":
        return {
            "adapter": adapter,
            "baseUrlEnv": binding["base_url_env"],
            "tokenEnv": binding["token_env"],
            "tenantEnv": binding["tenant_env"],
            "permission": binding["permission"],
            "method": binding["method"],
            "path": binding["path"],
            "operations": [
                {
                    "operation": operation["operation"],
                    "expectedStatus": operation["expected_status"],
                }
                for operation in binding["operations"]
            ],
            "failClosed": True,
        }
    if adapter == "admin_rest_command":
        return {
            "adapter": adapter,
            "baseUrlEnv": binding["base_url_env"],
            "tokenEnv": binding["token_env"],
            "tenantEnv": binding["tenant_env"],
            "permission": binding["permission"],
            "method": binding["method"],
            "path": binding["path"],
            "responseFields": binding.get("response_fields", []),
            "failClosed": True,
        }
    if adapter == "lakehousectl_sequence":
        return {
            "adapter": adapter,
            "executable": str((ROOT / binding["executable"]).resolve()),
            "commands": binding["commands"],
            "requiredNonemptyModels": binding["required_nonempty_models"],
            "requiredZeroChecks": binding["required_zero_checks"],
            "failClosed": True,
        }
    return {
        "adapter": "governed_skill",
        "skillId": binding.get("skill_id"),
        "failClosed": True,
    }


def _binding_table(contracts: dict[str, Any], executor: str) -> dict[str, Any]:
    if executor == "http":
        return contracts["bindings"]["bindings"]
    return contracts["bindings"]["external_evidence_bindings"]


def _binding_for_stage(contracts: dict[str, Any], stage: dict[str, Any]) -> dict[str, Any]:
    return _binding_table(contracts, stage["executor"])[stage["binding_id"]]


def _binding_digest(contracts: dict[str, Any], stage: dict[str, Any]) -> str:
    return digest(_binding_for_stage(contracts, stage))


def _runtime_dir(root: Path, run_id: str) -> Path:
    return root / run_id


def _runtime_state_path(runtime_dir: Path) -> Path:
    return runtime_dir / "state.json"


def _runtime_plan_path(runtime_dir: Path) -> Path:
    return runtime_dir / "plan.json"


def _runtime_gate_path(runtime_dir: Path) -> Path:
    return runtime_dir / "execute-gate.json"


def _runtime_receipts_dir(runtime_dir: Path) -> Path:
    return runtime_dir / "receipts"


def _runtime_receipt_path(runtime_dir: Path, ordinal: int, stage_id: str) -> Path:
    safe_stage = stage_id.replace("/", "_")
    return _runtime_receipts_dir(runtime_dir) / f"{ordinal:02d}-{safe_stage}.json"


def _runtime_status(step_states: list[dict[str, Any]]) -> str:
    if all(item.get("status") == "RECORDED" for item in step_states):
        return "READY_TO_REPLAY"
    if any(item.get("status") == "RECORDED" for item in step_states):
        return "PARTIAL"
    return "READY_TO_RECORD"


def _runtime_signature_payload(ledger: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenarioId": ledger["scenarioId"],
        "scenarioVersion": ledger["scenarioVersion"],
        "runId": ledger["runId"],
        "environment": ledger["environment"],
        "scenarioDigest": ledger["scenarioDigest"],
        "bindingsDigest": ledger["bindingsDigest"],
        "reconciliationDigest": ledger["reconciliationDigest"],
        "runtimeReceiptManifestSha256": ledger["runtimeReceiptManifestSha256"],
        "terminalEvidenceSha256": ledger["terminalEvidenceSha256"],
    }


def _sign_runtime_ledger(ledger: dict[str, Any], signed_at: datetime | None = None) -> dict[str, Any]:
    payload = _runtime_signature_payload(ledger)
    timestamp = _utc_now(signed_at).isoformat().replace("+00:00", "Z")
    return {
        "signatureType": TERMINAL_SIGNATURE_TYPE,
        "signer": "cross_channel_agentctl.replay",
        "signedAt": timestamp,
        "signedPayloadSha256": digest(payload),
    }


def _receipt_template(
    stage: dict[str, Any],
    contracts: dict[str, Any],
    run_id: str,
    environment: str,
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "stageId": stage["id"],
        "executor": stage["executor"],
        "operation": stage["operation"],
        "status": "SUCCEEDED",
        "idempotencyKey": stable_idempotency_key(run_id, stage["id"]),
        "requestEnvelope": {},
        "responseEnvelope": {},
        "effectEnvelope": {},
        "evidence": {},
        "linkage": {
            "runId": run_id,
            "environment": environment,
            "tenantId": "1",
        },
        "runtime": {
            "recordedAt": _utc_now().isoformat().replace("+00:00", "Z"),
            "receiptSource": "local-manual",
            "recorder": "cross_channel_agentctl.resume",
        },
        "definition": {
            "scenarioDigest": contracts["scenarioDigest"],
            "bindingsDigest": contracts["bindingsDigest"],
            "reconciliationDigest": contracts["reconciliationDigest"],
            "bindingId": stage["binding_id"],
            "bindingDefinitionSha256": _binding_digest(contracts, stage),
        },
    }


def validate_contracts(
    scenario_path: Path = DEFAULT_SCENARIO,
    bindings_path: Path = DEFAULT_BINDINGS,
    reconciliation_path: Path = DEFAULT_RECONCILIATION,
) -> dict[str, Any]:
    scenario = load_json(scenario_path)
    bindings = load_json(bindings_path)
    reconciliation = load_json(reconciliation_path)

    _require(
        scenario.get("schema_version") in SUPPORTED_CONTRACT_SCHEMA_VERSIONS,
        "scenario schema_version must be 1 or 2",
    )
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

    _require(
        bindings.get("schema_version") in SUPPORTED_CONTRACT_SCHEMA_VERSIONS,
        "bindings schema_version must be 1 or 2",
    )
    consumer_policy = bindings.get("consumer_data_policy")
    _require(isinstance(consumer_policy, dict), "consumer_data_policy is required")
    _require(
        consumer_policy.get("raw_delivery_pii_forbidden") is True,
        "consumer contracts must forbid raw delivery PII",
    )
    _require(
        consumer_policy.get("restricted_quality_evidence_forbidden") is True,
        "consumer contracts must forbid restricted quality evidence",
    )
    _require(
        consumer_policy.get("internal_task_ids_forbidden") is True,
        "consumer contracts must forbid internal task IDs",
    )
    _require(
        consumer_policy.get("delivery_address_capability")
        == "DEFERRED_ADDRESS_VAULT_TOKEN",
        "delivery address must remain deferred to Address Vault token",
    )
    http_bindings = bindings.get("bindings")
    external_bindings = bindings.get("external_evidence_bindings")
    _require(isinstance(http_bindings, dict), "HTTP bindings are required")
    _require(isinstance(external_bindings, dict), "external bindings are required")
    quality_binding = external_bindings.get("operator.quality.release")
    lakehouse_binding = external_bindings.get("reconcile.lakehouse")
    _require(isinstance(quality_binding, dict), "quality release binding is required")
    _require(isinstance(lakehouse_binding, dict), "lakehouse reconciliation binding is required")
    _validate_quality_release_binding(quality_binding)
    _validate_lakehouse_binding(lakehouse_binding, scenario, reconciliation)
    blockers: list[dict[str, str]] = []
    for stage in stages:
        table = http_bindings if stage["executor"] == "http" else external_bindings
        binding = table.get(stage["binding_id"])
        _require(binding is not None, f"{stage['id']}: missing binding")
        _require(
            binding.get("executor", stage["executor"]) == stage["executor"],
            f"{stage['id']}: executor mismatch",
        )
        availability = binding.get("availability")
        _require(
            availability in ALLOWED_BINDING_AVAILABILITY,
            f"{stage['id']}: availability is invalid",
        )
        if stage["executor"] == "http":
            path = binding.get("path", "")
            _require(
                path.startswith("/app-api/cloudmold/"),
                f"{stage['id']}: HTTP path must stay under /app-api/cloudmold",
            )
            _require(
                binding.get("method") in {"GET", "POST", "PUT"},
                f"{stage['id']}: HTTP method must be GET, POST, or PUT",
            )
            request_fields = set(binding.get("request_fields", []))
            response_fields = set(binding.get("response_fields", []))
            sku_response_fields = set(binding.get("sku_response_fields", []))
            _require(
                not request_fields.intersection(RAW_DELIVERY_PII_FIELDS),
                f"{stage['id']}: raw delivery PII is forbidden",
            )
            restricted = (response_fields | sku_response_fields).intersection(
                RESTRICTED_CONSUMER_FIELDS
            )
            _require(
                not restricted,
                f"{stage['id']}: restricted consumer fields are forbidden: {sorted(restricted)}",
            )
        if availability != EXECUTABLE_AVAILABILITY:
            blockers.append(
                {
                    "stageId": stage["id"],
                    "availability": availability,
                }
            )
    order_create = http_bindings.get("app.order.create", {})
    _require(
        set(order_create.get("forbidden_request_fields", []))
        == RAW_DELIVERY_PII_FIELDS,
        "app.order.create must explicitly forbid raw delivery PII fields",
    )
    _require(
        order_create.get("deferred_capability") == "ADDRESS_VAULT_DELIVERY_TOKEN",
        "app.order.create must defer delivery address to Address Vault token",
    )
    product_detail = http_bindings.get("app.product.detail", {})
    _require(
        RESTRICTED_CONSUMER_FIELDS.issubset(
            set(product_detail.get("forbidden_response_fields", []))
        ),
        "app.product.detail must explicitly forbid restricted quality/task fields",
    )
    _require(
        product_detail.get("quality_summary_fields") == ["status"],
        "app.product.detail quality summary must expose status only",
    )

    _require(
        reconciliation.get("schema_version") in SUPPORTED_CONTRACT_SCHEMA_VERSIONS,
        "reconciliation schema_version must be 1 or 2",
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
        "bindingDigests": {
            stage["id"]: _binding_digest(
                {
                    "bindings": bindings,
                },
                stage,
            )
            for stage in stages
        },
        "stageCount": len(stages),
        "blockers": blockers,
    }


def _normalize_runtime_receipt(
    receipt: dict[str, Any],
    stage: dict[str, Any],
    contracts: dict[str, Any],
    run_id: str,
    environment: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    stage_id = stage["id"]
    _require(
        receipt.get("schema_version") == 2,
        f"{stage_id}: runtime receipt schema_version must be 2",
    )
    _same(receipt.get("stageId"), stage_id, f"{stage_id}: runtime receipt stageId")
    _same(receipt.get("executor"), stage["executor"], f"{stage_id}: runtime executor")
    _same(receipt.get("operation"), stage["operation"], f"{stage_id}: runtime operation")
    _require(
        receipt.get("status") in RECEIPT_STATUSES,
        f"{stage_id}: runtime receipt status is invalid",
    )
    _same(
        receipt.get("idempotencyKey"),
        stable_idempotency_key(run_id, stage_id),
        f"{stage_id}: runtime idempotencyKey",
    )
    definition = receipt.get("definition")
    _require(isinstance(definition, dict), f"{stage_id}: definition is required")
    _same(
        definition.get("scenarioDigest"),
        contracts["scenarioDigest"],
        f"{stage_id}: scenarioDigest",
    )
    _same(
        definition.get("bindingsDigest"),
        contracts["bindingsDigest"],
        f"{stage_id}: bindingsDigest",
    )
    _same(
        definition.get("reconciliationDigest"),
        contracts["reconciliationDigest"],
        f"{stage_id}: reconciliationDigest",
    )
    _same(
        definition.get("bindingId"),
        stage["binding_id"],
        f"{stage_id}: bindingId",
    )
    _same(
        definition.get("bindingDefinitionSha256"),
        contracts["bindingDigests"][stage_id],
        f"{stage_id}: bindingDefinitionSha256",
    )
    linkage = receipt.get("linkage")
    _require(isinstance(linkage, dict), f"{stage_id}: linkage is required")
    _same(linkage.get("runId"), run_id, f"{stage_id}: linkage runId")
    _same(
        linkage.get("environment"),
        environment,
        f"{stage_id}: linkage environment",
    )
    _require(
        isinstance(linkage.get("tenantId"), str) and linkage["tenantId"].strip(),
        f"{stage_id}: linkage tenantId is required",
    )
    runtime = receipt.get("runtime")
    _require(isinstance(runtime, dict), f"{stage_id}: runtime metadata is required")
    recorded_at = _parse_time(runtime.get("recordedAt"), f"{stage_id} recordedAt")
    age_days = (_utc_now(now) - recorded_at).total_seconds() / 86400
    _require(
        age_days <= RUNTIME_STEP_MAX_AGE_DAYS,
        f"{stage_id}: runtime receipt is older than {RUNTIME_STEP_MAX_AGE_DAYS} days",
    )
    for field in ("receiptSource", "recorder"):
        _require(
            _has_value(runtime.get(field)),
            f"{stage_id}: runtime {field} is required",
        )
    request = receipt.get("requestEnvelope")
    response = receipt.get("responseEnvelope")
    _require(isinstance(request, dict), f"{stage_id}: requestEnvelope is required")
    _require(isinstance(response, dict), f"{stage_id}: responseEnvelope is required")
    effect = receipt.get("effectEnvelope")
    if stage["operation"] == "WRITE":
        _require(isinstance(effect, dict), f"{stage_id}: effectEnvelope is required")
        event_ids = effect.get("eventIds")
        _require(
            isinstance(event_ids, list) and event_ids,
            f"{stage_id}: effectEnvelope.eventIds are required",
        )
    else:
        effect = effect if isinstance(effect, dict) else {}
    evidence = receipt.get("evidence")
    _require(isinstance(evidence, dict), f"{stage_id}: evidence is required")
    missing = [
        field
        for field in stage["required_evidence"]
        if not _has_value(evidence.get(field))
    ]
    _require(not missing, f"{stage_id}: missing evidence fields {missing}")
    normalized = {
        **receipt,
        "requestSha256": digest(request),
        "responseSha256": digest(response),
        "effectSha256": digest(effect),
    }
    normalized["receiptSha256"] = digest(
        {
            "stageId": stage_id,
            "status": normalized["status"],
            "idempotencyKey": normalized["idempotencyKey"],
            "requestSha256": normalized["requestSha256"],
            "responseSha256": normalized["responseSha256"],
            "effectSha256": normalized["effectSha256"],
            "evidence": evidence,
            "linkage": linkage,
            "runtime": runtime,
            "definition": definition,
        }
    )
    return normalized


def initialize_runtime(
    run_id: str,
    environment: str,
    approval: dict[str, Any],
    contracts: dict[str, Any],
    *,
    runtime_root: Path = DEFAULT_RUNTIME_ROOT,
    now: datetime | None = None,
) -> dict[str, Any]:
    gate = build_execute_gate(run_id, environment, approval, contracts, now=now)
    runtime_dir = _runtime_dir(runtime_root, run_id)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    _runtime_receipts_dir(runtime_dir).mkdir(parents=True, exist_ok=True)
    state_path = _runtime_state_path(runtime_dir)
    if state_path.is_file():
        existing = load_json(state_path)
        _same(existing.get("runId"), run_id, "runtime state runId")
        _same(existing.get("environment"), environment, "runtime state environment")
        _same(existing.get("scenarioDigest"), contracts["scenarioDigest"], "runtime state scenarioDigest")
        return existing
    plan = build_plan(run_id, environment, contracts)
    step_states = [
        {
            "stageId": step["stageId"],
            "status": "PENDING",
            "receiptPath": None,
            "receiptSha256": None,
        }
        for step in plan["steps"]
    ]
    state = {
        "schema_version": 2,
        "scenarioId": contracts["scenario"]["scenario_id"],
        "scenarioVersion": contracts["scenario"]["scenario_version"],
        "runId": run_id,
        "environment": environment,
        "scenarioDigest": contracts["scenarioDigest"],
        "bindingsDigest": contracts["bindingsDigest"],
        "reconciliationDigest": contracts["reconciliationDigest"],
        "approval": approval,
        "status": "READY_TO_RECORD",
        "createdAt": _utc_now(now).isoformat().replace("+00:00", "Z"),
        "updatedAt": _utc_now(now).isoformat().replace("+00:00", "Z"),
        "stepStates": step_states,
    }
    _runtime_plan_path(runtime_dir).write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _runtime_gate_path(runtime_dir).write_text(
        json.dumps(gate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return state


def record_runtime_receipts(
    runtime_dir: Path,
    receipt_documents: list[dict[str, Any]],
    contracts: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    state_path = _runtime_state_path(runtime_dir)
    _require(state_path.is_file(), "runtime state does not exist")
    state = load_json(state_path)
    step_states = state.get("stepStates")
    _require(isinstance(step_states, list), "runtime state stepStates are required")
    by_stage = {item["stageId"]: item for item in step_states}
    scenario_stages = {stage["id"]: stage for stage in contracts["scenario"]["stages"]}
    recorded: list[str] = []
    for document in receipt_documents:
        stage_id = document.get("stageId")
        _require(stage_id in scenario_stages, f"unregistered runtime receipt stage: {stage_id}")
        normalized = _normalize_runtime_receipt(
            document,
            scenario_stages[stage_id],
            contracts,
            state["runId"],
            state["environment"],
            now=now,
        )
        step_state = by_stage[stage_id]
        ordinal = next(
            index
            for index, item in enumerate(step_states, start=1)
            if item["stageId"] == stage_id
        )
        receipt_path = _runtime_receipt_path(runtime_dir, ordinal, stage_id)
        receipt_path.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        step_state["status"] = "RECORDED"
        step_state["receiptPath"] = str(receipt_path)
        step_state["receiptSha256"] = normalized["receiptSha256"]
        recorded.append(stage_id)
    state["status"] = _runtime_status(step_states)
    state["updatedAt"] = _utc_now(now).isoformat().replace("+00:00", "Z")
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "status": state["status"],
        "runId": state["runId"],
        "environment": state["environment"],
        "recordedStages": recorded,
        "remainingStages": [
            item["stageId"] for item in step_states if item.get("status") != "RECORDED"
        ],
        "runtimeDir": str(runtime_dir),
    }


def build_runtime_ledger(
    runtime_dir: Path,
    terminal_evidence: dict[str, Any],
    contracts: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    state = load_json(_runtime_state_path(runtime_dir))
    step_states = state.get("stepStates", [])
    missing = [item["stageId"] for item in step_states if item.get("status") != "RECORDED"]
    _require(not missing, f"runtime receipts missing for stages: {missing}")
    runtime_receipts = []
    steps = []
    for item in step_states:
        receipt = load_json(Path(item["receiptPath"]))
        runtime_receipts.append(receipt)
        step = {
            "stageId": receipt["stageId"],
            "status": receipt["status"],
            "idempotencyKey": receipt["idempotencyKey"],
            "responseSha256": receipt["responseSha256"],
            "evidence": receipt["evidence"],
        }
        if receipt["operation"] == "WRITE":
            step["requestSha256"] = receipt["requestSha256"]
            step["effectSha256"] = receipt["effectSha256"]
            step["eventIds"] = receipt["effectEnvelope"]["eventIds"]
        steps.append(step)
    ledger = {
        "schema_version": 2,
        "scenarioId": state["scenarioId"],
        "scenarioVersion": state["scenarioVersion"],
        "mode": "EXECUTE",
        "status": "SUCCEEDED",
        "simulated": False,
        "evidenceScope": "TEST",
        "runId": state["runId"],
        "environment": state["environment"],
        "scenarioDigest": state["scenarioDigest"],
        "bindingsDigest": state["bindingsDigest"],
        "reconciliationDigest": state["reconciliationDigest"],
        "approval": state["approval"],
        "steps": steps,
        "runtimeReceipts": runtime_receipts,
        "runtimeReceiptManifestSha256": digest(runtime_receipts),
        "terminalEvidence": terminal_evidence,
        "terminalEvidenceSha256": digest(terminal_evidence),
    }
    ledger["terminalSignature"] = _sign_runtime_ledger(ledger, signed_at=now)
    return ledger


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
        step = {
            "stageId": stage_id,
            "phase": stage["phase"],
            "executor": stage["executor"],
            "operation": stage["operation"],
            "dependsOn": stage["depends_on"],
            "idempotencyKey": stable_idempotency_key(run_id, stage_id),
            "status": "BLOCKED_DEPENDENCY" if stage_id in blockers else "PLANNED",
            "blocker": blockers.get(stage_id),
            "requiredEvidence": stage["required_evidence"],
            "bindingDefinitionSha256": contracts["bindingDigests"][stage_id],
        }
        if stage["executor"] == "external_evidence":
            binding = contracts["bindings"]["external_evidence_bindings"][
                stage["binding_id"]
            ]
            step["invocation"] = external_invocation_spec(stage_id, binding)
        steps.append(step)
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
    _require(
        ledger.get("schema_version") in SUPPORTED_LEDGER_SCHEMA_VERSIONS,
        "ledger schema_version must be 1 or 2",
    )
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
    runtime_receipts = ledger.get("runtimeReceipts")
    _require(
        isinstance(runtime_receipts, list) and runtime_receipts,
        "runtimeReceipts are required",
    )
    _same(
        ledger.get("runtimeReceiptManifestSha256"),
        digest(runtime_receipts),
        "runtimeReceiptManifestSha256",
    )
    expected_runtime = []
    for stage, receipt in zip(scenario["stages"], runtime_receipts):
        normalized = _normalize_runtime_receipt(
            receipt,
            stage,
            contracts,
            run_id,
            environment,
            now=now,
        )
        expected_runtime.append(normalized)
    _same(runtime_receipts, expected_runtime, "runtimeReceipts")
    signature = ledger.get("terminalSignature")
    _require(isinstance(signature, dict), "terminalSignature is required")
    _same(
        signature.get("signatureType"),
        TERMINAL_SIGNATURE_TYPE,
        "terminalSignature.signatureType",
    )
    _same(
        signature.get("signer"),
        "cross_channel_agentctl.replay",
        "terminalSignature.signer",
    )
    _parse_time(signature.get("signedAt"), "terminalSignature.signedAt")
    _same(
        signature.get("signedPayloadSha256"),
        digest(_runtime_signature_payload(ledger)),
        "terminalSignature.signedPayloadSha256",
    )
    for step, receipt in zip(ledger["steps"], runtime_receipts):
        _same(step.get("stageId"), receipt.get("stageId"), "step/runtime stageId")
        _same(
            step.get("responseSha256"),
            receipt.get("responseSha256"),
            f"{step['stageId']}: step/runtime responseSha256",
        )
        _same(
            step.get("evidence"),
            receipt.get("evidence"),
            f"{step['stageId']}: step/runtime evidence",
        )
        if receipt["operation"] == "WRITE":
            _same(
                step.get("requestSha256"),
                receipt.get("requestSha256"),
                f"{step['stageId']}: step/runtime requestSha256",
            )
            _same(
                step.get("effectSha256"),
                receipt.get("effectSha256"),
                f"{step['stageId']}: step/runtime effectSha256",
            )
            _same(
                step.get("eventIds"),
                receipt.get("effectEnvelope", {}).get("eventIds"),
                f"{step['stageId']}: step/runtime eventIds",
            )

    terminal = ledger.get("terminalEvidence")
    _require(isinstance(terminal, dict), "terminalEvidence is required")
    _same(
        ledger.get("terminalEvidenceSha256"),
        digest(terminal),
        "terminalEvidenceSha256",
    )
    sections = [
        "identity",
        "address",
        "recommendation",
        "community",
        "product",
        "cart",
        "checkout",
        "order",
        "payment",
        "fulfillment",
        "review",
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
    address = terminal["address"]
    recommendation = terminal["recommendation"]
    community = terminal["community"]
    product = terminal["product"]
    cart = terminal["cart"]
    checkout = terminal["checkout"]
    order = terminal["order"]
    payment = terminal["payment"]
    fulfillment = terminal["fulfillment"]
    review = terminal["review"]
    after_sale = terminal["afterSale"]
    customer_service = terminal["customerService"]
    behavior = terminal["behavior"]
    inventory = terminal["inventory"]

    principal_id = identity.get("principalId")
    _require(_has_value(principal_id), "principalId is required")
    _same(
        address.get("addressRef"),
        checkout.get("addressRef"),
        "checkout addressRef",
    )
    _same(
        address.get("snapshotVersion"),
        checkout.get("addressSnapshotVersion"),
        "checkout addressSnapshotVersion",
    )
    for field in ("destinationRegionCode", "receiverSummary", "mobileSummary"):
        _require(_has_value(address.get(field)), f"address {field} is required")
    for field in ("decisionToken", "resultSetToken", "policyVersion", "primaryListingId"):
        _require(_has_value(recommendation.get(field)), f"recommendation {field} is required")
    _same(recommendation.get("primaryListingId"), product.get("listingId"), "recommendation primaryListingId")
    _same(community.get("productLinkListingId"), product.get("listingId"), "community product link listingId")
    _require(community.get("likedByCurrentUser") is True, "community interaction must be liked")
    _same(cart.get("checkoutToken"), checkout.get("checkoutToken"), "cart checkoutToken")
    _require(review.get("eligible") is True, "product review must be eligible")
    _same(review.get("listingId"), product.get("listingId"), "review listingId")
    _same(review.get("canonicalSpuId"), product.get("canonicalSpuId"), "review canonicalSpuId")
    _same(review.get("canonicalSkuId"), product.get("canonicalSkuId"), "review canonicalSkuId")
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
    _same(
        step_evidence["app.recommendation.home"].get("decisionToken"),
        recommendation.get("decisionToken"),
        "recommendation home decisionToken",
    )
    _same(
        step_evidence["app.community.detail"].get("contentId"),
        community.get("contentId"),
        "community detail contentId",
    )
    for stage_id in ("app.address.snapshot_create", "app.address.snapshot_replay", "app.address.snapshot_get"):
        _same(
            step_evidence[stage_id].get("addressRef"),
            address.get("addressRef"),
            f"{stage_id} addressRef",
        )
        _same(
            step_evidence[stage_id].get("snapshotVersion"),
            address.get("snapshotVersion"),
            f"{stage_id} snapshotVersion",
        )
    _same(
        step_evidence["app.address.snapshot_replay"].get("duplicate"),
        True,
        "address replay duplicate",
    )
    for stage_id in (
        "app.behavior.search_requested",
        "app.behavior.search_exposed",
        "app.behavior.search_clicked",
        "app.behavior.pdp",
        "app.behavior.cart_added",
        "app.behavior.checkout",
        "app.recommendation.exposure",
        "app.recommendation.click",
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
            "addressRef": address.get("addressRef"),
            "addressSnapshotVersion": address.get("snapshotVersion"),
            "listingId": product.get("listingId"),
            "listingOfferId": product.get("listingOfferId"),
            "canonicalSkuId": product.get("canonicalSkuId"),
            "payableAmountMinor": checkout.get("payableAmountMinor"),
        },
        "app.cart.preview_selected": {
            "principalId": principal_id,
            "addressRef": address.get("addressRef"),
            "addressSnapshotVersion": address.get("snapshotVersion"),
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
        },
        "app.product_review.eligibility": {
            "orderId": order_id,
            "orderItemId": order.get("orderItemId"),
            "listingId": product.get("listingId"),
            "listingOfferId": product.get("listingOfferId"),
            "canonicalSpuId": product.get("canonicalSpuId"),
            "canonicalSkuId": product.get("canonicalSkuId"),
        },
        "app.product_review.create": {
            "reviewId": review.get("reviewId"),
            "orderId": order_id,
            "orderItemId": order.get("orderItemId"),
            "listingId": product.get("listingId"),
            "canonicalSpuId": product.get("canonicalSpuId"),
            "canonicalSkuId": product.get("canonicalSkuId"),
        },
        "app.product_review.listing": {
            "total": review.get("total"),
        },
    }
    for stage_id, fields in receipt_links.items():
        for field, expected in fields.items():
            _same(
                step_evidence[stage_id].get(field),
                expected,
                f"{stage_id} receipt {field}",
            )
    quality_receipt = step_evidence["operator.quality.release"]
    _same(
        quality_receipt.get("qualityStatus"),
        product.get("qualityStatus"),
        "quality release receipt qualityStatus",
    )
    _same(
        quality_receipt.get("inspectionDecision"),
        "PASS",
        "quality release receipt inspectionDecision",
    )
    _require(
        isinstance(quality_receipt.get("qualityStandardVersion"), int)
        and quality_receipt["qualityStandardVersion"] > 0,
        "quality release receipt qualityStandardVersion must be positive",
    )
    _require(
        isinstance(quality_receipt.get("outboxEventIds"), list)
        and quality_receipt["outboxEventIds"],
        "quality release receipt requires non-empty outboxEventIds",
    )
    _same(
        step_evidence["operator.catalog.metadata_update"].get("businessCode"),
        step_evidence["app.product.detail"].get("skus")[0].get("skuCode"),
        "catalog metadata to product detail skuCode",
    )
    _same(
        step_evidence["operator.catalog.barcode_rotate"].get("currentBarcode"),
        step_evidence["app.product.detail"].get("skus")[0].get("barcode"),
        "catalog barcode to product detail barcode",
    )
    _same(
        step_evidence["operator.supply.prepare"].get("status"),
        "PREPARE",
        "supply prepare status",
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
    lakehouse_receipt = step_evidence["reconcile.lakehouse"]
    for field in (
        "outboxCdcCheckpointSucceeded",
        "fullDenominator",
        "nonempty",
        "sourceToFactMismatchCount",
        "factToProjectionMismatchCount",
        "crossTenantLinkCount",
        "identityLinkMismatchCount",
        "productLinkMismatchCount",
        "orderPaymentMoneyMismatchCount",
        "returnQuantityMismatchCount",
        "dqcViolationCount",
        "modelResults",
    ):
        _same(
            lakehouse_receipt.get(field),
            lakehouse.get(field),
            f"lakehouse receipt {field}",
        )
    _require(
        _has_value(lakehouse_receipt.get("dataFreshnessAt")),
        "lakehouse receipt dataFreshnessAt is required",
    )

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

    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("--run-id", required=True)
    execute_parser.add_argument("--environment", choices=sorted(EXECUTE_ENVIRONMENTS), required=True)
    execute_parser.add_argument("--approval", type=Path, required=True)
    execute_parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    execute_parser.add_argument("--output", type=Path)

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("--run-id", required=True)
    resume_parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    resume_parser.add_argument("--receipt", type=Path, action="append", default=[])
    resume_parser.add_argument("--output", type=Path)

    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("--run-id", required=True)
    replay_parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    replay_parser.add_argument("--terminal-evidence", type=Path, required=True)
    replay_parser.add_argument("--output", type=Path)

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
        elif args.command == "execute":
            result = initialize_runtime(
                args.run_id,
                args.environment,
                load_json(args.approval.resolve()),
                contracts,
                runtime_root=args.runtime_root.resolve(),
            )
            _write_result(result, args.output)
        elif args.command == "resume":
            runtime_dir = _runtime_dir(args.runtime_root.resolve(), args.run_id)
            receipts = [load_json(path.resolve()) for path in args.receipt]
            result = record_runtime_receipts(runtime_dir, receipts, contracts)
            _write_result(result, args.output)
        elif args.command == "replay":
            runtime_dir = _runtime_dir(args.runtime_root.resolve(), args.run_id)
            ledger = build_runtime_ledger(
                runtime_dir,
                load_json(args.terminal_evidence.resolve()),
                contracts,
            )
            if args.output:
                _write_result(ledger, args.output)
            else:
                _write_result(ledger, None)
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
