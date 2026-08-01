import json
from pathlib import Path


def test_merchant_rectification_definition():
    definition = json.loads(
        (Path(__file__).parents[1] / "skill-task.json").read_text(encoding="utf-8")
    )

    assert definition["skill_id"] == "skill.cloudmold.merchant-experience.rectification-lifecycle.v1"
    assert definition["workflow_level"] == "BUSINESS_ROLE"
    assert definition["owner_role"] == "merchant-experience-operator"
    assert definition["risk_level"] == "R3"
    assert len(definition["steps"]) == 13
    assert [step["step_order"] for step in definition["steps"]] == list(range(1, 14))

    by_code = {step["step_code"]: step for step in definition["steps"]}
    assert by_code["validate_responsible_merchant"]["operation_type"] == "READ"
    assert by_code["reopen_consumer_ticket"]["operation_type"] == "WRITE"
    assert by_code["verify_merchant_rectification"]["operation_type"] == "WRITE"
    assert by_code["verify_recovered_ticket"]["wait_success"] == {"/ticketStatus": "CLOSED"}

    writes = [step for step in definition["steps"] if step.get("operation_type") == "WRITE"]
    assert len(writes) == 10
    assert all(step["approval_required"] for step in writes)
    assert all("idempotency_binding" in step for step in writes)
