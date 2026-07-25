import hashlib
import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from production_evidence import (
    ASSET_UNIVERSE_CONTRACT_ID,
    CANONICAL_ASSET_UNIVERSE,
    COLLECTION_CONTRACT_ID,
    EXPECTED_ASSET_COUNT,
    blocked_readiness,
    generate_readiness,
)
from source_evidence import SourceEvidenceError, canonical_sha256


CHECKED_AT = "2026-07-25T00:10:00Z"
EXTRACTED_AT = "2026-07-25T00:00:00Z"
GTID = "3e11fa47-71ca-11e1-9e33-c80aa9429562:1-42"
CANONICAL_ASSETS = json.loads(
    CANONICAL_ASSET_UNIVERSE.read_text(encoding="utf-8")
)["assets"]
FIRST_ASSET = CANONICAL_ASSETS[0]


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _names_sha(names: list[str]) -> str:
    return hashlib.sha256(
        json.dumps(sorted(names), separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _write_pair(directory: Path, asset: str = FIRST_ASSET) -> tuple[Path, Path]:
    payload = directory / "source.jsonl"
    payload.write_text('{"tenant_id":"t-1","source_key":"k-1"}\n', encoding="utf-8")
    schema = directory / "source-schema.sql"
    schema.write_text("tenant_id STRING, source_key STRING\n", encoding="utf-8")
    query = directory / "extract.sql"
    query.write_text("SELECT tenant_id, source_key FROM source\n", encoding="utf-8")
    tenant_map = directory / "tenant-map.json"
    tenant_map.write_text('{"t-1":"1"}\n', encoding="utf-8")
    source_audit = directory / "source-audit.json"
    source_audit.write_text('{"access":"read-only"}\n', encoding="utf-8")
    verifier_code = directory / "verify.sql"
    verifier_code.write_text("SELECT COUNT(*) FROM independent_diff\n", encoding="utf-8")
    verifier_audit = directory / "verifier-audit.json"
    verifier_audit.write_text('{"identity":"verifier-prod"}\n', encoding="utf-8")

    bundle = {
        "contract_id": "yshopping.source-evidence-bundle.v1",
        "bundle_id": str(uuid.uuid4()),
        "source_system": "YSHOPPING",
        "source_environment": "production",
        "provenance": {
            "snapshot_id": "snapshot-prod-1",
            "extraction_job_id": "extract-prod-1",
            "extractor_identity": "extractor-prod",
            "extractor_environment_id": "extractor-host-prod",
            "fixture": False,
            "attestation_method": "SOURCE_SYSTEM_AUDIT_EXPORT",
            "read_only_confirmed": True,
            "attestation_ref": source_audit.name,
            "attestation_sha256": _file_sha(source_audit),
        },
        "source": {
            "asset": asset,
            "qualified_table": f"yshopping.{asset}",
            "schema_ref": schema.name,
            "schema_sha256": _file_sha(schema),
            "primary_key": ["source_key"],
            "columns": [
                {
                    "name": "tenant_id",
                    "type": "STRING",
                    "nullable": False,
                    "classification": "internal",
                    "semantic_role": "tenant",
                },
                {
                    "name": "source_key",
                    "type": "STRING",
                    "nullable": False,
                    "classification": "internal",
                    "semantic_role": "business_key",
                },
            ],
        },
        "extraction": {
            "mode": "READ_ONLY_SNAPSHOT",
            "full_denominator": True,
            "sampled": False,
            "query_ref": query.name,
            "query_sha256": _file_sha(query),
            "extracted_at": EXTRACTED_AT,
            "window": {
                "field": "id",
                "start_inclusive": "MIN",
                "end_exclusive": "MAX_PLUS_ONE",
            },
            "watermark": {
                "kind": "MYSQL_GTID_SET",
                "value": GTID,
                "server_id": "yshopping-primary",
            },
        },
        "tenant_scope": {
            "strategy": "source-key-map",
            "source_keys": ["tenant_id"],
            "tenant_count": 1,
        },
        "quality": {
            "row_count": 1,
            "distinct_business_key_count": 1,
            "duplicate_business_key_count": 0,
            "null_business_key_count": 0,
            "deleted_row_count": 0,
        },
        "semantic_artifacts": [
            {
                "kind": "tenant_mapping",
                "path": tenant_map.name,
                "sha256": _file_sha(tenant_map),
            }
        ],
        "security": {"pii_handling": "no_pii"},
        "files": [
            {
                "path": payload.name,
                "format": "JSONL",
                "byte_count": payload.stat().st_size,
                "row_count": 1,
                "sha256": _file_sha(payload),
            }
        ],
    }
    bundle["manifest_sha256"] = canonical_sha256(bundle, "manifest_sha256")
    bundle_path = directory / "bundle.json"
    _write_json(bundle_path, bundle)

    key_digest = hashlib.sha256(b"k-1").hexdigest()
    reconciliation = {
        "contract_id": "yshopping.source-reconciliation-evidence.v1",
        "reconciliation_id": str(uuid.uuid4()),
        "run_id": "reconcile-prod-1",
        "source_asset": asset,
        "source_bundle_ref": bundle_path.name,
        "source_bundle_manifest_sha256": bundle["manifest_sha256"],
        "result": "verified",
        "full_denominator": True,
        "sampled": False,
        "coverage": {
            "source_row_count": 1,
            "admitted_source_row_count": 1,
            "quarantined_source_row_count": 0,
            "missing_source_row_count": 0,
            "duplicate_source_coverage_count": 0,
            "tenant_count": 1,
            "source_business_key_sha256": key_digest,
            "accounted_business_key_sha256": key_digest,
        },
        "canonical_outputs": [{"target": f"canonical.{asset}", "row_count": 1}],
        "semantic_checks": [
            {
                "name": "business_key_coverage",
                "checked_count": 1,
                "mismatch_count": 0,
            }
        ],
        "independent_verifier": {
            "engine": "independent-sql-engine",
            "identity": "verifier-prod",
            "environment_id": "verifier-host-prod",
            "code_ref": verifier_code.name,
            "code_sha256": _file_sha(verifier_code),
            "execution_attestation_ref": verifier_audit.name,
            "execution_attestation_sha256": _file_sha(verifier_audit),
            "executed_at": "2026-07-25T00:05:00Z",
            "independent_from_extractor": True,
            "independent_from_canonical_transform": True,
        },
        "authorization": {"import_enabled": False, "cutover_enabled": False},
    }
    reconciliation["evidence_sha256"] = canonical_sha256(
        reconciliation, "evidence_sha256"
    )
    reconciliation_path = directory / "reconciliation.json"
    _write_json(reconciliation_path, reconciliation)
    return bundle_path, reconciliation_path


def _write_collection(directory: Path, *, include_entry: bool = True) -> Path:
    assets = CANONICAL_ASSETS
    universe = {
        "contract_id": ASSET_UNIVERSE_CONTRACT_ID,
        "assets": assets,
        "assets_sha256": _names_sha(assets),
    }
    universe_path = directory / "asset-universe.json"
    _write_json(universe_path, universe)
    access_audit = directory / "access-audit.json"
    access_audit.write_text('{"principal":"readonly-prod"}\n', encoding="utf-8")
    entries = []
    if include_entry:
        bundle, reconciliation = _write_pair(directory)
        entries.append(
            {
                "source_asset": FIRST_ASSET,
                "evidence_class": "PRODUCTION_OBSERVED",
                "fixture": False,
                "bundle_ref": bundle.name,
                "bundle_sha256": _file_sha(bundle),
                "reconciliation_ref": reconciliation.name,
                "reconciliation_sha256": _file_sha(reconciliation),
            }
        )
    collection = {
        "contract_id": COLLECTION_CONTRACT_ID,
        "collection_id": str(uuid.uuid4()),
        "readiness_checked_at": CHECKED_AT,
        "external_access": {
            "source_environment": "production",
            "endpoint_id": "yshopping-prod-ro",
            "read_only_identity": "readonly-prod",
            "identity_provider": "production-iam",
            "read_only_confirmed": True,
            "production_read_attempted": True,
            "audit_export_ref": access_audit.name,
            "audit_export_sha256": _file_sha(access_audit),
        },
        "denominator": {
            "expected_asset_count": EXPECTED_ASSET_COUNT,
            "asset_universe_ref": universe_path.name,
            "asset_universe_sha256": _file_sha(universe_path),
            "asset_names_sha256": _names_sha(assets),
        },
        "freshness": {"max_age_seconds": 3600},
        "entries": entries,
    }
    collection["collection_sha256"] = canonical_sha256(
        collection, "collection_sha256"
    )
    collection_path = directory / "collection.json"
    _write_json(collection_path, collection)
    return collection_path


def _mutate_json(path: Path, mutate) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    mutate(value)
    _write_json(path, value)
    return value


def _refresh_collection_digest(path: Path) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    value["collection_sha256"] = canonical_sha256(value, "collection_sha256")
    _write_json(path, value)


class ProductionEvidenceTest(unittest.TestCase):
    def test_missing_external_access_is_explicit_and_zero_credit(self):
        first = blocked_readiness(CHECKED_AT, ["production endpoint unavailable"])
        second = blocked_readiness(CHECKED_AT, ["production endpoint unavailable"])
        self.assertEqual(first, second)
        self.assertEqual("BLOCKED_EXTERNAL_ACCESS", first["status"])
        self.assertEqual(0, first["sourceInventory"]["runtimeReconciliations"])
        self.assertEqual(0, first["sourceInventory"]["finalVerified"])
        self.assertFalse(first["authorization"]["importEnabled"])
        self.assertFalse(first["authorization"]["cutoverEnabled"])

    def test_nonempty_valid_pair_is_credited_but_incomplete_denominator_is_not_ready(self):
        with tempfile.TemporaryDirectory() as raw:
            collection = _write_collection(Path(raw))
            first, errors = generate_readiness(collection)
            second, _ = generate_readiness(collection)
            self.assertEqual(first, second)
            self.assertEqual([], errors)
            self.assertEqual("BLOCKED_INCOMPLETE_OR_INVALID_EVIDENCE", first["status"])
            self.assertEqual(1, first["sourceInventory"]["runtimeReconciliations"])
            self.assertEqual(0, first["sourceInventory"]["finalVerified"])
            self.assertFalse(first["authorization"]["cutoverEnabled"])

    def test_empty_collection_never_receives_runtime_credit(self):
        with tempfile.TemporaryDirectory() as raw:
            collection = _write_collection(Path(raw), include_entry=False)
            readiness, errors = generate_readiness(collection)
            self.assertEqual([], errors)
            self.assertEqual(0, readiness["evidenceDiscovery"]["productionBundles"])
            self.assertEqual(0, readiness["sourceInventory"]["runtimeReconciliations"])

    def test_fixture_entry_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            collection = _write_collection(Path(raw))
            _mutate_json(collection, lambda value: value["entries"][0].update(fixture=True))
            _refresh_collection_digest(collection)
            readiness, _ = generate_readiness(collection)
            self.assertEqual(0, readiness["sourceInventory"]["runtimeReconciliations"])
            self.assertIn(FIRST_ASSET, readiness["evidenceDiscovery"]["rejectedAssets"])

    def test_incomplete_asset_universe_cannot_change_locked_denominator(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            collection = _write_collection(root)
            universe_path = root / "asset-universe.json"
            universe = _mutate_json(
                universe_path,
                lambda value: (
                    value["assets"].pop(),
                    value.update(assets_sha256=_names_sha(value["assets"])),
                ),
            )
            value = json.loads(collection.read_text(encoding="utf-8"))
            value["denominator"]["asset_universe_sha256"] = _file_sha(universe_path)
            value["denominator"]["asset_names_sha256"] = universe["assets_sha256"]
            value["collection_sha256"] = canonical_sha256(value, "collection_sha256")
            _write_json(collection, value)
            readiness, errors = generate_readiness(collection)
            self.assertTrue(any("exactly 718" in error for error in errors))
            self.assertEqual(EXPECTED_ASSET_COUNT, readiness["sourceInventory"]["logicalAssets"])
            self.assertNotEqual("READY", readiness["status"])

    def test_arbitrary_718_names_cannot_replace_canonical_denominator(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            collection = _write_collection(root)
            universe_path = root / "asset-universe.json"
            fake_assets = [f"asset_{index:03d}" for index in range(EXPECTED_ASSET_COUNT)]
            _write_json(
                universe_path,
                {
                    "contract_id": ASSET_UNIVERSE_CONTRACT_ID,
                    "assets": fake_assets,
                    "assets_sha256": _names_sha(fake_assets),
                },
            )
            value = json.loads(collection.read_text(encoding="utf-8"))
            value["denominator"]["asset_universe_sha256"] = _file_sha(universe_path)
            value["denominator"]["asset_names_sha256"] = _names_sha(fake_assets)
            value["collection_sha256"] = canonical_sha256(value, "collection_sha256")
            _write_json(collection, value)
            readiness, errors = generate_readiness(collection)
            self.assertTrue(any("canonical denominator" in error for error in errors))
            self.assertFalse(readiness["authorization"]["importEnabled"])
            self.assertFalse(readiness["authorization"]["cutoverEnabled"])
            self.assertFalse(readiness["productionCredit"])

    def test_gtid_freshness_and_verifier_separation_are_fail_closed(self):
        cases = (
            (
                "gtid",
                lambda bundle, reconciliation: bundle["extraction"]["watermark"].update(
                    value="partition-20260725"
                ),
                "GTID",
            ),
            (
                "stale",
                lambda bundle, reconciliation: bundle["extraction"].update(
                    extracted_at="2026-07-24T00:00:00Z"
                ),
                "stale",
            ),
            (
                "identity",
                lambda bundle, reconciliation: reconciliation[
                    "independent_verifier"
                ].update(identity="extractor-prod"),
                "must differ",
            ),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                collection = _write_collection(root)
                bundle_path = root / "bundle.json"
                reconciliation_path = root / "reconciliation.json"
                bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
                reconciliation = json.loads(
                    reconciliation_path.read_text(encoding="utf-8")
                )
                mutate(bundle, reconciliation)
                bundle["manifest_sha256"] = canonical_sha256(bundle, "manifest_sha256")
                _write_json(bundle_path, bundle)
                reconciliation["source_bundle_manifest_sha256"] = bundle[
                    "manifest_sha256"
                ]
                reconciliation["evidence_sha256"] = canonical_sha256(
                    reconciliation, "evidence_sha256"
                )
                _write_json(reconciliation_path, reconciliation)
                value = json.loads(collection.read_text(encoding="utf-8"))
                value["entries"][0]["bundle_sha256"] = _file_sha(bundle_path)
                value["entries"][0]["reconciliation_sha256"] = _file_sha(
                    reconciliation_path
                )
                value["collection_sha256"] = canonical_sha256(
                    value, "collection_sha256"
                )
                _write_json(collection, value)
                readiness, _ = generate_readiness(collection)
                messages = " ".join(
                    readiness["evidenceDiscovery"]["rejectedAssets"][FIRST_ASSET]
                )
                self.assertIn(expected, messages)
                self.assertEqual(0, readiness["sourceInventory"]["runtimeReconciliations"])

    def test_collection_and_referenced_file_digests_are_tamper_evident(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            collection = _write_collection(root)
            _mutate_json(
                collection,
                lambda value: value["external_access"].update(endpoint_id="tampered"),
            )
            with self.assertRaisesRegex(SourceEvidenceError, "collection_sha256"):
                generate_readiness(collection)

            collection = _write_collection(root)
            (root / "source.jsonl").write_text('{"tampered":true}\n', encoding="utf-8")
            readiness, _ = generate_readiness(collection)
            self.assertEqual(0, readiness["sourceInventory"]["runtimeReconciliations"])
            self.assertIn(FIRST_ASSET, readiness["evidenceDiscovery"]["rejectedAssets"])


if __name__ == "__main__":
    unittest.main()
