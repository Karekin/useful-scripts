import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_supplier_admission_preserves_independent_submitter_and_reviewer():
    definition = json.loads((ROOT / "skill-task.json").read_text())
    assert definition["risk_level"] == "R3"
    assert [step["step_code"] for step in definition["steps"]] == [
        "register_supplier", "submit_admission", "approve_admission"
    ]
    assert definition["steps"][1]["arguments"][1] == "$input.commands.1.actorPrincipalId"
    assert definition["steps"][2]["arguments"][1] == "$input.commands.2.actorPrincipalId"
