#!/usr/bin/env python3
"""Fail-closed CloudMold production P4 evidence gate.

Production credit requires a complete evidence denominator and an OpenSSL-
verified signature from a public key pinned in the reviewed trust policy.
Readiness never grants deployment, import, payment, or cutover authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONTRACT_ID = "cloudmold.production-p4.evidence.v1"
READINESS_ID = "cloudmold.production-p4.readiness.v1"
GATES_ID = "cloudmold.production-p4.gates.v1"
TRUST_ID = "cloudmold.production-p4.trust-policy.v1"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
BASE = Path(__file__).resolve().parents[1]
DEFAULT_GATES = BASE / "references" / "production-p4-gates-v1.json"
DEFAULT_TRUST = BASE / "references" / "production-trust-policy-v1.json"


class EvidenceError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise EvidenceError(f"missing regular non-symlink JSON file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"JSON root must be an object: {path}")
    return value


def _canonical(value: dict[str, Any], excluded: set[str] | None = None) -> bytes:
    filtered = {key: item for key, item in value.items() if key not in (excluded or set())}
    return json.dumps(
        filtered, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    return parsed if parsed.utcoffset() == timezone.utc.utcoffset(parsed) else None


def _safe_file(base: Path, ref: Any, digest: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(ref, str) or not ref.strip():
        errors.append(f"{label}_ref must be a non-empty relative path")
        return None
    relative = Path(ref)
    if relative.is_absolute() or ".." in relative.parts:
        errors.append(f"{label}_ref must not escape its evidence directory")
        return None
    try:
        root = base.resolve(strict=True)
        candidate = (base / relative).resolve(strict=True)
    except OSError as exc:
        errors.append(f"{label}_ref is missing or unreadable: {exc}")
        return None
    if root != candidate.parent and root not in candidate.parents:
        errors.append(f"{label}_ref escapes its evidence directory")
        return None
    if (base / relative).is_symlink() or not candidate.is_file() or candidate.stat().st_size == 0:
        errors.append(f"{label}_ref must be a non-empty regular non-symlink file")
        return None
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        errors.append(f"{label}_sha256 must be lowercase SHA-256")
    elif _file_digest(candidate) != digest:
        errors.append(f"{label}_sha256 does not match {label}_ref")
    return candidate


def _validate_registry(registry: dict[str, Any]) -> list[dict[str, Any]]:
    if registry.get("contract_id") != GATES_ID:
        raise EvidenceError(f"gate registry contract_id must be {GATES_ID}")
    gates = registry.get("gates")
    if not isinstance(gates, list) or not gates:
        raise EvidenceError("gate registry must contain a non-empty gates list")
    ids = [gate.get("gate_id") for gate in gates if isinstance(gate, dict)]
    if len(ids) != len(gates) or not all(isinstance(item, str) and item for item in ids):
        raise EvidenceError("every gate registry entry requires gate_id")
    if len(set(ids)) != len(ids):
        raise EvidenceError("gate registry contains duplicate gate_id")
    return gates


def _trusted_signer(
    trust_path: Path,
    signer_id: Any,
    account: Any,
    region: Any,
    errors: list[str],
) -> tuple[dict[str, Any] | None, Path | None]:
    trust = _load(trust_path)
    if trust.get("contract_id") != TRUST_ID:
        errors.append(f"trust policy contract_id must be {TRUST_ID}")
        return None, None
    signers = trust.get("signers")
    if not isinstance(signers, list) or not signers:
        errors.append("no reviewed production trust anchors are configured")
        return None, None
    matches = [item for item in signers if isinstance(item, dict) and item.get("signer_id") == signer_id]
    if len(matches) != 1:
        errors.append("manifest signer_id is not uniquely pinned by the trust policy")
        return None, None
    signer = matches[0]
    if signer.get("provider") not in {
        "ALIBABA_CLOUD_KMS_ASYMMETRIC",
        "APPROVED_ENTERPRISE_CA",
        "SIGSTORE_KEYLESS_EXPORT",
    }:
        errors.append("trusted signer provider is not an approved production trust source")
    if account not in signer.get("allowed_production_accounts", []):
        errors.append("production account is not allowed by the signer trust policy")
    if region not in signer.get("allowed_regions", []):
        errors.append("production region is not allowed by the signer trust policy")
    key = _safe_file(
        trust_path.parent,
        signer.get("public_key_ref"),
        signer.get("public_key_sha256"),
        "trusted_public_key",
        errors,
    )
    return signer, key


def _verify_signature(public_key: Path, signature: Path, payload: bytes) -> str | None:
    try:
        result = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-verify",
                str(public_key),
                "-signature",
                str(signature),
            ],
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"unable to run OpenSSL signature verification: {exc}"
    if result.returncode != 0:
        return "manifest signature is not valid for the pinned production signer"
    return None


def _base_readiness(checked_at: str, registry: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "contract_id": READINESS_ID,
        "checked_at": checked_at,
        "status": "BLOCKED_PRODUCTION_EVIDENCE",
        "production_credit": False,
        "required_gate_count": len(registry),
        "verified_gate_count": 0,
        "completion_percent": 0.0,
        "verified_gate_ids": [],
        "blocked_gate_ids": [gate["gate_id"] for gate in registry],
        "errors": [],
        "authorization": {
            "deploy_enabled": False,
            "payment_enabled": False,
            "import_enabled": False,
            "cutover_enabled": False,
            "note": "Readiness evidence never grants production mutation authority."
        }
    }


def blocked_readiness(checked_at: str, reason: str, gates_path: Path = DEFAULT_GATES) -> dict[str, Any]:
    if _utc(checked_at) is None:
        raise EvidenceError("checked_at must be an explicit UTC timestamp")
    registry = _validate_registry(_load(gates_path))
    result = _base_readiness(checked_at, registry)
    result["errors"] = [reason]
    return result


def evaluate(
    manifest_path: Path,
    checked_at: str,
    *,
    gates_path: Path = DEFAULT_GATES,
    trust_path: Path = DEFAULT_TRUST,
) -> dict[str, Any]:
    checked = _utc(checked_at)
    if checked is None:
        raise EvidenceError("checked_at must be an explicit UTC timestamp")
    registry = _validate_registry(_load(gates_path))
    result = _base_readiness(checked_at, registry)
    errors: list[str] = []
    manifest = _load(manifest_path)
    base = manifest_path.parent

    if manifest.get("contract_id") != CONTRACT_ID:
        errors.append(f"manifest contract_id must be {CONTRACT_ID}")
    if manifest.get("environment") != "production":
        errors.append("manifest environment must be production")
    for key in ("run_id", "production_account_id", "region", "deployment_revision"):
        if not isinstance(manifest.get(key), str) or not manifest[key].strip():
            errors.append(f"manifest {key} is required")
    if not isinstance(manifest.get("source_commit"), str) or not COMMIT.fullmatch(manifest["source_commit"]):
        errors.append("manifest source_commit must be a full Git commit")
    if not isinstance(manifest.get("image_digest"), str) or not IMAGE_DIGEST.fullmatch(manifest["image_digest"]):
        errors.append("manifest image_digest must be sha256:<64 lowercase hex>")

    collected = _utc(manifest.get("collected_at"))
    if collected is None:
        errors.append("manifest collected_at must be UTC")
    elif collected > checked:
        errors.append("manifest collected_at is in the future")

    collector = manifest.get("collector")
    collector = collector if isinstance(collector, dict) else {}
    collector_identity = collector.get("identity")
    collector_environment = collector.get("environment_id")
    if not isinstance(collector_identity, str) or not collector_identity:
        errors.append("collector.identity is required")
    if not isinstance(collector_environment, str) or not collector_environment:
        errors.append("collector.environment_id is required")
    _safe_file(
        base,
        collector.get("access_attestation_ref"),
        collector.get("access_attestation_sha256"),
        "collector_access_attestation",
        errors,
    )

    canonical = _canonical(
        manifest, {"manifest_sha256", "signature_ref", "signature_sha256"}
    )
    if manifest.get("manifest_sha256") != _digest(canonical):
        errors.append("manifest_sha256 does not match canonical manifest payload")
    signature = _safe_file(
        base,
        manifest.get("signature_ref"),
        manifest.get("signature_sha256"),
        "manifest_signature",
        errors,
    )
    _, public_key = _trusted_signer(
        trust_path,
        manifest.get("signer_id"),
        manifest.get("production_account_id"),
        manifest.get("region"),
        errors,
    )
    if signature is not None and public_key is not None:
        signature_error = _verify_signature(public_key, signature, canonical)
        if signature_error:
            errors.append(signature_error)

    expected = {gate["gate_id"]: gate for gate in registry}
    entries = manifest.get("gates")
    entries = entries if isinstance(entries, list) else []
    if not isinstance(manifest.get("gates"), list):
        errors.append("manifest gates must be a list")
    seen: set[str] = set()
    verified: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"gates[{index}] must be an object")
            continue
        gate_id = entry.get("gate_id")
        label = f"gates[{gate_id!r}]"
        if gate_id in seen:
            errors.append(f"{label} is duplicated")
            continue
        seen.add(gate_id)
        requirement = expected.get(gate_id)
        if requirement is None:
            errors.append(f"{label} is not in the reviewed denominator")
            continue
        gate_errors: list[str] = []
        if entry.get("evidence_class") != "PRODUCTION_OBSERVED":
            gate_errors.append(f"{label}.evidence_class must be PRODUCTION_OBSERVED")
        if entry.get("fixture") is not False:
            gate_errors.append(f"{label}.fixture must be false")
        observed = _utc(entry.get("observed_at"))
        if observed is None:
            gate_errors.append(f"{label}.observed_at must be UTC")
        elif observed > checked:
            gate_errors.append(f"{label}.observed_at is in the future")
        elif (checked - observed).total_seconds() > requirement["max_age_seconds"]:
            gate_errors.append(f"{label} evidence is stale")
        _safe_file(
            base,
            entry.get("artifact_ref"),
            entry.get("artifact_sha256"),
            f"{label}.artifact",
            gate_errors,
        )
        assertions = entry.get("assertions")
        assertions = assertions if isinstance(assertions, dict) else {}
        for key, expected_value in requirement.get("required_assertions", {}).items():
            if assertions.get(key) != expected_value:
                gate_errors.append(f"{label}.assertions.{key} must equal {expected_value!r}")
        measurements = entry.get("measurements")
        measurements = measurements if isinstance(measurements, dict) else {}
        for key, minimum in requirement.get("minimum_measurements", {}).items():
            value = measurements.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < minimum:
                gate_errors.append(f"{label}.measurements.{key} must be >= {minimum}")
        verifier = entry.get("independent_verifier")
        verifier = verifier if isinstance(verifier, dict) else {}
        identity = verifier.get("identity")
        environment = verifier.get("environment_id")
        if not isinstance(identity, str) or not identity:
            gate_errors.append(f"{label}.independent_verifier.identity is required")
        if identity == collector_identity:
            gate_errors.append(f"{label} verifier identity must differ from collector")
        if not isinstance(environment, str) or not environment:
            gate_errors.append(f"{label}.independent_verifier.environment_id is required")
        if environment == collector_environment:
            gate_errors.append(f"{label} verifier environment must differ from collector")
        executed = _utc(verifier.get("executed_at"))
        if executed is None:
            gate_errors.append(f"{label}.independent_verifier.executed_at must be UTC")
        elif observed is not None and executed < observed:
            gate_errors.append(f"{label} independent verification predates observation")
        elif executed > checked:
            gate_errors.append(f"{label} independent verification is in the future")
        _safe_file(
            base,
            verifier.get("attestation_ref"),
            verifier.get("attestation_sha256"),
            f"{label}.independent_verifier.attestation",
            gate_errors,
        )
        if gate_errors:
            errors.extend(gate_errors)
        else:
            verified.append(gate_id)

    missing = sorted(set(expected) - seen)
    errors.extend(f"missing required production gate: {gate_id}" for gate_id in missing)
    verified = sorted(verified)
    result["verified_gate_ids"] = verified
    result["verified_gate_count"] = len(verified)
    result["blocked_gate_ids"] = sorted(set(expected) - set(verified))
    result["completion_percent"] = round(100 * len(verified) / len(expected), 1)
    result["errors"] = sorted(set(errors))
    if not errors and len(verified) == len(expected):
        result["status"] = "PRODUCTION_P4_READY"
        result["production_credit"] = True
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    requirements = sub.add_parser("requirements")
    requirements.add_argument("--checked-at", required=True)
    check = sub.add_parser("check")
    check.add_argument("--manifest", type=Path, required=True)
    check.add_argument("--checked-at", required=True)
    check.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "requirements":
        result = blocked_readiness(
            args.checked_at, "production evidence manifest was not supplied"
        )
    else:
        result = evaluate(args.manifest.resolve(), args.checked_at)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if getattr(args, "output", None):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "PRODUCTION_P4_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
