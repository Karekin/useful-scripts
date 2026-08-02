import json
from pathlib import Path


def test_product_management_is_a_governed_role_workflow():
    definition = json.loads(
        (Path(__file__).parents[1] / "skill-task.json").read_text(encoding="utf-8")
    )

    assert definition["workflow_level"] == "BUSINESS_ROLE"
    assert definition["owner_role"] == "product-operations"
    assert definition["risk_level"] == "R3"
    assert len(definition["steps"]) == 15
    assert [
        step["child_skill_id"]
        for step in definition["steps"]
        if step.get("step_kind") == "SUBMIT_CHILD"
    ] == [
        "skill.cloudmold.catalog.assortment-planning-lifecycle.v1",
        "skill.cloudmold.commerce.product-to-listing.v1",
        "skill.cloudmold.consumer.shopping-journey.v1",
        "skill.cloudmold.quality.mystery-buyer-sample-verification.v1",
        "skill.cloudmold.engagement.promotion-campaign-operations.v1",
    ]
    assert definition["steps"][-1]["wait_success"]["/status"] == "RESOLVED"
    purchase_overrides = definition["steps"][7]["arguments"]["$overrides"]
    assert purchase_overrides["/favoriteCommand/canonicalSpuId"].endswith(
        ".canonicalSpuId"
    )
    assert definition["steps"][9]["child_run_id"] == "$input.quality.traceId"
