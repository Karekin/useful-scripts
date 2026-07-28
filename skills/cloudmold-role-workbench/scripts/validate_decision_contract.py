#!/usr/bin/env python3
"""Validate one bounded DeerFlow decision before CloudMold policy evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "cloudmold.deerflow-decision/v1"
ALLOWED_STATUS = {"READY", "NEEDS_DATA", "NEEDS_REVIEW"}
REQUIRED_FIELDS = {
    "schemaVersion", "decisionType", "status", "facts", "options",
    "recommendation", "risks", "confidence", "missingFacts",
}
ALLOWED_FIELDS = REQUIRED_FIELDS | {"evidenceRefs"}
FORBIDDEN_KEYS = {
    "tenant", "tenantid", "operator", "operatorid", "idempotencykey",
    "approvalid", "approvalscope", "executionpermit", "executionticket", "ticket",
}


class DecisionContractError(ValueError):
    """Raised when DeerFlow output crosses the bounded decision contract."""


def _normalized_key(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _reject_forbidden_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if _normalized_key(str(key)) in FORBIDDEN_KEYS:
                raise DecisionContractError(f"{path}.{key} is owned by CloudMold, not DeerFlow")
            _reject_forbidden_keys(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden_keys(nested, f"{path}[{index}]")


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionContractError(f"{field} must be a non-empty string")
    return value.strip()


def validate_decision(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise DecisionContractError("decision must be a JSON object")
    missing = REQUIRED_FIELDS - set(document)
    if missing:
        raise DecisionContractError(f"decision is missing fields: {sorted(missing)}")
    unexpected = set(document) - ALLOWED_FIELDS
    if unexpected:
        raise DecisionContractError(f"decision contains unsupported fields: {sorted(unexpected)}")
    if document["schemaVersion"] != SCHEMA_VERSION:
        raise DecisionContractError("unsupported decision schema version")
    _require_string(document["decisionType"], "decisionType")
    status = document["status"]
    if status not in ALLOWED_STATUS:
        raise DecisionContractError(f"unsupported decision status: {status}")
    for field in ("facts", "options", "risks", "missingFacts"):
        if not isinstance(document[field], list):
            raise DecisionContractError(f"{field} must be an array")
    if not isinstance(document["recommendation"], dict):
        raise DecisionContractError("recommendation must be an object")
    confidence = document["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise DecisionContractError("confidence must be a number between 0 and 1")
    for index, fact in enumerate(document["facts"]):
        if not isinstance(fact, dict) or set(fact) != {"sourceRef", "field", "value"}:
            raise DecisionContractError(f"facts[{index}] must contain sourceRef, field and value only")
        _require_string(fact["sourceRef"], f"facts[{index}].sourceRef")
        _require_string(fact["field"], f"facts[{index}].field")
    for index, value in enumerate(document["missingFacts"]):
        _require_string(value, f"missingFacts[{index}]")
    if document["missingFacts"] and status != "NEEDS_DATA":
        raise DecisionContractError("missingFacts requires status NEEDS_DATA")
    if status == "READY" and not document["facts"]:
        raise DecisionContractError("READY decisions require referenced facts")
    if status == "READY" and not document["recommendation"]:
        raise DecisionContractError("READY decisions require a recommendation")
    evidence_refs = document.get("evidenceRefs", [])
    if not isinstance(evidence_refs, list):
        raise DecisionContractError("evidenceRefs must be an array")
    for index, value in enumerate(evidence_refs):
        _require_string(value, f"evidenceRefs[{index}]")
    _reject_forbidden_keys(document)
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("decision", type=Path)
    args = parser.parse_args()
    try:
        document = json.loads(args.decision.read_text(encoding="utf-8"))
        validate_decision(document)
    except (OSError, json.JSONDecodeError, DecisionContractError) as error:
        print(json.dumps({"status": "REJECTED", "reason": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "ACCEPTED", "schemaVersion": SCHEMA_VERSION}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
