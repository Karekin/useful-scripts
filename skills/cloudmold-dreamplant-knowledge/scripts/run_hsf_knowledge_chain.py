#!/usr/bin/env python3
"""Build and verify one product-centric DreamPlant learning loop over Dubbo only."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = SKILL_ROOT.parents[2]
FLOW_RUNNER = WORKSPACE / "useful-scripts/scripts/yudao_dubbo_flow.py"
SCENARIO = SKILL_ROOT / "references/scenario.json"
SKILL_ID = "skill.cloudmold.dreamplant.knowledge.v1"


def load_successful(path: Path) -> dict[str, Any]:
    value = json.loads(path.expanduser().read_text(encoding="utf-8"))
    final = value.get("final", {})
    status = value.get("status") or final.get("status") or final.get("catalog_status")
    if status not in {"SUCCEEDED", "ACTIVE"}:
        raise RuntimeError(f"retained ledger is not successful: {path} ({status})")
    return value


def find_first(root: Any, key: str) -> Any:
    if isinstance(root, dict):
        value = root.get(key)
        if value not in (None, ""):
            return value
        for child in root.values():
            found = find_first(child, key)
            if found not in (None, ""):
                return found
    elif isinstance(root, list):
        for child in root:
            found = find_first(child, key)
            if found not in (None, ""):
                return found
    return None


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def retained_relation_id(from_asset_id: str, to_asset_id: str) -> str | None:
    """Reuse the canonical edge identity already proven in retained evidence."""
    root = Path.home() / ".cloudmold/runs/dreamplant-knowledge"
    for path in sorted(root.glob("*/run.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            ledger = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for step in ledger.get("steps", []):
            result = step.get("result") or {}
            if not isinstance(result, dict):
                continue
            if (result.get("fromAssetId"), result.get("toAssetId")) == (from_asset_id, to_asset_id):
                relation_id = result.get("relationId")
                if isinstance(relation_id, str) and relation_id:
                    return relation_id
    return None


def build_input(master: dict[str, Any], catalog: dict[str, Any], run_id: str) -> dict[str, Any]:
    principal_id = find_first(master, "principalId")
    merchant_id = find_first(master, "merchantId")
    shop_id = find_first(master, "shopId")
    sku_id = find_first(catalog, "canonicalSkuId")
    sku_code = find_first(catalog, "sku_code") or find_first(catalog, "skuCode")
    if not all(isinstance(value, str) and value for value in (principal_id, merchant_id, shop_id, sku_id)):
        raise RuntimeError("retained ledgers do not contain canonical Principal/Merchant/Shop/SKU identities")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    occurred_at = now.isoformat().replace("+00:00", "Z")
    dispatch_at = (now + timedelta(minutes=4)).isoformat().replace("+00:00", "Z")
    map_key = "dreamplant"
    product_asset_id = f"product:sku:{sku_id}"
    capability_asset_id = "capability:cloudmold:commerce-full-chain-hsf"
    relation_id = retained_relation_id(product_asset_id, capability_asset_id) \
        or f"relation:product-capability:{sku_id[:12]}"
    evidence_id = f"evidence:{run_id}:full-chain"
    metric_id = f"metric:{run_id}:hsf-success"
    sync_key = f"sync:{run_id}:cdc"
    drift_id = f"drift:{run_id}:coverage"
    exploration_run_id = f"exploration-{run_id}"
    source_ref = f"restricted:cloudmold/runs/{run_id}"
    evidence_payload = compact_json({"runId": run_id, "canonicalSkuId": sku_id, "transport": "dubbo"})
    evidence_ref = "sha256:" + sha256(evidence_payload)
    common = {"mapKey": map_key, "runTraceId": run_id, "expectedVersion": 0,
              "sourceRef": source_ref, "occurredAt": occurred_at}

    product_details = compact_json({"canonicalSkuId": sku_id, "skuCode": sku_code, "authority": "catalog"})
    capability_details = compact_json({"skillId": "skill.cloudmold.commerce.full-chain-hsf.v1",
                                       "transport": "dubbo", "status": "executed"})
    relation_details = compact_json({"purpose": "the canonical SKU is governed by the full-chain HSF Skill"})
    record_details = compact_json({"sourceRunId": run_id, "transport": "dubbo"})

    return {
        "authority": {
            "reference": {"merchantId": merchant_id, "shopId": shop_id},
            "operator": {"principalId": principal_id, "merchantId": merchant_id,
                         "shopId": shop_id, "roleCode": "OWNER"},
        },
        "graph": {"mapKey": map_key, "runTraceId": run_id, "occurredAt": occurred_at,
                  "projectionIdempotencyKey": f"{run_id}-projection"},
        "product": {"assetId": product_asset_id, "canonicalSkuId": sku_id,
                    "command": {**common, "assetId": product_asset_id, "assetType": "PRODUCT",
                                "idempotencyKey": f"{run_id}-product", "displayName": f"CloudMold SKU {sku_code or sku_id}",
                                "status": "ACTIVE", "lifecycleStage": "VERIFIED", "ownerPrincipalId": principal_id,
                                "canonicalKey": sku_id, "detailsJson": product_details,
                                "evidenceRef": evidence_ref, "observedAt": occurred_at}},
        "capability": {"assetId": capability_asset_id,
                       "command": {**common, "assetId": capability_asset_id, "assetType": "CAPABILITY",
                                   "idempotencyKey": f"{run_id}-capability", "displayName": "CloudMold commerce full-chain HSF",
                                   "status": "ACTIVE", "lifecycleStage": "EXECUTED", "ownerPrincipalId": principal_id,
                                   "canonicalKey": "skill.cloudmold.commerce.full-chain-hsf.v1",
                                   "detailsJson": capability_details, "evidenceRef": evidence_ref,
                                   "observedAt": occurred_at}},
        "relation": {"relationId": relation_id,
                     "command": {**common, "relationId": relation_id, "idempotencyKey": f"{run_id}-relation",
                                 "fromAssetId": product_asset_id, "fromAssetType": "PRODUCT",
                                 "toAssetId": capability_asset_id, "toAssetType": "CAPABILITY",
                                 "relationType": "IMPLEMENTS", "status": "ACTIVE", "detailsJson": relation_details,
                                 "evidenceRef": evidence_ref, "observedAt": occurred_at}},
        "evidence": {"evidenceId": evidence_id,
                     "command": {**common, "evidenceId": evidence_id, "idempotencyKey": f"{run_id}-evidence",
                                 "subjectType": "PRODUCT", "subjectId": product_asset_id,
                                 "evidenceType": "HSF_FULL_CHAIN", "title": "HSF full-chain execution evidence",
                                 "summary": "Canonical SKU completed commerce, after-sale, refund and lakehouse reconciliation",
                                 "contentRef": evidence_ref, "contentSha256": sha256(evidence_payload),
                                 "detailsJson": record_details, "observedAt": occurred_at, "capturedAt": occurred_at}},
        "metric": {"metricId": metric_id,
                   "command": {**common, "metricId": metric_id, "idempotencyKey": f"{run_id}-metric",
                               "subjectType": "PRODUCT", "subjectId": product_asset_id,
                               "metricCode": "HSF_CHAIN_SUCCESS", "metricName": "HSF full-chain success",
                               "metricValue": 1, "metricUnit": "BOOLEAN", "status": "VERIFIED",
                               "dimensionJson": compact_json({"transport": "dubbo"}), "detailsJson": record_details,
                               "evidenceRef": evidence_ref, "measuredAt": occurred_at}},
        "sync": {"syncKey": sync_key,
                 "command": {**common, "syncKey": sync_key, "idempotencyKey": f"{run_id}-sync",
                             "sourceSystem": "CLOUDMOLD_CDC", "sourceNamespace": "commerce",
                             "sourceCursor": run_id, "sourceCheckpointRef": evidence_ref,
                             "targetProjection": "dreamplant", "status": "COMPLETED",
                             "detailsJson": record_details, "evidenceRef": evidence_ref,
                             "checkpointAt": occurred_at}},
        "drift": {"driftId": drift_id,
                  "command": {**common, "driftId": drift_id, "idempotencyKey": f"{run_id}-drift",
                              "subjectType": "PRODUCT", "subjectId": product_asset_id,
                              "driftType": "HSF_CAPABILITY_COVERAGE", "severity": "LOW", "status": "OBSERVED",
                              "baselineRef": evidence_ref, "observedRef": evidence_ref,
                              "detailsJson": record_details, "evidenceRef": evidence_ref,
                              "detectedAt": occurred_at}},
        "exploration": {"explorationRunId": exploration_run_id, "dispatchAt": dispatch_at,
                        "dispatchIdempotencyKey": f"{run_id}-dispatch",
                        "command": {"operation": "SUBMIT_EXPLORATION", "idempotencyKey": f"{run_id}-exploration",
                                    "runTraceId": run_id, "occurredAt": occurred_at, "mapKey": map_key,
                                    "explorationRunId": exploration_run_id,
                                    "intent": f"Evaluate next governed automation capability for canonical SKU {sku_id}",
                                    "contextJson": compact_json({"canonicalSkuId": sku_id, "evidenceRef": evidence_ref}),
                                    "requestedByPrincipalId": principal_id}},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["plan", "execute"], default="execute")
    parser.add_argument("--master-ledger", type=Path)
    parser.add_argument("--catalog-ledger", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--tenant-id", type=int, default=1)
    parser.add_argument("--operator-id", type=int, default=1)
    parser.add_argument("--operator-type", type=int, default=1)
    parser.add_argument("--step-timeout-seconds", type=int, default=90)
    args = parser.parse_args()

    if args.mode == "plan":
        return subprocess.call([sys.executable, str(FLOW_RUNNER), "plan", "--scenario", str(SCENARIO)])
    if not args.master_ledger or not args.catalog_ledger or not args.run_id:
        parser.error("execute requires --master-ledger, --catalog-ledger and --run-id")

    inputs = build_input(load_successful(args.master_ledger), load_successful(args.catalog_ledger), args.run_id)
    with tempfile.TemporaryDirectory(prefix="cloudmold-dreamplant-") as directory:
        input_path = Path(directory) / "input.json"
        input_path.write_text(json.dumps(inputs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        command = [sys.executable, str(FLOW_RUNNER), "execute", "--scenario", str(SCENARIO),
                   "--input-json", str(input_path), "--skill-id", SKILL_ID, "--run-id", args.run_id,
                   "--tenant-id", str(args.tenant_id), "--operator-id", str(args.operator_id),
                   "--operator-type", str(args.operator_type), "--step-timeout-seconds",
                   str(args.step_timeout_seconds), "--write-approved", "--evidence-root",
                   str(Path.home() / ".cloudmold/runs/dreamplant-knowledge")]
        return subprocess.call(command, cwd=WORKSPACE)


if __name__ == "__main__":
    raise SystemExit(main())
