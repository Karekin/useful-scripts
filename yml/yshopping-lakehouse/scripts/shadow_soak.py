"""Resumable local shadow/soak recorder.

Version 1 accepts caller-supplied timestamps and unsigned local files. It may
record a complete sequence, but it can never issue production credit. Trusted
production admission is performed by the separately signed production P4 gate.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_CONTRACT_ID = "cloudmold.yshopping.shadow-soak-state.v1"
ACCESS_CONTRACT_ID = "cloudmold.yshopping.shadow-soak-production-access.v1"
ROUND_CONTRACT_ID = "cloudmold.yshopping.shadow-soak-round.v1"
MIN_DURATION_SECONDS = 72 * 60 * 60
EXPECTED_ASSET_COUNT = 718


class ShadowSoakError(RuntimeError):
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


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ShadowSoakError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ShadowSoakError(f"{path}: root must be an object")
    return value


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    return parsed if parsed.utcoffset() == timezone.utc.utcoffset(parsed) else None


def _sha(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _uuid(value: Any) -> bool:
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return False
    return True


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    _atomic_bytes(
        path,
        (
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
    )


def _single_file_ref(base: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ShadowSoakError(f"{label} must be a file name")
    relative = Path(value)
    if relative.is_absolute() or len(relative.parts) != 1:
        raise ShadowSoakError(f"{label} must be a local file name")
    path = base / relative
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        raise ShadowSoakError(f"{label} must reference a non-empty regular file")
    return path


def _parse_gtid_set(value: Any) -> dict[str, list[tuple[int, int]]]:
    if not isinstance(value, str) or not value.strip():
        raise ShadowSoakError("GTID set must be non-empty")
    result: dict[str, list[tuple[int, int]]] = {}
    for server_set in value.split(","):
        parts = server_set.strip().split(":")
        if len(parts) < 2 or not _uuid(parts[0]):
            raise ShadowSoakError(f"invalid GTID server set: {server_set!r}")
        server = str(uuid.UUID(parts[0])).lower()
        if server in result:
            raise ShadowSoakError(f"duplicate GTID server UUID: {server}")
        intervals: list[tuple[int, int]] = []
        for raw_interval in parts[1:]:
            bounds = raw_interval.split("-")
            if len(bounds) not in {1, 2} or not all(item.isdigit() for item in bounds):
                raise ShadowSoakError(f"invalid GTID interval: {raw_interval!r}")
            start = int(bounds[0])
            end = int(bounds[-1])
            if start <= 0 or end < start:
                raise ShadowSoakError(f"invalid GTID interval: {raw_interval!r}")
            intervals.append((start, end))
        intervals.sort()
        for previous, current in zip(intervals, intervals[1:]):
            if current[0] <= previous[1]:
                raise ShadowSoakError(f"overlapping GTID intervals for {server}")
        result[server] = intervals
    return result


def _gtid_contains(container: Any, contained: Any) -> bool:
    outer = _parse_gtid_set(container)
    inner = _parse_gtid_set(contained)
    for server, intervals in inner.items():
        available = outer.get(server, [])
        for start, end in intervals:
            if not any(left <= start and right >= end for left, right in available):
                return False
    return True


def _validate_access(path: Path) -> dict[str, Any]:
    access = _load(path)
    errors: list[str] = []
    if access.get("contractId") != ACCESS_CONTRACT_ID:
        errors.append(f"contractId must be {ACCESS_CONTRACT_ID}")
    if access.get("sourceEnvironment") != "production":
        errors.append("sourceEnvironment must be production")
    if access.get("evidenceClass") != "PRODUCTION_OBSERVED":
        errors.append("evidenceClass must be PRODUCTION_OBSERVED")
    if access.get("fixture") is not False:
        errors.append("fixture must be false")
    for key in (
        "endpointId",
        "collectorIdentity",
        "collectorEnvironmentId",
        "identityProvider",
    ):
        if not isinstance(access.get(key), str) or not access[key].strip():
            errors.append(f"{key} is required")
    if access.get("readOnlyConfirmed") is not True:
        errors.append("readOnlyConfirmed must be true")
    audit_path: Path | None = None
    try:
        audit_path = _single_file_ref(path.parent, access.get("auditRef"), "auditRef")
    except ShadowSoakError as exc:
        errors.append(str(exc))
    if not _sha(access.get("auditSha256")):
        errors.append("auditSha256 must be SHA-256")
    elif audit_path is not None and file_sha256(audit_path) != access["auditSha256"]:
        errors.append("auditSha256 does not match auditRef")
    if access.get("accessSha256") != canonical_sha256(access, "accessSha256"):
        errors.append("accessSha256 does not match canonical access manifest")
    if errors:
        raise ShadowSoakError("; ".join(errors))
    return access


def _state_path(state_dir: Path) -> Path:
    return state_dir / "state.json"


def _write_state(state_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    state["stateSha256"] = canonical_sha256(state, "stateSha256")
    _atomic_json(_state_path(state_dir), state)
    return state


def _verify_persisted_artifacts(state_dir: Path, state: dict[str, Any]) -> None:
    production_access = state.get("productionAccess")
    if production_access is None:
        if state.get("status") != "BLOCKED" or state.get("rounds"):
            raise ShadowSoakError("missing production access is valid only for an empty BLOCKED window")
    else:
        access_path = state_dir / production_access["manifestRef"]
        if (
            not access_path.is_file()
            or file_sha256(access_path) != production_access["manifestFileSha256"]
        ):
            raise ShadowSoakError("persisted production access manifest is missing or tampered")
        _validate_access(access_path)
    for recorded in state.get("rounds", []):
        round_path = state_dir / recorded["artifactRef"]
        if not round_path.is_file() or file_sha256(round_path) != recorded["artifactSha256"]:
            raise ShadowSoakError(
                f"persisted round {recorded.get('sequence')} is missing or tampered"
            )
        round_value = _load(round_path)
        if round_value.get("roundSha256") != canonical_sha256(
            round_value, "roundSha256"
        ):
            raise ShadowSoakError(
                f"persisted round {recorded.get('sequence')} canonical digest is invalid"
            )
        verifier = round_value.get("independentVerifier")
        if not isinstance(verifier, dict):
            raise ShadowSoakError(
                f"persisted round {recorded.get('sequence')} verifier is missing"
            )
        for ref_key, digest_key in (
            ("codeRef", "codeSha256"),
            ("attestationRef", "attestationSha256"),
        ):
            referenced = _single_file_ref(
                round_path.parent,
                verifier.get(ref_key),
                f"persisted round {recorded.get('sequence')} verifier {ref_key}",
            )
            if (
                not _sha(verifier.get(digest_key))
                or file_sha256(referenced) != verifier[digest_key]
            ):
                raise ShadowSoakError(
                    f"persisted round {recorded.get('sequence')} verifier evidence is tampered"
                )
        if (
            recorded.get("verifierCodeSha256") != verifier.get("codeSha256")
            or recorded.get("verifierAttestationSha256")
            != verifier.get("attestationSha256")
        ):
            raise ShadowSoakError(
                f"persisted round {recorded.get('sequence')} verifier digest differs from state"
            )
    rejected = state.get("rejectedRound")
    if isinstance(rejected, dict):
        rejected_path = state_dir / rejected.get("artifactRef", "")
        if (
            not rejected_path.is_file()
            or file_sha256(rejected_path) != rejected.get("artifactSha256")
        ):
            raise ShadowSoakError("persisted rejected round is missing or tampered")


def load_state(state_dir: Path) -> dict[str, Any]:
    state = _load(_state_path(state_dir))
    if state.get("contractId") != STATE_CONTRACT_ID:
        raise ShadowSoakError("invalid shadow/soak state contract")
    if state.get("stateSha256") != canonical_sha256(state, "stateSha256"):
        raise ShadowSoakError("stateSha256 does not match canonical state")
    _verify_persisted_artifacts(state_dir, state)
    return state


def open_window(
    state_dir: Path,
    *,
    window_id: str,
    opened_at: str,
    expected_asset_names_sha256: str,
    access_manifest: Path | None,
    max_gap_seconds: int = 6 * 60 * 60,
    max_lag_seconds: int = 300,
    max_freshness_seconds: int = 600,
    required_round_count: int = 12,
) -> dict[str, Any]:
    if _state_path(state_dir).exists():
        existing = load_state(state_dir)
        requested_policy = {
            "minimumDurationSeconds": MIN_DURATION_SECONDS,
            "requiredRoundCount": required_round_count,
            "maxGapSeconds": max_gap_seconds,
            "maxLagSeconds": max_lag_seconds,
            "maxFreshnessSeconds": max_freshness_seconds,
            "expectedAssetCount": EXPECTED_ASSET_COUNT,
            "expectedAssetNamesSha256": expected_asset_names_sha256,
        }
        if (
            existing.get("windowId") != window_id
            or existing.get("openedAt") != opened_at
            or existing.get("policy") != requested_policy
        ):
            raise ShadowSoakError(
                "existing window is immutable and differs from the requested window"
            )
        if access_manifest is not None:
            requested_access = _validate_access(access_manifest)
            persisted_access = existing.get("productionAccess")
            if (
                not isinstance(persisted_access, dict)
                or persisted_access.get("endpointId") != requested_access.get("endpointId")
                or persisted_access.get("collectorIdentity")
                != requested_access.get("collectorIdentity")
                or persisted_access.get("collectorEnvironmentId")
                != requested_access.get("collectorEnvironmentId")
            ):
                raise ShadowSoakError(
                    "existing production access identity differs from the request"
                )
        return existing
    if not _uuid(window_id) or _utc(opened_at) is None:
        raise ShadowSoakError("window_id must be UUID and opened_at must be UTC")
    if not _sha(expected_asset_names_sha256):
        raise ShadowSoakError("expected_asset_names_sha256 must be SHA-256")
    for label, value in (
        ("max_gap_seconds", max_gap_seconds),
        ("max_lag_seconds", max_lag_seconds),
        ("max_freshness_seconds", max_freshness_seconds),
        ("required_round_count", required_round_count),
    ):
        if not _positive_int(value):
            raise ShadowSoakError(f"{label} must be positive")
    state_dir.mkdir(parents=True, exist_ok=True)
    if access_manifest is None:
        state = {
            "contractId": STATE_CONTRACT_ID,
            "windowId": window_id,
            "status": "BLOCKED",
            "openedAt": opened_at,
            "policy": {
                "minimumDurationSeconds": MIN_DURATION_SECONDS,
                "requiredRoundCount": required_round_count,
                "maxGapSeconds": max_gap_seconds,
                "maxLagSeconds": max_lag_seconds,
                "maxFreshnessSeconds": max_freshness_seconds,
                "expectedAssetCount": EXPECTED_ASSET_COUNT,
                "expectedAssetNamesSha256": expected_asset_names_sha256,
            },
            "productionAccess": None,
            "rounds": [],
            "verifierEvidenceSha256": hashlib.sha256(b"").hexdigest(),
            "blockers": ["production access manifest is required"],
            "authorization": {"importEnabled": False, "cutoverEnabled": False},
            "productionCredit": False,
            "trust": {
                "timeSource": "CALLER_SUPPLIED_UNTRUSTED",
                "signatureVerified": False,
            },
        }
        return _write_state(state_dir, state)

    access = _validate_access(access_manifest)
    access_dir = state_dir / "access"
    audit_source = _single_file_ref(
        access_manifest.parent, access["auditRef"], "auditRef"
    )
    _atomic_bytes(access_dir / access["auditRef"], audit_source.read_bytes())
    _atomic_bytes(access_dir / "manifest.json", access_manifest.read_bytes())
    persisted_access = access_dir / "manifest.json"
    state = {
        "contractId": STATE_CONTRACT_ID,
        "windowId": window_id,
        "status": "OPEN",
        "openedAt": opened_at,
        "policy": {
            "minimumDurationSeconds": MIN_DURATION_SECONDS,
            "requiredRoundCount": required_round_count,
            "maxGapSeconds": max_gap_seconds,
            "maxLagSeconds": max_lag_seconds,
            "maxFreshnessSeconds": max_freshness_seconds,
            "expectedAssetCount": EXPECTED_ASSET_COUNT,
            "expectedAssetNamesSha256": expected_asset_names_sha256,
        },
        "productionAccess": {
            "manifestRef": "access/manifest.json",
            "manifestFileSha256": file_sha256(persisted_access),
            "endpointId": access["endpointId"],
            "collectorIdentity": access["collectorIdentity"],
            "collectorEnvironmentId": access["collectorEnvironmentId"],
        },
        "rounds": [],
        "verifierEvidenceSha256": hashlib.sha256(b"").hexdigest(),
        "blockers": [],
        "authorization": {"importEnabled": False, "cutoverEnabled": False},
        "productionCredit": False,
        "trust": {
            "timeSource": "CALLER_SUPPLIED_UNTRUSTED",
            "signatureVerified": False,
        },
    }
    return _write_state(state_dir, state)


def _validate_round(
    state: dict[str, Any], round_path: Path
) -> tuple[dict[str, Any], list[str]]:
    round_value = _load(round_path)
    errors: list[str] = []
    if round_value.get("contractId") != ROUND_CONTRACT_ID:
        errors.append(f"contractId must be {ROUND_CONTRACT_ID}")
    if not _uuid(round_value.get("roundId")):
        errors.append("roundId must be UUID")
    if round_value.get("windowId") != state["windowId"]:
        errors.append("windowId differs from open window")
    expected_sequence = len(state["rounds"]) + 1
    if round_value.get("sequence") != expected_sequence:
        errors.append(f"sequence must be {expected_sequence}")
    if round_value.get("sourceEnvironment") != "production":
        errors.append("sourceEnvironment must be production")
    if round_value.get("evidenceClass") != "PRODUCTION_OBSERVED":
        errors.append("evidenceClass must be PRODUCTION_OBSERVED")
    if round_value.get("fixture") is not False:
        errors.append("fixture must be false")
    if round_value.get("roundSha256") != canonical_sha256(
        round_value, "roundSha256"
    ):
        errors.append("roundSha256 does not match canonical round")

    observed_at = _utc(round_value.get("observedAt"))
    opened_at = _utc(state["openedAt"])
    previous_at = (
        _utc(state["rounds"][-1]["observedAt"]) if state["rounds"] else opened_at
    )
    if observed_at is None:
        errors.append("observedAt must be UTC")
    elif previous_at is not None:
        gap = (observed_at - previous_at).total_seconds()
        if gap <= 0:
            errors.append("observedAt must increase")
        if gap > state["policy"]["maxGapSeconds"]:
            errors.append("observation gap exceeds maxGapSeconds")

    denominator = round_value.get("denominator")
    denominator = denominator if isinstance(denominator, dict) else {}
    if denominator.get("expectedAssetCount") != EXPECTED_ASSET_COUNT:
        errors.append(f"expectedAssetCount must be {EXPECTED_ASSET_COUNT}")
    if denominator.get("observedAssetCount") != EXPECTED_ASSET_COUNT:
        errors.append("observedAssetCount must cover the complete denominator")
    expected_hash = state["policy"]["expectedAssetNamesSha256"]
    if denominator.get("expectedAssetNamesSha256") != expected_hash:
        errors.append("expected asset denominator hash drifted")
    if denominator.get("observedAssetNamesSha256") != expected_hash:
        errors.append("observed asset denominator hash is incomplete")

    watermark = round_value.get("watermark")
    watermark = watermark if isinstance(watermark, dict) else {}
    if watermark.get("kind") != "MYSQL_GTID_SET":
        errors.append("watermark.kind must be MYSQL_GTID_SET")
    source_gtid = watermark.get("sourceGtidSet")
    target_gtid = watermark.get("targetGtidSet")
    try:
        if not _gtid_contains(target_gtid, source_gtid):
            errors.append("target GTID set does not contain source GTID set")
        if state["rounds"]:
            previous = state["rounds"][-1]
            if not _gtid_contains(source_gtid, previous["sourceGtidSet"]):
                errors.append("source GTID watermark regressed")
            elif _gtid_contains(previous["sourceGtidSet"], source_gtid):
                errors.append("source GTID watermark is stale")
            if not _gtid_contains(target_gtid, previous["targetGtidSet"]):
                errors.append("target GTID watermark regressed")
            elif _gtid_contains(previous["targetGtidSet"], target_gtid):
                errors.append("target GTID watermark is stale")
    except ShadowSoakError as exc:
        errors.append(str(exc))

    health = round_value.get("health")
    health = health if isinstance(health, dict) else {}
    for key, maximum in (
        ("lagSeconds", state["policy"]["maxLagSeconds"]),
        ("freshnessSeconds", state["policy"]["maxFreshnessSeconds"]),
    ):
        if not _nonnegative_int(health.get(key)):
            errors.append(f"health.{key} must be non-negative")
        elif health[key] > maximum:
            errors.append(f"health.{key} exceeds policy")

    comparison = round_value.get("comparison")
    comparison = comparison if isinstance(comparison, dict) else {}
    for key in ("rowCountDifference", "quantityDifference", "amountMinorDifference"):
        if comparison.get(key) != 0:
            errors.append(f"comparison.{key} must be zero")
    for source_key, target_key in (
        ("sourceQuantitySha256", "targetQuantitySha256"),
        ("sourceAmountSha256", "targetAmountSha256"),
        ("sourceContentSha256", "targetContentSha256"),
    ):
        if not _sha(comparison.get(source_key)) or not _sha(comparison.get(target_key)):
            errors.append(f"comparison {source_key}/{target_key} must be SHA-256")
        elif comparison[source_key] != comparison[target_key]:
            errors.append(f"comparison {source_key}/{target_key} differ")

    verifier = round_value.get("independentVerifier")
    verifier = verifier if isinstance(verifier, dict) else {}
    access = state.get("productionAccess") or {}
    for key in ("identity", "environmentId", "engine"):
        if not isinstance(verifier.get(key), str) or not verifier[key].strip():
            errors.append(f"independentVerifier.{key} is required")
    if verifier.get("identity") == access.get("collectorIdentity"):
        errors.append("independent verifier identity must differ from collector")
    if verifier.get("environmentId") == access.get("collectorEnvironmentId"):
        errors.append("independent verifier environment must differ from collector")
    for ref_key, digest_key in (
        ("codeRef", "codeSha256"),
        ("attestationRef", "attestationSha256"),
    ):
        referenced: Path | None = None
        try:
            referenced = _single_file_ref(
                round_path.parent, verifier.get(ref_key), f"independentVerifier.{ref_key}"
            )
        except ShadowSoakError as exc:
            errors.append(str(exc))
        if not _sha(verifier.get(digest_key)):
            errors.append(f"independentVerifier.{digest_key} must be SHA-256")
        elif referenced is not None and file_sha256(referenced) != verifier[digest_key]:
            errors.append(f"independentVerifier.{digest_key} does not match {ref_key}")
    executed_at = _utc(verifier.get("executedAt"))
    if executed_at is None:
        errors.append("independentVerifier.executedAt must be UTC")
    elif observed_at is not None and executed_at < observed_at:
        errors.append("independent verification predates observation")
    return round_value, errors


def observe_round(state_dir: Path, round_path: Path) -> dict[str, Any]:
    state = load_state(state_dir)
    if state["status"] not in {"OPEN", "OBSERVING"}:
        raise ShadowSoakError(f"cannot observe a round from {state['status']} state")
    sequence = len(state["rounds"]) + 1
    artifact_dir = state_dir / "rounds" / f"{sequence:04d}"
    try:
        round_value, errors = _validate_round(state, round_path)
    except ShadowSoakError as exc:
        artifact_path = artifact_dir / "rejected.json"
        rejection = {
            "result": "INVALID",
            "inputPath": str(round_path),
            "error": str(exc),
        }
        _atomic_json(artifact_path, rejection)
        state["status"] = "BLOCKED"
        state["blockers"] = [str(exc)]
        state["rejectedRound"] = {
            "sequence": sequence,
            "artifactRef": str(artifact_path.relative_to(state_dir)),
            "artifactSha256": file_sha256(artifact_path),
            "result": "INVALID",
        }
        return _write_state(state_dir, state)
    verifier = round_value.get("independentVerifier")
    verifier = verifier if isinstance(verifier, dict) else {}
    for ref_key in ("codeRef", "attestationRef"):
        try:
            source = _single_file_ref(
                round_path.parent, verifier.get(ref_key), f"independentVerifier.{ref_key}"
            )
        except ShadowSoakError:
            continue
        _atomic_bytes(artifact_dir / source.name, source.read_bytes())
    artifact_path = artifact_dir / "round.json"
    _atomic_bytes(artifact_path, round_path.read_bytes())

    if errors:
        state["status"] = "BLOCKED"
        state["blockers"] = sorted(set(errors))
        state["rejectedRound"] = {
            "sequence": sequence,
            "artifactRef": str(artifact_path.relative_to(state_dir)),
            "artifactSha256": file_sha256(artifact_path),
            "result": "INVALID",
        }
        return _write_state(state_dir, state)

    record = {
        "sequence": sequence,
        "roundId": round_value["roundId"],
        "observedAt": round_value["observedAt"],
        "sourceGtidSet": round_value["watermark"]["sourceGtidSet"],
        "targetGtidSet": round_value["watermark"]["targetGtidSet"],
        "artifactRef": str(artifact_path.relative_to(state_dir)),
        "artifactSha256": file_sha256(artifact_path),
        "result": "MATCH",
        "verifierIdentity": verifier["identity"],
        "verifierCodeSha256": verifier["codeSha256"],
        "verifierAttestationSha256": verifier["attestationSha256"],
    }
    state["rounds"].append(record)
    verifier_chain = [
        {
            "sequence": item["sequence"],
            "identity": item["verifierIdentity"],
            "codeSha256": item["verifierCodeSha256"],
            "attestationSha256": item["verifierAttestationSha256"],
        }
        for item in state["rounds"]
    ]
    state["verifierEvidenceSha256"] = hashlib.sha256(
        json.dumps(
            verifier_chain, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    opened_at = _utc(state["openedAt"])
    observed_at = _utc(record["observedAt"])
    duration = int((observed_at - opened_at).total_seconds())
    state["observedDurationSeconds"] = duration
    if (
        duration >= state["policy"]["minimumDurationSeconds"]
        and len(state["rounds"]) >= state["policy"]["requiredRoundCount"]
    ):
        state["status"] = "LOCAL_SEQUENCE_COMPLETE_UNTRUSTED"
    else:
        state["status"] = "OBSERVING"
    state["authorization"] = {"importEnabled": False, "cutoverEnabled": False}
    state["productionCredit"] = False
    return _write_state(state_dir, state)
