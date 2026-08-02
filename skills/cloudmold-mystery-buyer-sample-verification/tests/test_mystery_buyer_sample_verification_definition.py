import json
from pathlib import Path


def test_mystery_buyer_sample_verification_is_internal_and_fail_closed():
    definition = json.loads(
        (Path(__file__).parents[1] / "skill-task.json").read_text(encoding="utf-8")
    )

    assert definition["workflow_level"] == "INTERNAL_SUBFLOW"
    assert definition["risk_level"] == "R3"
    assert len(definition["steps"]) == 12
    assert sum(step.get("operation_type") == "WRITE" for step in definition["steps"]) == 11
    write_steps = [
        step for step in definition["steps"] if step.get("operation_type") == "WRITE"
    ]
    assert all(
        step["arguments"][0]["$overrides"]["/runId"] == "$task.runId"
        for step in write_steps
    )

    terminal = definition["steps"][-1]
    assert terminal["step_kind"] == "WAIT_CAPABILITY"
    assert terminal["wait_success"] == {
        "/status": "VERIFIED",
        "/inspectionStatus": "COMPLETED",
        "/decision": "PASS",
    }
    assert terminal["wait_failure"]["/status"] == ["REJECTED", "RECALLED"]
