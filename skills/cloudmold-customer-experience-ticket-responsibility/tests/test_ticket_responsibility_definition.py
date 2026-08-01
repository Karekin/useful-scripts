import json
from pathlib import Path


def test_ticket_responsibility_definition():
    definition = json.loads(
        (Path(__file__).parents[1] / "skill-task.json").read_text(encoding="utf-8")
    )

    assert definition["skill_id"] == "skill.cloudmold.customer-experience.ticket-responsibility-lifecycle.v1"
    assert definition["workflow_level"] == "BUSINESS_ROLE"
    assert definition["owner_role"] == "consumer-experience-operator"
    assert definition["risk_level"] == "R3"
    assert len(definition["steps"]) == 19
    assert [step["step_order"] for step in definition["steps"]] == list(range(1, 20))

    by_code = {step["step_code"]: step for step in definition["steps"]}
    assert by_code["submit_consumer_journey"]["step_kind"] == "SUBMIT_CHILD"
    assert by_code["submit_consumer_journey"]["child_skill_id"] == (
        "skill.cloudmold.consumer.shopping-journey.v1"
    )
    assert by_code["ticket_responsibility_decision"]["operation_type"] == "WRITE"
    assert by_code["ticket_pay_compensation"]["operation_type"] == "WRITE"
    assert by_code["ticket_terminal_readback"]["wait_success"] == {"/ticketStatus": "CLOSED"}

    writes = [step for step in definition["steps"] if step.get("operation_type") == "WRITE"]
    assert len(writes) == 15
    assert all(step["approval_required"] for step in writes)
    assert all("idempotency_binding" in step for step in writes)
