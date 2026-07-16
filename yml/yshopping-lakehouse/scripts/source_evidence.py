"""Fail-closed validation for Y-Shopping source and reconciliation evidence.

The source documents are design evidence, not runtime data.  These validators make
runtime credit depend on a non-empty, full-denominator production snapshot whose
payload files and independent reconciliation are tamper-evident.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


BUNDLE_CONTRACT_ID = "yshopping.source-evidence-bundle.v1"
RECONCILIATION_CONTRACT_ID = "yshopping.source-reconciliation-evidence.v1"
TRADE_ADMISSION_CONTRACT_ID = "yshopping.trade-history-admission.v1"
METADATA_RUNTIME_POLICY_CONTRACT_ID = "yshopping.metadata.runtime-evidence-policy.v1"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_SEMANTIC_ARTIFACTS = {
    "money": "currency_unit",
    "quantity": "quantity_unit",
    "timestamp": "timezone",
    "status": "status_dictionary",
}
TRADE_ADMISSION_PATH = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "yshopping-trade-history-admission-v1.json"
)
METADATA_DISPOSITION_PATH = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "yshopping-metadata-source-disposition-v1.json"
)
METADATA_SOURCE_ASSETS = {
    "ods_meta_task_instance_di",
    "ods_meta_task_node_df",
    "ods_sla_parent_child_nodes_df",
    "ods_sla_sla_task_df",
    "ods_meta_table_df",
    "ods_meta_table_columns_df",
    "ods_meta_table_lineage_df",
    "ods_meta_dq_dqc_df",
    "ods_meta_dq_dqc_instance_df",
    "ods_metrics_metrics_info_df",
}
ALLOWED_SEMANTIC_ARTIFACT_KINDS = {
    "currency_unit", "quantity_unit", "timezone", "status_dictionary",
    "tenant_mapping", "identity_mapping", "catalog_mapping", "listing_mapping",
    "inventory_mapping", "benefit_type_mapping", "entitlement_mapping",
    "subsidy_schema",
}


class SourceEvidenceError(RuntimeError):
    pass


def canonical_sha256(value: dict[str, Any], digest_field: str) -> str:
    normalized = dict(value)
    normalized.pop(digest_field, None)
    payload = json.dumps(
        normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SourceEvidenceError(f"cannot load JSON evidence {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SourceEvidenceError(f"{path}: root must be an object")
    return value


def _trade_admission_asset(source_asset: Any) -> dict[str, Any] | None:
    if not _nonempty_string(source_asset) or not TRADE_ADMISSION_PATH.is_file():
        return None
    try:
        contract = load_json_object(TRADE_ADMISSION_PATH)
    except SourceEvidenceError:
        return None
    for asset in contract.get("assets", []):
        if isinstance(asset, dict) and asset.get("source_asset") == source_asset:
            return asset
    return None


def _metadata_runtime_policy(source_asset: Any) -> tuple[dict[str, Any], dict[str, Any]] | None:
    if source_asset not in METADATA_SOURCE_ASSETS:
        return None
    contract = load_json_object(METADATA_DISPOSITION_PATH)
    policy = contract.get("runtime_evidence_policy")
    if not isinstance(policy, dict) or policy.get("contract_id") != METADATA_RUNTIME_POLICY_CONTRACT_ID:
        raise SourceEvidenceError("Metadata runtime evidence policy is missing or invalid")
    requirements = policy.get("assets")
    requirement = requirements.get(source_asset) if isinstance(requirements, dict) else None
    if not isinstance(requirement, dict):
        raise SourceEvidenceError(f"Metadata runtime evidence requirement is missing for {source_asset}")
    return policy, requirement


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _valid_uuid(value: Any) -> bool:
    if not _nonempty_string(value):
        return False
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError):
        return False
    return True


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None


def _valid_utc_timestamp(value: Any) -> bool:
    if not _nonempty_string(value) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return True


def _safe_relative_file(base: Path, value: Any, label: str, errors: list[str]) -> Path | None:
    if not _nonempty_string(value):
        errors.append(f"{label}: path must be a non-empty relative path")
        return None
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        errors.append(f"{label}: path traversal and absolute paths are forbidden")
        return None
    path = base / relative
    try:
        resolved_base = base.resolve(strict=True)
        resolved_path = path.resolve(strict=True)
    except OSError as exc:
        errors.append(f"{label}: missing or unreadable file {path}: {exc}")
        return None
    if resolved_path.parent != resolved_base and resolved_base not in resolved_path.parents:
        errors.append(f"{label}: resolved path escapes the evidence directory")
        return None
    if path.is_symlink() or not resolved_path.is_file():
        errors.append(f"{label}: evidence payload must be a regular non-symlink file")
        return None
    return resolved_path


def validate_bundle(manifest_path: Path, *, require_production: bool = False) -> list[str]:
    errors: list[str] = []
    try:
        manifest = load_json_object(manifest_path)
    except SourceEvidenceError as exc:
        return [str(exc)]
    label = str(manifest_path)
    if manifest.get("contract_id") != BUNDLE_CONTRACT_ID:
        errors.append(f"{label}: contract_id must be {BUNDLE_CONTRACT_ID}")
    if not _valid_uuid(manifest.get("bundle_id")):
        errors.append(f"{label}: bundle_id must be a UUID")
    if manifest.get("source_system") != "YSHOPPING":
        errors.append(f"{label}: source_system must be YSHOPPING")
    environment = manifest.get("source_environment")
    if environment not in {"production", "staging", "test"}:
        errors.append(f"{label}: invalid source_environment")
    if require_production and environment != "production":
        errors.append(f"{label}: strict runtime credit requires production source evidence")
    if manifest.get("manifest_sha256") != canonical_sha256(manifest, "manifest_sha256"):
        errors.append(f"{label}: manifest_sha256 does not match canonical manifest content")

    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        errors.append(f"{label}: provenance must be an object")
        provenance = {}
    for key in ("snapshot_id", "extraction_job_id", "extractor_identity"):
        if not _nonempty_string(provenance.get(key)):
            errors.append(f"{label}: provenance.{key} is required")
    if provenance.get("attestation_method") not in {
        "SOURCE_SYSTEM_AUDIT_EXPORT", "SIGNED_JOB_METADATA"
    }:
        errors.append(f"{label}: provenance.attestation_method is invalid")
    if provenance.get("read_only_confirmed") is not True:
        errors.append(f"{label}: provenance must confirm read-only extraction")
    attestation_path = _safe_relative_file(
        manifest_path.parent,
        provenance.get("attestation_ref"),
        f"{label}: provenance.attestation_ref",
        errors,
    )
    if not _valid_sha256(provenance.get("attestation_sha256")):
        errors.append(f"{label}: provenance.attestation_sha256 must be SHA-256")
    elif attestation_path is not None and provenance["attestation_sha256"] != file_sha256(attestation_path):
        errors.append(f"{label}: provenance.attestation_sha256 differs from attestation_ref")

    source = manifest.get("source")
    if not isinstance(source, dict):
        errors.append(f"{label}: source must be an object")
        source = {}
    for key in ("asset", "qualified_table"):
        if not _nonempty_string(source.get(key)):
            errors.append(f"{label}: source.{key} is required")
    schema_path = _safe_relative_file(
        manifest_path.parent, source.get("schema_ref"), f"{label}: source.schema_ref", errors
    )
    if not _valid_sha256(source.get("schema_sha256")):
        errors.append(f"{label}: source.schema_sha256 must be SHA-256")
    elif schema_path is not None and source["schema_sha256"] != file_sha256(schema_path):
        errors.append(f"{label}: source.schema_sha256 differs from schema_ref")
    primary_key = source.get("primary_key")
    if not isinstance(primary_key, list) or not primary_key or not all(
        _nonempty_string(item) for item in primary_key
    ):
        errors.append(f"{label}: source.primary_key must be a non-empty string list")
    columns = source.get("columns")
    semantic_roles: set[str] = set()
    column_names: set[str] = set()
    if not isinstance(columns, list) or not columns:
        errors.append(f"{label}: source.columns must be non-empty")
    else:
        for index, column in enumerate(columns):
            column_label = f"{label}: source.columns[{index}]"
            if not isinstance(column, dict):
                errors.append(f"{column_label} must be an object")
                continue
            name = column.get("name")
            if not _nonempty_string(name):
                errors.append(f"{column_label}.name is required")
            elif name in column_names:
                errors.append(f"{column_label}: duplicate column {name}")
            else:
                column_names.add(name)
            if not _nonempty_string(column.get("type")):
                errors.append(f"{column_label}.type is required")
            if not isinstance(column.get("nullable"), bool):
                errors.append(f"{column_label}.nullable must be boolean")
            if column.get("classification") not in {
                "public", "internal", "confidential", "restricted"
            }:
                errors.append(f"{column_label}.classification is invalid")
            role = column.get("semantic_role")
            if role not in {
                "business_key", "tenant", "status", "money", "quantity",
                "timestamp", "partition", "attribute", "pii", "opaque"
            }:
                errors.append(f"{column_label}.semantic_role is invalid")
            else:
                semantic_roles.add(role)
    if isinstance(primary_key, list) and column_names:
        unknown_keys = set(primary_key) - column_names
        if unknown_keys:
            errors.append(f"{label}: source.primary_key contains unknown columns {sorted(unknown_keys)}")

    trade_policy = _trade_admission_asset(source.get("asset"))
    if trade_policy is not None:
        if source.get("qualified_table") != trade_policy.get("qualified_table"):
            errors.append(f"{label}: Trade qualified table differs from admission policy")
        if primary_key != trade_policy.get("business_key"):
            errors.append(f"{label}: Trade business key differs from admission policy")
        observed_schema = [
            (column.get("name"), re.sub(r"\s+", "", str(column.get("type", ""))).upper())
            for column in columns or [] if isinstance(column, dict)
        ]
        governed_schema = [
            (column.get("name"), re.sub(r"\s+", "", str(column.get("type", ""))).upper())
            for column in trade_policy.get("columns", []) if isinstance(column, dict)
        ]
        if observed_schema != governed_schema:
            errors.append(f"{label}: Trade source schema differs from admission policy")
        critical_roles = {"business_key", "status", "money", "quantity", "timestamp", "partition", "pii"}
        observed_roles = {
            column.get("name"): column.get("semantic_role")
            for column in columns or [] if isinstance(column, dict)
        }
        for column in trade_policy.get("columns", []):
            if isinstance(column, dict) and column.get("role") in critical_roles:
                if observed_roles.get(column.get("name")) != column.get("role"):
                    errors.append(
                        f"{label}: Trade column {column.get('name')} semantic role differs from admission policy"
                    )

    extraction = manifest.get("extraction")
    if not isinstance(extraction, dict):
        errors.append(f"{label}: extraction must be an object")
        extraction = {}
    if extraction.get("mode") != "READ_ONLY_SNAPSHOT":
        errors.append(f"{label}: extraction.mode must be READ_ONLY_SNAPSHOT")
    if extraction.get("full_denominator") is not True or extraction.get("sampled") is not False:
        errors.append(f"{label}: extraction must be full-denominator and non-sampled")
    query_path = _safe_relative_file(
        manifest_path.parent,
        extraction.get("query_ref"),
        f"{label}: extraction.query_ref",
        errors,
    )
    if not _valid_sha256(extraction.get("query_sha256")):
        errors.append(f"{label}: extraction.query_sha256 must be SHA-256")
    elif query_path is not None and extraction["query_sha256"] != file_sha256(query_path):
        errors.append(f"{label}: extraction.query_sha256 differs from query_ref")
    if not _valid_utc_timestamp(extraction.get("extracted_at")):
        errors.append(f"{label}: extraction.extracted_at must be a UTC timestamp")
    window = extraction.get("window")
    if not isinstance(window, dict) or not all(
        _nonempty_string(window.get(key)) for key in ("field", "start_inclusive", "end_exclusive")
    ):
        errors.append(f"{label}: extraction.window requires field and exact half-open bounds")
    watermark = extraction.get("watermark")
    if not isinstance(watermark, dict) or not all(
        _nonempty_string(watermark.get(key)) for key in ("kind", "value")
    ):
        errors.append(f"{label}: extraction.watermark requires kind and value")

    tenant = manifest.get("tenant_scope")
    if not isinstance(tenant, dict):
        errors.append(f"{label}: tenant_scope must be an object")
        tenant = {}
    if not _nonempty_string(tenant.get("strategy")):
        errors.append(f"{label}: tenant_scope.strategy is required")
    if not isinstance(tenant.get("source_keys"), list) or not tenant.get("source_keys") or not all(
        _nonempty_string(item) for item in tenant.get("source_keys", [])
    ):
        errors.append(f"{label}: tenant_scope.source_keys must be non-empty")
    if not _positive_int(tenant.get("tenant_count")):
        errors.append(f"{label}: tenant_scope.tenant_count must be positive")

    quality = manifest.get("quality")
    if not isinstance(quality, dict):
        errors.append(f"{label}: quality must be an object")
        quality = {}
    row_count = quality.get("row_count")
    for key in (
        "row_count", "distinct_business_key_count", "duplicate_business_key_count",
        "null_business_key_count", "deleted_row_count"
    ):
        if not _nonnegative_int(quality.get(key)):
            errors.append(f"{label}: quality.{key} must be a non-negative integer")
    if not _positive_int(row_count):
        errors.append(f"{label}: quality.row_count must be positive")
    if quality.get("duplicate_business_key_count") != 0:
        errors.append(f"{label}: duplicate business keys forbid strict runtime credit")
    if quality.get("null_business_key_count") != 0:
        errors.append(f"{label}: null business keys forbid strict runtime credit")
    if _nonnegative_int(row_count) and _nonnegative_int(quality.get("distinct_business_key_count")):
        if quality["distinct_business_key_count"] > row_count:
            errors.append(f"{label}: distinct business keys cannot exceed rows")

    artifacts = manifest.get("semantic_artifacts")
    artifact_kinds: set[str] = set()
    if not isinstance(artifacts, list):
        errors.append(f"{label}: semantic_artifacts must be a list")
        artifacts = []
    for index, artifact in enumerate(artifacts):
        artifact_label = f"{label}: semantic_artifacts[{index}]"
        if not isinstance(artifact, dict):
            errors.append(f"{artifact_label} must be an object")
            continue
        kind = artifact.get("kind")
        if kind not in ALLOWED_SEMANTIC_ARTIFACT_KINDS:
            errors.append(f"{artifact_label}.kind is invalid")
        else:
            artifact_kinds.add(kind)
        path = _safe_relative_file(manifest_path.parent, artifact.get("path"), artifact_label, errors)
        if path is not None:
            if not _valid_sha256(artifact.get("sha256")) or artifact["sha256"] != file_sha256(path):
                errors.append(f"{artifact_label}: sha256 mismatch")
    for role, artifact_kind in REQUIRED_SEMANTIC_ARTIFACTS.items():
        if role in semantic_roles and artifact_kind not in artifact_kinds:
            errors.append(f"{label}: semantic role {role} requires {artifact_kind} evidence")
    if "tenant_mapping" not in artifact_kinds:
        errors.append(f"{label}: every source bundle requires tenant_mapping evidence")
    if trade_policy is not None:
        missing_artifacts = set(trade_policy.get("required_semantic_artifacts", [])) - artifact_kinds
        if missing_artifacts:
            errors.append(
                f"{label}: Trade admission policy requires semantic artifacts {sorted(missing_artifacts)}"
            )

    security = manifest.get("security")
    if not isinstance(security, dict) or security.get("pii_handling") not in {
        "no_pii", "tokenized", "restricted_encrypted"
    }:
        errors.append(f"{label}: security.pii_handling is invalid")
    elif "pii" in semantic_roles and security.get("pii_handling") == "no_pii":
        errors.append(f"{label}: pii columns require tokenized or restricted_encrypted handling")

    files = manifest.get("files")
    file_rows = 0
    if not isinstance(files, list) or not files:
        errors.append(f"{label}: files must be non-empty")
    else:
        seen_paths: set[str] = set()
        for index, item in enumerate(files):
            item_label = f"{label}: files[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{item_label} must be an object")
                continue
            relative = item.get("path")
            if relative in seen_paths:
                errors.append(f"{item_label}: duplicate payload path {relative}")
            if isinstance(relative, str):
                seen_paths.add(relative)
            path = _safe_relative_file(manifest_path.parent, relative, item_label, errors)
            if item.get("format") not in {"PARQUET", "CSV", "JSONL", "AVRO"}:
                errors.append(f"{item_label}: unsupported format")
            if not _positive_int(item.get("byte_count")):
                errors.append(f"{item_label}: byte_count must be positive")
            elif path is not None and item["byte_count"] != path.stat().st_size:
                errors.append(f"{item_label}: byte_count differs from payload")
            if not _positive_int(item.get("row_count")):
                errors.append(f"{item_label}: row_count must be positive")
            else:
                file_rows += item["row_count"]
            if path is not None:
                if not _valid_sha256(item.get("sha256")) or item["sha256"] != file_sha256(path):
                    errors.append(f"{item_label}: sha256 mismatch")
    if _nonnegative_int(row_count) and file_rows != row_count:
        errors.append(f"{label}: payload file row counts do not equal quality.row_count")
    return errors


def validate_reconciliation(
    evidence_path: Path,
    *,
    expected_asset: str | None = None,
    expected_run_id: str | None = None,
    expected_row_count: int | None = None,
    expected_tenant_count: int | None = None,
    require_production: bool = True,
) -> list[str]:
    errors: list[str] = []
    try:
        evidence = load_json_object(evidence_path)
    except SourceEvidenceError as exc:
        return [str(exc)]
    label = str(evidence_path)
    if evidence.get("contract_id") != RECONCILIATION_CONTRACT_ID:
        errors.append(f"{label}: contract_id must be {RECONCILIATION_CONTRACT_ID}")
    if not _valid_uuid(evidence.get("reconciliation_id")):
        errors.append(f"{label}: reconciliation_id must be a UUID")
    if evidence.get("evidence_sha256") != canonical_sha256(evidence, "evidence_sha256"):
        errors.append(f"{label}: evidence_sha256 does not match canonical evidence content")
    for key in ("run_id", "source_asset"):
        if not _nonempty_string(evidence.get(key)):
            errors.append(f"{label}: {key} is required")
    if expected_asset is not None and evidence.get("source_asset") != expected_asset:
        errors.append(f"{label}: source_asset does not match disposition asset")
    if expected_run_id is not None and evidence.get("run_id") != expected_run_id:
        errors.append(f"{label}: run_id does not match disposition runtime")
    if evidence.get("result") != "verified":
        errors.append(f"{label}: result must be verified")
    if evidence.get("full_denominator") is not True or evidence.get("sampled") is not False:
        errors.append(f"{label}: reconciliation must be full-denominator and non-sampled")

    bundle_ref = evidence.get("source_bundle_ref")
    bundle_path = _safe_relative_file(evidence_path.parent, bundle_ref, f"{label}: source_bundle_ref", errors)
    bundle: dict[str, Any] = {}
    if bundle_path is not None:
        errors.extend(validate_bundle(bundle_path, require_production=require_production))
        try:
            bundle = load_json_object(bundle_path)
        except SourceEvidenceError:
            bundle = {}
        if evidence.get("source_bundle_manifest_sha256") != bundle.get("manifest_sha256"):
            errors.append(f"{label}: source bundle manifest digest does not match")
        if evidence.get("source_asset") != bundle.get("source", {}).get("asset"):
            errors.append(f"{label}: source asset differs from source bundle")

    coverage = evidence.get("coverage")
    if not isinstance(coverage, dict):
        errors.append(f"{label}: coverage must be an object")
        coverage = {}
    for key in (
        "source_row_count", "admitted_source_row_count", "quarantined_source_row_count",
        "missing_source_row_count", "duplicate_source_coverage_count", "tenant_count"
    ):
        if not _nonnegative_int(coverage.get(key)):
            errors.append(f"{label}: coverage.{key} must be a non-negative integer")
    if not _positive_int(coverage.get("source_row_count")):
        errors.append(f"{label}: coverage.source_row_count must be positive")
    if not _positive_int(coverage.get("tenant_count")):
        errors.append(f"{label}: coverage.tenant_count must be positive")
    if all(_nonnegative_int(coverage.get(key)) for key in (
        "source_row_count", "admitted_source_row_count", "quarantined_source_row_count"
    )) and coverage["source_row_count"] != (
        coverage["admitted_source_row_count"] + coverage["quarantined_source_row_count"]
    ):
        errors.append(f"{label}: admitted plus quarantined source rows must equal source denominator")
    if coverage.get("missing_source_row_count") != 0:
        errors.append(f"{label}: missing source rows must be zero")
    if coverage.get("duplicate_source_coverage_count") != 0:
        errors.append(f"{label}: duplicate source coverage must be zero")
    for key in ("source_business_key_sha256", "accounted_business_key_sha256"):
        if not _valid_sha256(coverage.get(key)):
            errors.append(f"{label}: coverage.{key} must be SHA-256")
    if coverage.get("source_business_key_sha256") != coverage.get("accounted_business_key_sha256"):
        errors.append(f"{label}: accounted business-key digest must equal source digest")
    if bundle:
        bundle_quality = bundle.get("quality", {})
        bundle_tenant = bundle.get("tenant_scope", {})
        if coverage.get("source_row_count") != bundle_quality.get("row_count"):
            errors.append(f"{label}: reconciliation source rows differ from source bundle")
        if coverage.get("tenant_count") != bundle_tenant.get("tenant_count"):
            errors.append(f"{label}: reconciliation tenant count differs from source bundle")
    if expected_row_count is not None and coverage.get("source_row_count") != expected_row_count:
        errors.append(f"{label}: source row count does not match disposition runtime")
    if expected_tenant_count is not None and coverage.get("tenant_count") != expected_tenant_count:
        errors.append(f"{label}: tenant count does not match disposition runtime")

    outputs = evidence.get("canonical_outputs")
    if not isinstance(outputs, list) or not outputs:
        errors.append(f"{label}: canonical_outputs must be non-empty")
    else:
        for index, output in enumerate(outputs):
            if not isinstance(output, dict) or not _nonempty_string(output.get("target")) or not _nonnegative_int(output.get("row_count")):
                errors.append(f"{label}: canonical_outputs[{index}] requires target and row_count")
    checks = evidence.get("semantic_checks")
    if not isinstance(checks, list) or not checks:
        errors.append(f"{label}: semantic_checks must be non-empty")
    else:
        seen_checks: set[str] = set()
        for index, check in enumerate(checks):
            check_label = f"{label}: semantic_checks[{index}]"
            if not isinstance(check, dict) or not _nonempty_string(check.get("name")):
                errors.append(f"{check_label}: name is required")
                continue
            if check["name"] in seen_checks:
                errors.append(f"{check_label}: duplicate check name")
            seen_checks.add(check["name"])
            if not _positive_int(check.get("checked_count")):
                errors.append(f"{check_label}: checked_count must be positive")
            if check.get("mismatch_count") != 0:
                errors.append(f"{check_label}: mismatch_count must be zero")

    trade_policy = _trade_admission_asset(evidence.get("source_asset"))
    if trade_policy is not None:
        output_targets = {
            output.get("target") for output in outputs or [] if isinstance(output, dict)
        }
        missing_targets = set(trade_policy.get("canonical_targets", [])) - output_targets
        if missing_targets:
            errors.append(f"{label}: Trade admission canonical outputs missing {sorted(missing_targets)}")
        check_names = {
            check.get("name") for check in checks or [] if isinstance(check, dict)
        }
        missing_checks = set(trade_policy.get("required_checks", [])) - check_names
        if missing_checks:
            errors.append(f"{label}: Trade admission semantic checks missing {sorted(missing_checks)}")

    verifier = evidence.get("independent_verifier")
    if not isinstance(verifier, dict):
        errors.append(f"{label}: independent_verifier must be an object")
    else:
        for key in ("engine", "code_ref"):
            if not _nonempty_string(verifier.get(key)):
                errors.append(f"{label}: independent_verifier.{key} is required")
        code_path = _safe_relative_file(
            evidence_path.parent,
            verifier.get("code_ref"),
            f"{label}: independent_verifier.code_ref",
            errors,
        )
        if not _valid_sha256(verifier.get("code_sha256")):
            errors.append(f"{label}: independent_verifier.code_sha256 must be SHA-256")
        elif code_path is not None and verifier["code_sha256"] != file_sha256(code_path):
            errors.append(f"{label}: independent_verifier.code_sha256 differs from code_ref")
        if not _valid_utc_timestamp(verifier.get("executed_at")):
            errors.append(f"{label}: independent_verifier.executed_at must be UTC")
        if verifier.get("independent_from_extractor") is not True:
            errors.append(f"{label}: verifier must be independent from the extractor")
        if verifier.get("independent_from_canonical_transform") is not True:
            errors.append(f"{label}: verifier must be independent from the canonical transform")
        bundle_query_sha = bundle.get("extraction", {}).get("query_sha256") if bundle else None
        if _valid_sha256(bundle_query_sha) and verifier.get("code_sha256") == bundle_query_sha:
            errors.append(f"{label}: verifier code must differ from the extraction query")
    authorization = evidence.get("authorization")
    if not isinstance(authorization, dict) or not all(
        isinstance(authorization.get(key), bool)
        for key in ("import_enabled", "cutover_enabled")
    ):
        errors.append(f"{label}: authorization must declare boolean import and cutover flags")

    metadata_policy: tuple[dict[str, Any], dict[str, Any]] | None = None
    try:
        metadata_policy = _metadata_runtime_policy(evidence.get("source_asset"))
    except SourceEvidenceError as exc:
        errors.append(f"{label}: {exc}")
    if metadata_policy is not None:
        policy, requirement = metadata_policy
        if bundle.get("source_environment") != "production":
            errors.append(f"{label}: Metadata runtime evidence requires production")
        if bundle.get("source", {}).get("qualified_table") != f"yshopping.{evidence.get('source_asset')}":
            errors.append(f"{label}: Metadata qualified source table differs")
        if not _positive_int(coverage.get("admitted_source_row_count")):
            errors.append(f"{label}: Metadata runtime evidence requires non-empty admitted rows")
        output_rows = {
            output.get("target"): output.get("row_count")
            for output in outputs or [] if isinstance(output, dict)
        }
        required_outputs = set(requirement.get("required_outputs") or [])
        missing_outputs = required_outputs - set(output_rows)
        if missing_outputs:
            errors.append(f"{label}: Metadata canonical outputs missing {sorted(missing_outputs)}")
        nonempty_output_failures = sorted(
            target for target in required_outputs
            if target in output_rows and not _positive_int(output_rows[target])
        )
        if nonempty_output_failures:
            errors.append(
                f"{label}: Metadata canonical outputs must be non-empty "
                f"{nonempty_output_failures}"
            )
        observed_checks = {
            check.get("name") for check in checks or [] if isinstance(check, dict)
        }
        required_checks = set(policy.get("common_required_checks") or []) | set(
            requirement.get("required_checks") or []
        )
        missing_checks = required_checks - observed_checks
        if missing_checks:
            errors.append(f"{label}: Metadata semantic checks missing {sorted(missing_checks)}")
        if authorization != policy.get("authorization"):
            errors.append(f"{label}: Metadata evidence cannot authorize import or cutover")
    return errors


def _prototype_ddl_columns(content: str, asset: str) -> list[tuple[str, str]]:
    escaped_asset = re.escape(asset)
    match = re.search(
        rf"CREATE\s+TABLE\s+`yshopping`\.`{escaped_asset}`\s*\((?P<body>.*?)^\s*\)"
        rf"(?P<tail>.*?)(?:```|\Z)",
        content,
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    if not match:
        return []
    columns: list[tuple[str, str]] = []
    for line in match.group("body").splitlines():
        column = re.match(
            r"^\s*`?(?P<name>[A-Za-z_][A-Za-z0-9_]*)`?\s+"
            r"(?P<type>[A-Za-z]+(?:\s*\([^)]*\))?)\b",
            line,
        )
        if column:
            columns.append(
                (column.group("name"), re.sub(r"\s+", "", column.group("type")).upper())
            )
    partition = re.search(
        r"PARTITIONED\s+BY\s*\(\s*`?(?P<name>[A-Za-z_][A-Za-z0-9_]*)`?\s+"
        r"(?P<type>[A-Za-z]+(?:\s*\([^)]*\))?)\b",
        match.group("tail"),
        flags=re.IGNORECASE,
    )
    if partition:
        columns.append(
            (partition.group("name"), re.sub(r"\s+", "", partition.group("type")).upper())
        )
    return columns


def validate_trade_admission(contract_path: Path, source_document: Path) -> list[str]:
    errors: list[str] = []
    try:
        contract = load_json_object(contract_path)
    except SourceEvidenceError as exc:
        return [str(exc)]
    label = str(contract_path)
    if contract.get("contract_id") != TRADE_ADMISSION_CONTRACT_ID:
        errors.append(f"{label}: contract_id must be {TRADE_ADMISSION_CONTRACT_ID}")
    if contract.get("status") != "pending_real_source_evidence":
        errors.append(f"{label}: status must remain pending_real_source_evidence until evidence is admitted")
    if "expected_row_count" in json.dumps(contract, ensure_ascii=False):
        errors.append(f"{label}: documentation volume estimates must not become expected_row_count")
    source_meta = contract.get("source_document")
    if not isinstance(source_meta, dict):
        errors.append(f"{label}: source_document must be an object")
        source_meta = {}
    try:
        source_bytes = source_document.read_bytes()
        source_content = source_bytes.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        return errors + [f"{label}: cannot read source document {source_document}: {exc}"]
    if source_meta.get("sha256") != hashlib.sha256(source_bytes).hexdigest():
        errors.append(f"{label}: source document digest drifted; admission policy requires review")
    if source_meta.get("row_volume_notes_are_denominators") is not False:
        errors.append(f"{label}: source row-volume notes must not be denominators")
    policy = contract.get("admission_policy")
    if not isinstance(policy, dict):
        errors.append(f"{label}: admission_policy must be an object")
        policy = {}
    required_policy = {
        "source_system": "YSHOPPING",
        "source_environment": "production",
        "extraction_mode": "READ_ONLY_SNAPSHOT",
        "full_denominator": True,
        "sampled": False,
    }
    for key, expected in required_policy.items():
        if policy.get(key) != expected:
            errors.append(f"{label}: admission_policy.{key} must be {expected!r}")
    if set(policy.get("runtime_credit_contracts", [])) != {
        BUNDLE_CONTRACT_ID, RECONCILIATION_CONTRACT_ID
    }:
        errors.append(f"{label}: runtime credit contracts must bind source bundle and reconciliation")
    for key in (
        "tenant_resolution", "partition_semantics", "deletion_semantics", "security",
        "activation_gate"
    ):
        if not _nonempty_string(policy.get(key)):
            errors.append(f"{label}: admission_policy.{key} is required")

    assets = contract.get("assets")
    expected_assets = {
        "ods_trade_trade_order_di",
        "ods_trade_trade_sub_order_di",
        "ods_trade_trade_discount_di",
    }
    if not isinstance(assets, list):
        return errors + [f"{label}: assets must be a list"]
    observed_assets = {
        asset.get("source_asset") for asset in assets if isinstance(asset, dict)
    }
    if observed_assets != expected_assets or len(assets) != len(expected_assets):
        errors.append(f"{label}: assets must contain exactly the first three Trade history sources")
    for index, asset in enumerate(assets):
        asset_label = f"{label}: assets[{index}]"
        if not isinstance(asset, dict):
            errors.append(f"{asset_label} must be an object")
            continue
        name = asset.get("source_asset")
        if not _nonempty_string(name):
            errors.append(f"{asset_label}: source_asset is required")
            continue
        if asset.get("qualified_table") != f"yshopping.{name}":
            errors.append(f"{asset_label}: qualified_table must retain the documented namespace")
        columns = asset.get("columns")
        declared_columns: list[tuple[str, str]] = []
        if not isinstance(columns, list) or not columns:
            errors.append(f"{asset_label}: columns must be non-empty")
        else:
            seen_columns: set[str] = set()
            for column_index, column in enumerate(columns):
                if not isinstance(column, dict):
                    errors.append(f"{asset_label}: columns[{column_index}] must be an object")
                    continue
                column_name = column.get("name")
                column_type = column.get("type")
                if not _nonempty_string(column_name) or not _nonempty_string(column_type):
                    errors.append(f"{asset_label}: columns[{column_index}] requires name and type")
                    continue
                if column_name in seen_columns:
                    errors.append(f"{asset_label}: duplicate column {column_name}")
                seen_columns.add(column_name)
                declared_columns.append((column_name, re.sub(r"\s+", "", column_type).upper()))
                if not _nonempty_string(column.get("role")):
                    errors.append(f"{asset_label}: column {column_name} requires a semantic role")
        documented_columns = _prototype_ddl_columns(source_content, name)
        if not documented_columns:
            errors.append(f"{asset_label}: documented DDL not found")
        elif declared_columns != documented_columns:
            errors.append(
                f"{asset_label}: declared columns/types differ from the locked prototype DDL: "
                f"declared={declared_columns!r}, documented={documented_columns!r}"
            )
        business_key = asset.get("business_key")
        if not isinstance(business_key, list) or not business_key or not set(business_key) <= {
            name for name, _ in declared_columns
        }:
            errors.append(f"{asset_label}: business_key must reference declared columns")
        for key in ("required_semantic_artifacts", "canonical_targets", "required_checks"):
            value = asset.get(key)
            if not isinstance(value, list) or not value or not all(_nonempty_string(item) for item in value):
                errors.append(f"{asset_label}: {key} must be a non-empty string list")
    checks = contract.get("cross_asset_checks")
    if not isinstance(checks, list) or len(checks) < 5 or not all(_nonempty_string(item) for item in checks):
        errors.append(f"{label}: cross_asset_checks must define the multi-table conservation gates")
    return errors


def runtime_reconciliation_errors(
    runtime: Any, *, expected_asset: str, resolve_reference
) -> list[str]:
    if not isinstance(runtime, dict):
        return ["runtime reconciliation must be an object"]
    if runtime.get("status") != "verified":
        return ["runtime reconciliation status is not verified"]
    evidence_ref = runtime.get("evidence_ref")
    if not _nonempty_string(evidence_ref):
        return ["runtime reconciliation evidence_ref is missing"]
    if not _nonempty_string(runtime.get("run_id")):
        return ["runtime reconciliation run_id is missing"]
    if not _positive_int(runtime.get("row_count")):
        return ["runtime reconciliation row_count must be positive"]
    if not _positive_int(runtime.get("tenant_count")):
        return ["runtime reconciliation tenant_count must be positive"]
    evidence_path = resolve_reference(evidence_ref)
    if not evidence_path.is_file() or evidence_path.stat().st_size == 0:
        return [f"runtime reconciliation evidence is missing or empty: {evidence_path}"]
    return validate_reconciliation(
        evidence_path,
        expected_asset=expected_asset,
        expected_run_id=runtime["run_id"],
        expected_row_count=runtime["row_count"],
        expected_tenant_count=runtime["tenant_count"],
        require_production=True,
    )
