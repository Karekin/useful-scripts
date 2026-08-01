import json
from pathlib import Path


def test_warehouse_admission_enforces_quality_before_merchant_and_inbound():
    definition = json.loads(
        (Path(__file__).parents[1] / "skill-task.json").read_text(encoding="utf-8")
    )

    assert definition["workflow_level"] == "BUSINESS_ROLE"
    assert definition["owner_role"] == "supply-chain-operator"
    assert definition["risk_level"] == "R3"
    assert len(definition["steps"]) == 12

    quality_gate = definition["steps"][3]
    assert quality_gate["step_code"] == "verify_quality_first_admission_gate"
    assert quality_gate["wait_success"]["/status"] == "VERIFIED"

    children = [
        step["child_skill_id"]
        for step in definition["steps"]
        if step.get("step_kind") == "SUBMIT_CHILD"
    ]
    assert children == [
        "skill.cloudmold.merchant.onboarding-lifecycle.v1",
        "skill.cloudmold.supply.replenishment-lifecycle.v1",
        "skill.cloudmold.engagement.promotion-campaign-operations.v1",
    ]
    assert definition["steps"][-1]["wait_success"]["/status"] == "RESOLVED"
