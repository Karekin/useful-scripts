import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_stock_transfer_is_a_canonical_ai_approved_dispatch_receive_lifecycle():
    manifest = json.loads((ROOT / "skill.json").read_text())
    definition = json.loads((ROOT / "skill-task.json").read_text())

    assert manifest["authority"] == "canonical-cloudmold"
    assert manifest["risk_level"] == "R2"
    assert definition["owner_role"] == "inventory-control"
    assert [step["step_code"] for step in definition["steps"]] == [
        "dispatch_stock", "receive_stock"
    ]
    assert all(step["approval_required"] for step in definition["steps"])
    assert all(
        step["capability_id"]
        == "capability.cloudmold.inventory.inventory-stock-transfer.execute.v1"
        for step in definition["steps"]
    )
    assert definition["steps"][1]["arguments"][0]["$overrides"]["/movementGroupId"] \
        == "$steps.dispatch_stock.result.movementGroupId"
