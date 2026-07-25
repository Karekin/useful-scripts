from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from shadow_soak import (
    ACCESS_CONTRACT_ID,
    EXPECTED_ASSET_COUNT,
    ROUND_CONTRACT_ID,
    ShadowSoakError,
    canonical_sha256,
    load_state,
    observe_round,
    open_window,
)


SERVER_ID = "3e11fa47-71ca-11e1-9e33-c80aa9429562"
OPENED_AT = datetime(2026, 7, 25, 0, 0, tzinfo=timezone.utc)
ASSET_HASH = hashlib.sha256(b"718-governed-assets").hexdigest()
MATCH_HASH = hashlib.sha256(b"matched").hexdigest()


def _utc(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _access(directory: Path) -> Path:
    audit = directory / "access-audit.json"
    audit.write_text('{"principal":"shadow-collector-prod"}\n', encoding="utf-8")
    value = {
        "contractId": ACCESS_CONTRACT_ID,
        "sourceEnvironment": "production",
        "evidenceClass": "PRODUCTION_OBSERVED",
        "fixture": False,
        "endpointId": "yshopping-prod-ro",
        "collectorIdentity": "shadow-collector-prod",
        "collectorEnvironmentId": "collector-host-prod",
        "identityProvider": "production-iam",
        "readOnlyConfirmed": True,
        "auditRef": audit.name,
        "auditSha256": _file_sha(audit),
    }
    value["accessSha256"] = canonical_sha256(value, "accessSha256")
    path = directory / "access.json"
    _write_json(path, value)
    return path


def _round(
    directory: Path,
    *,
    window_id: str,
    sequence: int,
    observed_at: datetime,
    source_end: int | None = None,
    target_end: int | None = None,
) -> Path:
    source_end = source_end if source_end is not None else sequence * 10
    target_end = target_end if target_end is not None else source_end + 5
    code = directory / "verify.sql"
    code.write_text("SELECT mismatch_count FROM independent_diff\n", encoding="utf-8")
    attestation = directory / "verify-attestation.json"
    attestation.write_text(
        json.dumps({"sequence": sequence, "identity": "shadow-verifier-prod"}),
        encoding="utf-8",
    )
    value = {
        "contractId": ROUND_CONTRACT_ID,
        "roundId": str(uuid.uuid4()),
        "windowId": window_id,
        "sequence": sequence,
        "observedAt": _utc(observed_at),
        "sourceEnvironment": "production",
        "evidenceClass": "PRODUCTION_OBSERVED",
        "fixture": False,
        "denominator": {
            "expectedAssetCount": EXPECTED_ASSET_COUNT,
            "observedAssetCount": EXPECTED_ASSET_COUNT,
            "expectedAssetNamesSha256": ASSET_HASH,
            "observedAssetNamesSha256": ASSET_HASH,
        },
        "watermark": {
            "kind": "MYSQL_GTID_SET",
            "sourceGtidSet": f"{SERVER_ID}:1-{source_end}",
            "targetGtidSet": f"{SERVER_ID}:1-{target_end}",
        },
        "health": {"lagSeconds": 10, "freshnessSeconds": 20},
        "comparison": {
            "rowCountDifference": 0,
            "quantityDifference": 0,
            "amountMinorDifference": 0,
            "sourceQuantitySha256": MATCH_HASH,
            "targetQuantitySha256": MATCH_HASH,
            "sourceAmountSha256": MATCH_HASH,
            "targetAmountSha256": MATCH_HASH,
            "sourceContentSha256": MATCH_HASH,
            "targetContentSha256": MATCH_HASH,
        },
        "independentVerifier": {
            "identity": "shadow-verifier-prod",
            "environmentId": "verifier-host-prod",
            "engine": "independent-sql-engine",
            "codeRef": code.name,
            "codeSha256": _file_sha(code),
            "attestationRef": attestation.name,
            "attestationSha256": _file_sha(attestation),
            "executedAt": _utc(observed_at + timedelta(minutes=1)),
        },
    }
    value["roundSha256"] = canonical_sha256(value, "roundSha256")
    path = directory / "round-input.json"
    _write_json(path, value)
    return path


def _mutate_round(path: Path, mutation) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    mutation(value)
    value["roundSha256"] = canonical_sha256(value, "roundSha256")
    _write_json(path, value)


def _open(root: Path, *, access: bool = True, max_gap: int = 21600) -> tuple[Path, str]:
    state_dir = root / "state"
    window_id = str(uuid.uuid4())
    open_window(
        state_dir,
        window_id=window_id,
        opened_at=_utc(OPENED_AT),
        expected_asset_names_sha256=ASSET_HASH,
        access_manifest=_access(root) if access else None,
        max_gap_seconds=max_gap,
    )
    return state_dir, window_id


class ShadowSoakTest(unittest.TestCase):
    def test_no_production_access_is_blocked_and_never_authorizes(self):
        with tempfile.TemporaryDirectory() as raw:
            state_dir, _ = _open(Path(raw), access=False)
            state = load_state(state_dir)
            self.assertEqual("BLOCKED", state["status"])
            self.assertEqual([], state["rounds"])
            self.assertFalse(state["authorization"]["cutoverEnabled"])

    def test_resumes_after_restart_but_unsigned_time_never_gets_production_credit(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state_dir, window_id = _open(root)
            for sequence in range(1, 13):
                path = _round(
                    root,
                    window_id=window_id,
                    sequence=sequence,
                    observed_at=OPENED_AT + timedelta(hours=6 * sequence),
                )
                state = observe_round(state_dir, path)
                state = load_state(state_dir)
            self.assertEqual("LOCAL_SEQUENCE_COMPLETE_UNTRUSTED", state["status"])
            self.assertEqual(12, len(state["rounds"]))
            self.assertEqual(72 * 60 * 60, state["observedDurationSeconds"])
            self.assertTrue(all(item["result"] == "MATCH" for item in state["rounds"]))
            self.assertFalse(state["authorization"]["importEnabled"])
            self.assertFalse(state["productionCredit"])
            self.assertFalse(state["trust"]["signatureVerified"])
            self.assertEqual(64, len(state["verifierEvidenceSha256"]))

    def test_under_72_hours_remains_observing(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state_dir, window_id = _open(root)
            state = observe_round(
                state_dir,
                _round(
                    root,
                    window_id=window_id,
                    sequence=1,
                    observed_at=OPENED_AT + timedelta(hours=6),
                ),
            )
            self.assertEqual("OBSERVING", state["status"])
            self.assertNotEqual("LOCAL_SEQUENCE_COMPLETE_UNTRUSTED", state["status"])

    def test_stream_gap_blocks_window_and_rejected_round_is_never_match(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state_dir, window_id = _open(root, max_gap=3600)
            state = observe_round(
                state_dir,
                _round(
                    root,
                    window_id=window_id,
                    sequence=1,
                    observed_at=OPENED_AT + timedelta(hours=2),
                ),
            )
            self.assertEqual("BLOCKED", state["status"])
            self.assertEqual("INVALID", state["rejectedRound"]["result"])
            self.assertEqual([], state["rounds"])

    def test_stale_watermark_blocks_window(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state_dir, window_id = _open(root)
            observe_round(
                state_dir,
                _round(
                    root,
                    window_id=window_id,
                    sequence=1,
                    observed_at=OPENED_AT + timedelta(hours=1),
                    source_end=10,
                    target_end=20,
                ),
            )
            state = observe_round(
                state_dir,
                _round(
                    root,
                    window_id=window_id,
                    sequence=2,
                    observed_at=OPENED_AT + timedelta(hours=2),
                    source_end=10,
                    target_end=20,
                ),
            )
            self.assertEqual("BLOCKED", state["status"])
            self.assertTrue(any("stale" in item for item in state["blockers"]))

    def test_lag_freshness_denominator_and_differences_fail_closed(self):
        mutations = (
            lambda value: value["health"].update(lagSeconds=301),
            lambda value: value["health"].update(freshnessSeconds=601),
            lambda value: value["denominator"].update(observedAssetCount=717),
            lambda value: value["comparison"].update(quantityDifference=1),
            lambda value: value["comparison"].update(amountMinorDifference=1),
            lambda value: value["comparison"].update(
                targetContentSha256=hashlib.sha256(b"different").hexdigest()
            ),
            lambda value: value["independentVerifier"].update(
                identity="shadow-collector-prod"
            ),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                state_dir, window_id = _open(root)
                path = _round(
                    root,
                    window_id=window_id,
                    sequence=1,
                    observed_at=OPENED_AT + timedelta(hours=1),
                )
                _mutate_round(path, mutation)
                state = observe_round(state_dir, path)
                self.assertEqual("BLOCKED", state["status"])
                self.assertEqual([], state["rounds"])
                self.assertEqual("INVALID", state["rejectedRound"]["result"])

    def test_state_and_round_artifact_tampering_are_detected(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state_dir, window_id = _open(root)
            state = observe_round(
                state_dir,
                _round(
                    root,
                    window_id=window_id,
                    sequence=1,
                    observed_at=OPENED_AT + timedelta(hours=1),
                ),
            )
            state_path = state_dir / "state.json"
            state_value = json.loads(state_path.read_text(encoding="utf-8"))
            state_value["status"] = "VERIFIED"
            _write_json(state_path, state_value)
            with self.assertRaisesRegex(ShadowSoakError, "stateSha256"):
                load_state(state_dir)

            state_value["status"] = state["status"]
            state_value["stateSha256"] = canonical_sha256(
                state_value, "stateSha256"
            )
            _write_json(state_path, state_value)
            artifact = state_dir / state["rounds"][0]["artifactRef"]
            artifact.write_text('{"tampered":true}\n', encoding="utf-8")
            with self.assertRaisesRegex(ShadowSoakError, "tampered"):
                load_state(state_dir)

    def test_independent_verifier_artifact_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state_dir, window_id = _open(root)
            state = observe_round(
                state_dir,
                _round(
                    root,
                    window_id=window_id,
                    sequence=1,
                    observed_at=OPENED_AT + timedelta(hours=1),
                ),
            )
            round_artifact = state_dir / state["rounds"][0]["artifactRef"]
            verifier_code = round_artifact.parent / "verify.sql"
            verifier_code.write_text("SELECT forged_match\n", encoding="utf-8")
            with self.assertRaisesRegex(ShadowSoakError, "verifier evidence is tampered"):
                load_state(state_dir)

    def test_empty_round_input_never_creates_match(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state_dir, _ = _open(root)
            empty = root / "empty.json"
            empty.write_text("", encoding="utf-8")
            state = observe_round(state_dir, empty)
            self.assertEqual("BLOCKED", state["status"])
            self.assertEqual("INVALID", state["rejectedRound"]["result"])
            self.assertEqual([], state["rounds"])


if __name__ == "__main__":
    unittest.main()
