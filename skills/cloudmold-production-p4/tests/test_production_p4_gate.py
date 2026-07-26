from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "production_p4_gate.py"
)
SPEC = importlib.util.spec_from_file_location("production_p4_gate", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

CHECKED_AT = "2026-07-25T12:00:00Z"
OBSERVED_AT = "2026-07-25T10:00:00Z"
VERIFIED_AT = "2026-07-25T11:00:00Z"
RETENTION_UNTIL = "2033-07-25T12:00:00Z"


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _signed_manifest(root: Path) -> tuple[Path, Path]:
    private_key = root / "private.pem"
    public_key = root / "public.pem"
    storage_private_key = root / "storage-private.pem"
    storage_public_key = root / "storage-public.pem"
    subprocess.run(
        ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private_key)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            "openssl",
            "genpkey",
            "-algorithm",
            "RSA",
            "-pkeyopt",
            "rsa_keygen_bits:2048",
            "-out",
            str(storage_private_key),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            "openssl",
            "pkey",
            "-in",
            str(storage_private_key),
            "-pubout",
            "-out",
            str(storage_public_key),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    access = root / "collector-access.json"
    access.write_text('{"audit":"production-read-only"}\n', encoding="utf-8")
    verifier_attestation = root / "verifier-attestation.json"
    verifier_attestation.write_text('{"verifier":"independent"}\n', encoding="utf-8")
    artifact = root / "gate-evidence.json"
    artifact.write_text('{"source":"production-observation"}\n', encoding="utf-8")

    registry = json.loads(MODULE.DEFAULT_GATES.read_text(encoding="utf-8"))
    gates = []
    for requirement in registry["gates"]:
        gate_id = requirement["gate_id"]
        immutable_attestation = {
            "contract_id": MODULE.IMMUTABLE_ATTESTATION_ID,
            "attestor_id": "oss-control-plane-key",
            "provider": "ALIBABA_CLOUD_OSS_WORM",
            "production_account_id": "cloudmold-prod",
            "region": "cn-hangzhou",
            "bucket": "cloudmold-prod-evidence",
            "object_key": f"production-p4/{gate_id}.json",
            "version_id": "immutable-version-1",
            "etag": "example-production-etag",
            "artifact_sha256": _sha(artifact),
            "retention_until": RETENTION_UNTIL,
            "issued_at": VERIFIED_AT,
        }
        attestation_path = root / f"{gate_id}.storage-attestation.json"
        _write_json(attestation_path, immutable_attestation)
        attestation_signature = root / f"{gate_id}.storage-attestation.sig"
        subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-sign",
                str(storage_private_key),
                "-out",
                str(attestation_signature),
            ],
            input=MODULE._canonical(immutable_attestation),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        gates.append(
            {
                "gate_id": gate_id,
                "evidence_class": "PRODUCTION_OBSERVED",
                "fixture": False,
                "observed_at": OBSERVED_AT,
                "artifact_ref": artifact.name,
                "artifact_sha256": _sha(artifact),
                "immutable_source": {
                    "provider": "ALIBABA_CLOUD_OSS_WORM",
                    "bucket": "cloudmold-prod-evidence",
                    "object_key": f"production-p4/{gate_id}.json",
                    "version_id": "immutable-version-1",
                    "etag": "example-production-etag",
                    "retention_until": RETENTION_UNTIL,
                    "attestor_id": "oss-control-plane-key",
                    "attestation_ref": attestation_path.name,
                    "attestation_sha256": _sha(attestation_path),
                    "attestation_signature_ref": attestation_signature.name,
                    "attestation_signature_sha256": _sha(attestation_signature),
                },
                "assertions": dict(requirement.get("required_assertions", {})),
                "measurements": dict(requirement.get("minimum_measurements", {})),
                "independent_verifier": {
                    "identity": "prod-verifier",
                    "environment_id": "prod-verifier-runtime",
                    "executed_at": VERIFIED_AT,
                    "attestation_ref": verifier_attestation.name,
                    "attestation_sha256": _sha(verifier_attestation),
                },
            }
        )
    manifest = {
        "contract_id": MODULE.CONTRACT_ID,
        "run_id": "prod-p4-20260725",
        "environment": "production",
        "production_account_id": "cloudmold-prod",
        "region": "cn-hangzhou",
        "source_commit": "a" * 40,
        "image_digest": "sha256:" + "b" * 64,
        "deployment_revision": "prod-revision-1",
        "collected_at": OBSERVED_AT,
        "collector": {
            "identity": "prod-collector",
            "environment_id": "prod-collector-runtime",
            "access_attestation_ref": access.name,
            "access_attestation_sha256": _sha(access),
        },
        "signer_id": "release-kms-key",
        "gates": gates,
    }
    canonical = MODULE._canonical(
        manifest, {"manifest_sha256", "signature_ref", "signature_sha256"}
    )
    manifest["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    signature = root / "manifest.sig"
    subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", str(private_key), "-out", str(signature)],
        input=canonical,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    manifest["signature_ref"] = signature.name
    manifest["signature_sha256"] = _sha(signature)
    manifest_path = root / "manifest.json"
    _write_json(manifest_path, manifest)
    trust = {
        "contract_id": MODULE.TRUST_ID,
        "policy_status": "ACTIVE",
        "signers": [
            {
                "signer_id": "release-kms-key",
                "provider": "ALIBABA_CLOUD_KMS_ASYMMETRIC",
                "public_key_ref": public_key.name,
                "public_key_sha256": _sha(public_key),
                "allowed_production_accounts": ["cloudmold-prod"],
                "allowed_regions": ["cn-hangzhou"],
            }
        ],
        "storage_attestors": [
            {
                "attestor_id": "oss-control-plane-key",
                "provider": "ALIBABA_CLOUD_KMS_ASYMMETRIC",
                "public_key_ref": storage_public_key.name,
                "public_key_sha256": _sha(storage_public_key),
                "allowed_production_accounts": ["cloudmold-prod"],
                "allowed_regions": ["cn-hangzhou"],
                "allowed_immutable_providers": ["ALIBABA_CLOUD_OSS_WORM"],
            }
        ],
    }
    trust_path = root / "trust.json"
    _write_json(trust_path, trust)
    return manifest_path, trust_path


class ProductionP4GateTest(unittest.TestCase):
    def test_requirements_are_zero_credit_and_never_authorize(self):
        result = MODULE.blocked_readiness(
            CHECKED_AT, "production evidence manifest was not supplied"
        )
        self.assertEqual("BLOCKED_PRODUCTION_EVIDENCE", result["status"])
        self.assertEqual(16, result["required_gate_count"])
        self.assertEqual(0, result["verified_gate_count"])
        self.assertFalse(result["production_credit"])
        self.assertFalse(result["authorization"]["deploy_enabled"])
        self.assertFalse(result["authorization"]["cutover_enabled"])

    def test_default_policy_rejects_unsigned_self_assertion(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "manifest.json"
            _write_json(path, {"contract_id": MODULE.CONTRACT_ID})
            result = MODULE.evaluate(path, CHECKED_AT)
            self.assertFalse(result["production_credit"])
            self.assertEqual(0, result["verified_gate_count"])
            self.assertTrue(
                any("trust anchors" in error for error in result["errors"])
            )

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL is required")
    def test_complete_self_assertion_without_reviewed_trust_anchor_scores_zero(self):
        with tempfile.TemporaryDirectory() as raw:
            manifest, _ = _signed_manifest(Path(raw))
            result = MODULE.evaluate(manifest, CHECKED_AT)
            self.assertFalse(result["production_credit"])
            self.assertEqual(0, result["verified_gate_count"])
            self.assertEqual(0.0, result["completion_percent"])

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL is required")
    def test_manifest_signed_metadata_without_storage_attestor_scores_zero(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest, trust = _signed_manifest(root)
            trust_policy = json.loads(trust.read_text(encoding="utf-8"))
            trust_policy["storage_attestors"] = []
            _write_json(trust, trust_policy)
            result = MODULE.evaluate(manifest, CHECKED_AT, trust_path=trust)
            self.assertFalse(result["production_credit"])
            self.assertEqual(0, result["verified_gate_count"])
            self.assertIn(
                "no reviewed immutable-storage attestors are configured",
                " ".join(result["errors"]),
            )

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL is required")
    def test_complete_signed_denominator_is_evidence_ready_but_never_authorizes(self):
        with tempfile.TemporaryDirectory() as raw:
            manifest, trust = _signed_manifest(Path(raw))
            result = MODULE.evaluate(manifest, CHECKED_AT, trust_path=trust)
            self.assertEqual("PRODUCTION_P4_READY", result["status"])
            self.assertTrue(result["production_credit"])
            self.assertEqual(16, result["verified_gate_count"])
            self.assertEqual([], result["errors"])
            self.assertFalse(result["authorization"]["deploy_enabled"])
            self.assertFalse(result["authorization"]["payment_enabled"])
            self.assertFalse(result["authorization"]["import_enabled"])
            self.assertFalse(result["authorization"]["cutover_enabled"])

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL is required")
    def test_self_asserted_immutable_metadata_without_control_plane_proof_fails(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, trust = _signed_manifest(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            proof = root / manifest["gates"][0]["immutable_source"]["attestation_ref"]
            proof.unlink()
            result = MODULE.evaluate(manifest_path, CHECKED_AT, trust_path=trust)
            self.assertFalse(result["production_credit"])
            self.assertEqual(15, result["verified_gate_count"])
            self.assertIn(
                "attestation_ref is missing or unreadable",
                " ".join(result["errors"]),
            )

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL is required")
    def test_same_verifier_identity_and_tamper_fail_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path, trust = _signed_manifest(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["gates"][0]["independent_verifier"]["identity"] = "prod-collector"
            _write_json(manifest_path, manifest)
            result = MODULE.evaluate(manifest_path, CHECKED_AT, trust_path=trust)
            self.assertFalse(result["production_credit"])
            self.assertIn(
                "verifier identity must differ from collector",
                " ".join(result["errors"]),
            )
            self.assertIn(
                "manifest_sha256 does not match",
                " ".join(result["errors"]),
            )


if __name__ == "__main__":
    unittest.main()
