"""Fail-closed production evidence collection and readiness generation.

This module deliberately does not connect to Y-Shopping.  It admits only an
operator-produced, tamper-evident collection manifest and the production
artifacts referenced by that manifest.  Missing external access therefore
produces a blocked readiness document instead of synthetic runtime credit.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from source_evidence import (
    SourceEvidenceError,
    canonical_sha256,
    file_sha256,
    load_json_object,
    validate_bundle,
    validate_reconciliation,
)


COLLECTION_CONTRACT_ID = "cloudmold.yshopping.production-evidence-collection.v1"
READINESS_CONTRACT_ID = "cloudmold.yshopping.production-evidence-readiness.v1"
ASSET_UNIVERSE_CONTRACT_ID = "cloudmold.yshopping.production-asset-universe.v1"
EXPECTED_ASSET_COUNT = 718
CANONICAL_ASSET_UNIVERSE = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "yshopping-production-asset-universe-v1.json"
)
GTID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}:[0-9]+(?:-[0-9]+)?"
    r"(?:,[0-9a-fA-F-]{36}:[0-9]+(?:-[0-9]+)?)*$"
)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _utc(value: Any) -> datetime | None:
    if not _nonempty(value) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    return parsed if parsed.utcoffset() == timezone.utc.utcoffset(parsed) else None


def _safe_file(base: Path, value: Any, label: str, errors: list[str]) -> Path | None:
    if not _nonempty(value):
        errors.append(f"{label} must be a non-empty relative path")
        return None
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        errors.append(f"{label} must not escape the collection directory")
        return None
    try:
        base_resolved = base.resolve(strict=True)
        resolved = (base / relative).resolve(strict=True)
    except OSError as exc:
        errors.append(f"{label} is missing or unreadable: {exc}")
        return None
    if base_resolved != resolved.parent and base_resolved not in resolved.parents:
        errors.append(f"{label} escapes the collection directory")
        return None
    if (base / relative).is_symlink() or not resolved.is_file() or resolved.stat().st_size == 0:
        errors.append(f"{label} must be a non-empty regular non-symlink file")
        return None
    return resolved


def _document_ref(
    base: Path,
    owner: dict[str, Any],
    ref_key: str,
    digest_key: str,
    label: str,
    errors: list[str],
) -> Path | None:
    path = _safe_file(base, owner.get(ref_key), f"{label}.{ref_key}", errors)
    digest = owner.get(digest_key)
    if not _sha256(digest):
        errors.append(f"{label}.{digest_key} must be SHA-256")
    elif path is not None and file_sha256(path) != digest:
        errors.append(f"{label}.{digest_key} does not match {ref_key}")
    return path


def _asset_names_digest(names: list[str]) -> str:
    payload = json.dumps(
        sorted(names), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _external_access_errors(collection: dict[str, Any], base: Path) -> list[str]:
    errors: list[str] = []
    access = collection.get("external_access")
    if not isinstance(access, dict):
        return ["external_access must be an object"]
    if access.get("source_environment") != "production":
        errors.append("external_access.source_environment must be production")
    for key in ("endpoint_id", "read_only_identity", "identity_provider"):
        if not _nonempty(access.get(key)):
            errors.append(f"external_access.{key} is required")
    if access.get("read_only_confirmed") is not True:
        errors.append("external_access.read_only_confirmed must be true")
    if access.get("production_read_attempted") is not True:
        errors.append("external_access.production_read_attempted must be true")
    _document_ref(
        base,
        access,
        "audit_export_ref",
        "audit_export_sha256",
        "external_access",
        errors,
    )
    return errors


def _load_asset_universe(
    collection: dict[str, Any], base: Path, errors: list[str]
) -> list[str]:
    try:
        canonical = load_json_object(CANONICAL_ASSET_UNIVERSE)
    except SourceEvidenceError as exc:
        errors.append(f"canonical asset universe is unavailable: {exc}")
        return []
    if canonical.get("contract_id") != ASSET_UNIVERSE_CONTRACT_ID:
        errors.append("canonical asset universe contract_id is invalid")
        return []
    canonical_assets = canonical.get("assets")
    if (
        not isinstance(canonical_assets, list)
        or len(canonical_assets) != EXPECTED_ASSET_COUNT
        or canonical_assets != sorted(canonical_assets)
        or len(set(canonical_assets)) != EXPECTED_ASSET_COUNT
    ):
        errors.append("canonical asset universe must contain 718 unique sorted assets")
        return []
    canonical_digest = _asset_names_digest(canonical_assets)
    if canonical.get("assets_sha256") != canonical_digest:
        errors.append("canonical asset universe assets_sha256 is invalid")
        return []

    denominator = collection.get("denominator")
    if not isinstance(denominator, dict):
        errors.append("denominator must be an object")
        return []
    if denominator.get("expected_asset_count") != EXPECTED_ASSET_COUNT:
        errors.append(f"denominator.expected_asset_count must equal {EXPECTED_ASSET_COUNT}")
    universe_path = _document_ref(
        base,
        denominator,
        "asset_universe_ref",
        "asset_universe_sha256",
        "denominator",
        errors,
    )
    if universe_path is None:
        return []
    try:
        universe = load_json_object(universe_path)
    except SourceEvidenceError as exc:
        errors.append(str(exc))
        return []
    if universe.get("contract_id") != ASSET_UNIVERSE_CONTRACT_ID:
        errors.append(f"asset universe contract_id must be {ASSET_UNIVERSE_CONTRACT_ID}")
    assets = universe.get("assets")
    if not isinstance(assets, list) or not all(_nonempty(item) for item in assets):
        errors.append("asset universe assets must be a string list")
        return []
    if len(assets) != EXPECTED_ASSET_COUNT:
        errors.append(f"asset universe must contain exactly {EXPECTED_ASSET_COUNT} assets")
    if len(set(assets)) != len(assets):
        errors.append("asset universe contains duplicate assets")
    if assets != sorted(assets):
        errors.append("asset universe assets must be sorted")
    observed_digest = _asset_names_digest(assets)
    if universe.get("assets_sha256") != observed_digest:
        errors.append("asset universe assets_sha256 does not match the complete asset list")
    if denominator.get("asset_names_sha256") != observed_digest:
        errors.append("denominator.asset_names_sha256 does not match the asset universe")
    if assets != canonical_assets:
        errors.append(
            "collection asset universe does not match the repository-governed canonical denominator"
        )
    if observed_digest != canonical_digest:
        errors.append(
            "collection asset universe digest does not match the canonical denominator"
        )
    return canonical_assets


def _validate_fresh_production_pair(
    *,
    base: Path,
    entry: dict[str, Any],
    checked_at: datetime,
    max_age_seconds: int,
) -> list[str]:
    errors: list[str] = []
    asset = entry.get("source_asset")
    label = f"entries[{asset!r}]"
    if entry.get("evidence_class") != "PRODUCTION_OBSERVED":
        errors.append(f"{label}.evidence_class must be PRODUCTION_OBSERVED")
    if entry.get("fixture") is not False:
        errors.append(f"{label}.fixture must be false")
    bundle_path = _document_ref(
        base, entry, "bundle_ref", "bundle_sha256", label, errors
    )
    reconciliation_path = _document_ref(
        base,
        entry,
        "reconciliation_ref",
        "reconciliation_sha256",
        label,
        errors,
    )
    if bundle_path is None or reconciliation_path is None:
        return errors

    errors.extend(validate_bundle(bundle_path, require_production=True))
    errors.extend(
        validate_reconciliation(
            reconciliation_path,
            expected_asset=asset if _nonempty(asset) else None,
            require_production=True,
        )
    )
    try:
        bundle = load_json_object(bundle_path)
        reconciliation = load_json_object(reconciliation_path)
    except SourceEvidenceError as exc:
        return errors + [str(exc)]

    provenance = bundle.get("provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    if provenance.get("fixture") is not False:
        errors.append(f"{label}: bundle provenance.fixture must be false")
    extractor_identity = provenance.get("extractor_identity")
    extractor_environment = provenance.get("extractor_environment_id")
    if not _nonempty(extractor_environment):
        errors.append(f"{label}: provenance.extractor_environment_id is required")

    extraction = bundle.get("extraction")
    extraction = extraction if isinstance(extraction, dict) else {}
    watermark = extraction.get("watermark")
    watermark = watermark if isinstance(watermark, dict) else {}
    if watermark.get("kind") != "MYSQL_GTID_SET":
        errors.append(f"{label}: extraction.watermark.kind must be MYSQL_GTID_SET")
    if not _nonempty(watermark.get("value")) or not GTID_PATTERN.fullmatch(watermark["value"]):
        errors.append(f"{label}: extraction.watermark.value must be a concrete MySQL GTID set")
    if not _nonempty(watermark.get("server_id")):
        errors.append(f"{label}: extraction.watermark.server_id is required")

    extracted_at = _utc(extraction.get("extracted_at"))
    if extracted_at is None:
        errors.append(f"{label}: extraction.extracted_at must be UTC")
    elif extracted_at > checked_at:
        errors.append(f"{label}: extraction timestamp is in the future")
    elif (checked_at - extracted_at).total_seconds() > max_age_seconds:
        errors.append(f"{label}: source evidence is stale")

    verifier = reconciliation.get("independent_verifier")
    verifier = verifier if isinstance(verifier, dict) else {}
    verifier_identity = verifier.get("identity")
    verifier_environment = verifier.get("environment_id")
    if not _nonempty(verifier_identity):
        errors.append(f"{label}: independent_verifier.identity is required")
    if verifier_identity == extractor_identity:
        errors.append(f"{label}: independent verifier identity must differ from extractor identity")
    if not _nonempty(verifier_environment):
        errors.append(f"{label}: independent_verifier.environment_id is required")
    if verifier_environment == extractor_environment:
        errors.append(f"{label}: independent verifier environment must differ from extractor environment")
    _document_ref(
        reconciliation_path.parent,
        verifier,
        "execution_attestation_ref",
        "execution_attestation_sha256",
        f"{label}.independent_verifier",
        errors,
    )
    executed_at = _utc(verifier.get("executed_at"))
    if extracted_at is not None and executed_at is not None and executed_at < extracted_at:
        errors.append(f"{label}: independent verification predates extraction")
    if executed_at is not None and executed_at > checked_at:
        errors.append(f"{label}: independent verification timestamp is in the future")
    return errors


def blocked_readiness(checked_at: str, reasons: list[str]) -> dict[str, Any]:
    """Build a deterministic zero-credit readiness document."""
    if _utc(checked_at) is None:
        raise SourceEvidenceError("checked_at must be an explicit UTC timestamp")
    result: dict[str, Any] = {
        "contractId": READINESS_CONTRACT_ID,
        "checkedAt": checked_at,
        "status": "BLOCKED_EXTERNAL_ACCESS",
        "sourceInventory": {
            "logicalAssets": EXPECTED_ASSET_COUNT,
            "runtimeReconciliations": 0,
            "finalVerified": 0,
            "activeModelPipelineViolations": 0,
        },
        "evidenceDiscovery": {
            "productionBundles": 0,
            "independentReconciliations": 0,
            "fixtureBundlesCredited": 0,
            "emptyBundlesCredited": 0,
            "collectorImplemented": True,
            "validatorImplemented": True,
        },
        "localConfiguration": {
            "productionSourceEndpointConfigured": False,
            "productionReadOnlyIdentityConfigured": False,
            "sourceAuditExportConfigured": False,
            "independentVerifierEnvironmentConfigured": False,
        },
        "missingExternalRequirements": sorted(set(reasons)),
        "authorization": {
            "productionReadAttempted": False,
            "importEnabled": False,
            "cutoverEnabled": False,
        },
        "conclusion": "No production credit was granted without external production evidence.",
    }
    result["readinessSha256"] = canonical_sha256(result, "readinessSha256")
    return result


def generate_readiness(collection_path: Path) -> tuple[dict[str, Any], list[str]]:
    """Validate a collection and deterministically generate its readiness."""
    collection = load_json_object(collection_path)
    checked_at_raw = collection.get("readiness_checked_at")
    checked_at = _utc(checked_at_raw)
    if checked_at is None:
        raise SourceEvidenceError("readiness_checked_at must be an explicit UTC timestamp")
    if collection.get("contract_id") != COLLECTION_CONTRACT_ID:
        raise SourceEvidenceError(f"contract_id must be {COLLECTION_CONTRACT_ID}")
    try:
        uuid.UUID(str(collection.get("collection_id")))
    except (ValueError, AttributeError):
        raise SourceEvidenceError("collection_id must be a UUID")
    if collection.get("collection_sha256") != canonical_sha256(
        collection, "collection_sha256"
    ):
        raise SourceEvidenceError("collection_sha256 does not match canonical collection content")

    errors = _external_access_errors(collection, collection_path.parent)
    assets = _load_asset_universe(collection, collection_path.parent, errors)
    freshness = collection.get("freshness")
    freshness = freshness if isinstance(freshness, dict) else {}
    max_age_seconds = freshness.get("max_age_seconds")
    if (
        not isinstance(max_age_seconds, int)
        or isinstance(max_age_seconds, bool)
        or max_age_seconds <= 0
        or max_age_seconds > 86400
    ):
        errors.append("freshness.max_age_seconds must be an integer in 1..86400")
        max_age_seconds = 1

    entries = collection.get("entries")
    if not isinstance(entries, list):
        errors.append("entries must be a list")
        entries = []
    entry_assets = [
        entry.get("source_asset") for entry in entries if isinstance(entry, dict)
    ]
    if len(set(entry_assets)) != len(entry_assets):
        errors.append("entries contain duplicate source assets")
    unknown = sorted(set(entry_assets) - set(assets))
    if unknown:
        errors.append(f"entries contain assets outside the governed denominator: {unknown}")

    credited: list[str] = []
    rejected: dict[str, list[str]] = {}
    for entry in sorted(
        (item for item in entries if isinstance(item, dict)),
        key=lambda item: str(item.get("source_asset", "")),
    ):
        asset = entry.get("source_asset")
        pair_errors = _validate_fresh_production_pair(
            base=collection_path.parent,
            entry=entry,
            checked_at=checked_at,
            max_age_seconds=max_age_seconds,
        )
        if pair_errors:
            rejected[str(asset)] = sorted(set(pair_errors))
        elif asset in assets:
            credited.append(asset)

    access_blocked = bool(_external_access_errors(collection, collection_path.parent))
    status = (
        "BLOCKED_EXTERNAL_ACCESS"
        if access_blocked
        else "EVIDENCE_VERIFIED_UNTRUSTED"
        if len(credited) == EXPECTED_ASSET_COUNT and not errors and not rejected
        else "BLOCKED_INCOMPLETE_OR_INVALID_EVIDENCE"
    )
    result: dict[str, Any] = {
        "contractId": READINESS_CONTRACT_ID,
        "checkedAt": checked_at_raw,
        "status": status,
        "sourceInventory": {
            "logicalAssets": EXPECTED_ASSET_COUNT,
            "runtimeReconciliations": len(credited),
            "finalVerified": (
                len(credited) if status == "EVIDENCE_VERIFIED_UNTRUSTED" else 0
            ),
            "activeModelPipelineViolations": 0,
        },
        "evidenceDiscovery": {
            "productionBundles": len(credited),
            "independentReconciliations": len(credited),
            "fixtureBundlesCredited": 0,
            "emptyBundlesCredited": 0,
            "collectorImplemented": True,
            "validatorImplemented": True,
            "creditedAssets": sorted(credited),
            "rejectedAssets": rejected,
        },
        "localConfiguration": {
            "productionSourceEndpointConfigured": not access_blocked,
            "productionReadOnlyIdentityConfigured": not access_blocked,
            "sourceAuditExportConfigured": not access_blocked,
            "independentVerifierEnvironmentConfigured": not access_blocked,
        },
        "authorization": {
            "productionReadAttempted": not access_blocked,
            "importEnabled": False,
            "cutoverEnabled": False,
        },
        "productionCredit": False,
        "missingExternalRequirements": (
            sorted(set(_external_access_errors(collection, collection_path.parent)))
            if access_blocked
            else []
        ),
        "validationErrors": sorted(set(errors)),
        "conclusion": (
            "All 718 assets passed local semantic evidence validation, but production "
            "admission still requires a trusted signed aggregate gate."
            if status == "EVIDENCE_VERIFIED_UNTRUSTED"
            else "Import and cutover remain disabled; evidence readiness never grants authority."
        ),
    }
    result["readinessSha256"] = canonical_sha256(result, "readinessSha256")
    return result, errors


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
