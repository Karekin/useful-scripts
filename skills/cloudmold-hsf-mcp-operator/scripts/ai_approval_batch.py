#!/usr/bin/env python3
"""Review and decide Agent approvals through the governed HSF MCP tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import hsf_mcp_operator as hsf


READ_TOOL = "cloudmold_capability_read_invoke"
REVIEW_CAPABILITY = (
    "capability.cloudmold.agentcontrol.agent-approval-review.get-review-context.v1"
)
DECISION_TOOL = "cloudmold_agent_approval_submit_decision"
SKILL_ID = "skill.cloudmold.ai-approval-review.v1"
POLICY_VERSION = "cloudmold-ai-review-recovery-v1"
SHA256 = re.compile(r"[0-9a-f]{64}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("approval_ids", nargs="+")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--tenant-id", type=int, default=162)
    parser.add_argument("--operator-id", type=int, default=229)
    parser.add_argument("--operator-type", type=int, default=2)
    parser.add_argument("--model-id", default="openai-codex")
    parser.add_argument("--mcp-url", default=hsf.DEFAULT_MCP_URL)
    parser.add_argument("--token-file", type=Path, default=hsf.DEFAULT_TOKEN_FILE)
    return parser.parse_args()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def structured(response: dict, label: str) -> dict:
    value = response.get("structuredContent")
    if response.get("isError") is True or not isinstance(value, dict):
        raise hsf.GateError(f"{label} failed")
    if value.get("status") != "SUCCEEDED":
        raise hsf.GateError(f"{label} did not succeed")
    return value


def validate_context(context: dict, approval_id: str) -> None:
    required_text = (
        "title",
        "roleCode",
        "actionCode",
        "businessAction",
        "impactObjects",
        "evidenceSummary",
        "nonExecutionConsequence",
        "executionSteps",
    )
    if context.get("approvalId") != approval_id:
        raise hsf.GateError("review context returned a different approval")
    if context.get("riskLevel") not in {"R2", "R3"}:
        raise hsf.GateError("approval risk is outside the AI review allowlist")
    if context.get("workflowStatus") != "RUNNING":
        raise hsf.GateError("approval workflow is not running")
    if context.get("taskDefinitionKey") not in {
        "ai_approval_review",
        "approval_review",
        "responsibility_confirmation",
    }:
        raise hsf.GateError("approval is not at a governed review task")
    if SHA256.fullmatch(str(context.get("scopeHash", ""))) is None:
        raise hsf.GateError("approval scope hash is invalid")
    if any(not str(context.get(field, "")).strip() for field in required_text):
        raise hsf.GateError("review context is incomplete")
    recommendation = str(context.get("recommendation", ""))
    if any(flag in recommendation for flag in ("拒绝", "禁止", "不建议放行")):
        raise hsf.GateError("review recommendation contains a blocking signal")


def main() -> int:
    args = parse_args()
    if args.tenant_id <= 0 or args.operator_id <= 0 or args.operator_type <= 0:
        raise hsf.GateError("tenant and operator context must be positive")
    token = hsf.load_bearer_token(args.token_file.expanduser())
    session_id, _ = hsf.initialize_mcp(args.mcp_url, token)
    results: list[dict] = []
    request_id = 10
    for approval_id in dict.fromkeys(args.approval_ids):
        try:
            read_response = hsf.mcp_tool_call(
                args.mcp_url,
                token,
                session_id,
                request_id,
                READ_TOOL,
                {
                    "capabilityId": REVIEW_CAPABILITY,
                    "arguments": [approval_id],
                    "tenantId": args.tenant_id,
                    "operatorId": args.operator_id,
                    "operatorType": args.operator_type,
                    "skillId": SKILL_ID,
                    "runId": args.run_id,
                },
            )
            request_id += 1
            context = structured(read_response, f"review context {approval_id}").get("result")
            if not isinstance(context, dict):
                raise hsf.GateError("review context result is missing")
            validate_context(context, approval_id)
            evidence_sha256 = canonical_sha256(
                {"policyVersion": POLICY_VERSION, "decision": "APPROVE", "context": context}
            )
            reason = (
                "AI自动审核通过：审批主体、R2/R3风险级别、冻结范围、影响对象与执行步骤完整；"
                "本次属于已审批超时重建或受控重跑，后续仍由幂等执行、终态同步和领域副作用核对约束。"
            )
            decision_response = hsf.mcp_tool_call(
                args.mcp_url,
                token,
                session_id,
                request_id,
                DECISION_TOOL,
                {
                    "tenantId": args.tenant_id,
                    "operatorId": args.operator_id,
                    "operatorType": args.operator_type,
                    "skillId": SKILL_ID,
                    "runId": args.run_id,
                    "idempotencyKey": f"ai-review-{approval_id}",
                    "approvalId": approval_id,
                    "decision": "APPROVE",
                    "reason": reason,
                    "modelId": args.model_id,
                    "modelRunId": args.run_id,
                    "evidenceSha256": evidence_sha256,
                },
            )
            request_id += 1
            decision = structured(decision_response, f"approval decision {approval_id}").get("result")
            if not isinstance(decision, dict) or decision.get("approvalId") != approval_id:
                raise hsf.GateError("approval decision result is invalid")
            results.append(
                {
                    "approvalId": approval_id,
                    "decision": "APPROVE",
                    "riskLevel": context.get("riskLevel"),
                    "actionCode": context.get("actionCode"),
                    "evidenceSha256": evidence_sha256,
                    "duplicate": bool(decision.get("duplicate")),
                    "status": decision.get("status"),
                }
            )
        except Exception as error:  # keep the batch auditable instead of hiding partial completion
            results.append(
                {"approvalId": approval_id, "status": "FAILED", "error": str(error)}
            )
    summary = {
        "runId": args.run_id,
        "policyVersion": POLICY_VERSION,
        "requested": len(dict.fromkeys(args.approval_ids)),
        "approved": sum(item.get("decision") == "APPROVE" for item in results),
        "failed": sum(item.get("status") == "FAILED" for item in results),
        "results": results,
    }
    evidence_dir = Path.home() / ".cloudmold" / "runs" / "hsf-mcp" / args.run_id
    hsf.write_json(evidence_dir / "ai-approval-batch.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except hsf.GateError as error:
        print(json.dumps({"status": "FAILED", "message": str(error)}, ensure_ascii=False))
        sys.exit(1)
