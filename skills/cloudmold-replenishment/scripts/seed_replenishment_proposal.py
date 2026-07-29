#!/usr/bin/env python3
"""Create one rotating, API-backed replenishment execution proposal."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any


NAMESPACE = uuid.UUID("55a8be58-8841-4fbe-b496-e168034dfe91")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(value: Any) -> str:
    payload = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stable_id(tenant_id: int, run_key: str, kind: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{tenant_id}:{run_key}:{kind}"))


def choose_scenario(document: dict[str, Any], business_date: dt.date,
                    allow_single_scenario: bool = False) -> dict[str, Any]:
    scenarios = document.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("scenario file must contain a non-empty scenarios array")
    if len(scenarios) < 2 and not allow_single_scenario:
        raise ValueError(
            "at least two scenarios are required for rotation; "
            "pass --allow-single-scenario only for a bounded local proof"
        )
    scenario = scenarios[business_date.toordinal() % len(scenarios)]
    required = {
        "scenarioCode",
        "canonicalSkuId",
        "canonicalWarehouseId",
        "mappingEvidenceSha256",
        "targetType",
    }
    missing = sorted(required.difference(scenario))
    if missing:
        raise ValueError(f"rotating scenario is missing fields: {', '.join(missing)}")
    if len(str(scenario["mappingEvidenceSha256"])) != 64:
        raise ValueError("mappingEvidenceSha256 must be a lowercase SHA-256")
    return scenario


def floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if value < 0 or step <= 0:
        raise ValueError("value must be non-negative and step must be positive")
    return (value // step) * step


def adapt_transfer_scenario(
    scenario: dict[str, Any],
    source_quantity: Decimal,
    target_quantity: Decimal,
) -> tuple[dict[str, Any], dict[str, str]]:
    if scenario.get("targetType") != "TRANSFER_REQUEST":
        return dict(scenario), {}
    if source_quantity < 0 or target_quantity < 0:
        raise ValueError("live WMS inventory quantities must be non-negative")

    minimum_order = Decimal(str(scenario.get("minimumOrderQuantity", "1")))
    reserve = Decimal(str(scenario.get("sourceReserveQuantity", minimum_order)))
    fraction = Decimal(str(scenario.get("maxTransferFraction", "0.25")))
    total_capacity = Decimal(str(scenario.get("capacityQuantity", "0")))
    if minimum_order <= 0:
        raise ValueError("minimumOrderQuantity must be positive")
    if reserve < 0:
        raise ValueError("sourceReserveQuantity must be non-negative")
    if fraction <= 0 or fraction > 1:
        raise ValueError("maxTransferFraction must be in (0, 1]")
    if total_capacity <= target_quantity:
        raise ValueError("target warehouse has no configured capacity headroom")

    source_limit = floor_to_step(
        max(Decimal("0"), source_quantity - reserve), minimum_order
    )
    fraction_limit = floor_to_step(source_quantity * fraction, minimum_order)
    target_headroom = total_capacity - target_quantity
    target_limit = floor_to_step(target_headroom, minimum_order)
    suggested = min(source_limit, fraction_limit, target_limit)
    if suggested < minimum_order:
        raise ValueError(
            "no safe transfer quantity: live source inventory, reserve, "
            "rotation fraction or target capacity is below minimum order"
        )

    safety_stock = min(
        Decimal(str(scenario.get("safetyStockQuantity", "0"))),
        target_quantity,
    )
    forecast_quantity = target_quantity + suggested - safety_stock
    adapted = dict(scenario)
    adapted.update(
        {
            "forecastQuantity": str(forecast_quantity),
            "safetyStockQuantity": str(safety_stock),
            "onHandQuantity": str(target_quantity),
            "inboundQuantity": "0",
            "capacityQuantity": str(target_headroom),
            "suggestedQuantity": str(suggested),
        }
    )
    preflight = {
        "sourceAvailableQuantity": str(source_quantity),
        "sourceReserveQuantity": str(reserve),
        "targetAvailableQuantity": str(target_quantity),
        "targetCapacityQuantity": str(total_capacity),
        "targetHeadroomQuantity": str(target_headroom),
        "maxTransferFraction": str(fraction),
        "safeTransferQuantity": str(suggested),
    }
    return adapted, preflight


def build_commands(tenant_id: int, business_date: dt.date, run_key: str,
                   scenario: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    ids = {
        "forecastId": stable_id(tenant_id, run_key, "forecast"),
        "planId": stable_id(tenant_id, run_key, "plan"),
        "scenarioId": stable_id(tenant_id, run_key, "scenario"),
        "recommendationId": stable_id(tenant_id, run_key, "recommendation"),
        "proposalId": stable_id(tenant_id, run_key, "proposal"),
        "correlationId": stable_id(tenant_id, run_key, "correlation"),
    }
    occurred_at = dt.datetime.combine(
        business_date, dt.time(hour=1), tzinfo=dt.timezone.utc
    ).isoformat().replace("+00:00", "Z")
    horizon_start = business_date + dt.timedelta(days=1)
    horizon_end = business_date + dt.timedelta(days=14)
    code_suffix = run_key.upper().replace("-", "")[-12:]
    sku = str(scenario["canonicalSkuId"])
    warehouse = str(scenario["canonicalWarehouseId"])
    uom = str(scenario.get("uomCode", "EA"))
    forecast_quantity = str(scenario.get("forecastQuantity", "80"))
    safety_stock = str(scenario.get("safetyStockQuantity", "20"))
    on_hand = str(scenario.get("onHandQuantity", "10"))
    inbound = str(scenario.get("inboundQuantity", "5"))
    capacity = str(scenario.get("capacityQuantity", "200"))
    minimum_order = str(scenario.get("minimumOrderQuantity", "10"))
    suggested_quantity = str(
        scenario.get(
            "suggestedQuantity",
            max(Decimal("1"), Decimal(forecast_quantity) + Decimal(safety_stock)
                - Decimal(on_hand) - Decimal(inbound)),
        )
    )
    unit_cost_minor = int(scenario.get("unitCostMinor", 100))

    def envelope(operation: str, body: dict[str, Any]) -> dict[str, Any]:
        return {
            "operation": operation,
            "idempotencyKey": f"fixture:{run_key}:{operation.lower()}",
            "runId": f"fixture-{run_key}",
            "correlationId": ids["correlationId"],
            "occurredAt": occurred_at,
            **body,
        }

    commands = [
        envelope(
            "CREATE_FORECAST",
            {
                "forecast": {
                    "forecastId": ids["forecastId"],
                    "forecastCode": f"FC-{code_suffix}",
                    "horizonStart": horizon_start.isoformat(),
                    "horizonEnd": horizon_end.isoformat(),
                    "bucketType": "DAY",
                    "modelRef": "ROTATING_TEST_DEMAND_V1",
                    "baselineSha256": sha256(
                        {"runKey": run_key, "scenario": scenario["scenarioCode"]}
                    ),
                    "points": [
                        {
                            "canonicalSkuId": sku,
                            "warehouseId": warehouse,
                            "bucketStart": horizon_start.isoformat(),
                            "forecastQuantity": forecast_quantity,
                            "lowerQuantity": str(
                                max(Decimal("0"), Decimal(forecast_quantity) * Decimal("0.8"))
                            ),
                            "upperQuantity": str(
                                Decimal(forecast_quantity) * Decimal("1.2")
                            ),
                            "uomCode": uom,
                        }
                    ],
                }
            },
        ),
        envelope(
            "PUBLISH_FORECAST",
            {"forecast": {"forecastId": ids["forecastId"], "expectedVersion": 1}},
        ),
        envelope(
            "CREATE_SUPPLY_PLAN",
            {
                "supplyPlan": {
                    "planId": ids["planId"],
                    "planCode": f"SP-{code_suffix}",
                    "demandForecastId": ids["forecastId"],
                    "horizonStart": horizon_start.isoformat(),
                    "horizonEnd": horizon_end.isoformat(),
                    "targetServiceLevelBasisPoints": 9500,
                    "budgetAmountMinor": int(scenario.get("budgetAmountMinor", 1_000_000)),
                    "currencyCode": "CNY",
                    "constraintsSha256": sha256(
                        {"capacity": capacity, "budget": scenario.get("budgetAmountMinor", 1_000_000)}
                    ),
                }
            },
        ),
        envelope(
            "EVALUATE_PLAN_SCENARIO",
            {
                "planScenario": {
                    "scenarioId": ids["scenarioId"],
                    "planId": ids["planId"],
                    "scenarioCode": str(scenario["scenarioCode"]),
                    "canonicalSkuId": sku,
                    "warehouseId": warehouse,
                    "forecastQuantity": forecast_quantity,
                    "safetyStockQuantity": safety_stock,
                    "onHandQuantity": on_hand,
                    "inboundQuantity": inbound,
                    "capacityQuantity": capacity,
                    "minimumOrderQuantity": minimum_order,
                    "unitCostMinor": unit_cost_minor,
                    "uomCode": uom,
                    "parametersSha256": sha256(
                        {
                            "forecast": forecast_quantity,
                            "safetyStock": safety_stock,
                            "onHand": on_hand,
                            "inbound": inbound,
                            "capacity": capacity,
                        }
                    ),
                }
            },
        ),
        envelope(
            "SELECT_PLAN_SCENARIO",
            {
                "planScenario": {
                    "scenarioId": ids["scenarioId"],
                    "expectedVersion": 1,
                    "selectedByPrincipalId": "AI_SUPPLY_PLANNER",
                }
            },
        ),
        envelope(
            "APPROVE_SUPPLY_PLAN",
            {
                "supplyPlan": {
                    "planId": ids["planId"],
                    "expectedVersion": 1,
                    "approverPrincipalId": "AI_SUPPLY_PLANNER",
                }
            },
        ),
        envelope(
            "CREATE_REPLENISHMENT",
            {
                "replenishment": {
                    "recommendationId": ids["recommendationId"],
                    "planId": ids["planId"],
                    "canonicalSkuId": sku,
                    "warehouseId": warehouse,
                    "suggestedQuantity": suggested_quantity,
                    "uomCode": uom,
                    "needByDate": horizon_start.isoformat(),
                    "reasonCode": "ROTATING_TEST_DEMAND",
                }
            },
        ),
        envelope(
            "DECIDE_REPLENISHMENT",
            {
                "replenishment": {
                    "recommendationId": ids["recommendationId"],
                    "expectedVersion": 1,
                    "decision": "APPROVED",
                    "decisionPrincipalId": "AI_SUPPLY_PLANNER",
                }
            },
        ),
        envelope(
            "PROPOSE_REPLENISHMENT_EXECUTION",
            {
                "replenishmentExecutionProposal": {
                    "proposalId": ids["proposalId"],
                    "recommendationId": ids["recommendationId"],
                    "expectedRecommendationVersion": 2,
                    "targetType": scenario["targetType"],
                    "mappingEvidenceSha256": scenario["mappingEvidenceSha256"],
                    "supplierId": scenario.get("supplierId"),
                    "accountId": scenario.get("accountId"),
                    "erpProductId": scenario.get("erpProductId"),
                    "erpProductUnitId": scenario.get("erpProductUnitId"),
                    "unitCostMinor": scenario.get("unitCostMinor"),
                    "taxPercent": scenario.get("taxPercent"),
                    "sourceWarehouseId": scenario.get("sourceWarehouseId"),
                    "targetWarehouseId": scenario.get("targetWarehouseId"),
                    "wmsSkuId": scenario.get("wmsSkuId"),
                    "proposedByPrincipalId": "AI_SUPPLY_PLANNER",
                    "policyCode": "ROTATING_REPLENISHMENT_EXECUTION_V1",
                    "policySha256": sha256(
                        {
                            "scenarioCode": scenario["scenarioCode"],
                            "targetType": scenario["targetType"],
                            "mappingEvidenceSha256": scenario["mappingEvidenceSha256"],
                        }
                    ),
                }
            },
        ),
    ]
    return commands, ids


class SupplyPlanningClient:
    def __init__(self, base_url: str, access_token: str, tenant_id: int):
        self.endpoint = base_url.rstrip("/") + "/admin-api/cloudmold/supply-planning/command"
        self.access_token = access_token
        self.tenant_id = tenant_id

    def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.endpoint,
            data=canonical_json(command).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "tenant-id": str(self.tenant_id),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{command['operation']} HTTP {error.code}: {detail}") from error
        if payload.get("code") != 0:
            raise RuntimeError(
                f"{command['operation']} rejected: "
                f"{payload.get('msg') or payload.get('message') or payload}"
            )
        return payload["data"]

    def get_wms_inventory_quantity(self, warehouse_id: int, sku_id: int) -> Decimal:
        query = urllib.parse.urlencode({"warehouseId": warehouse_id})
        endpoint = (
            self.endpoint.removesuffix("/cloudmold/supply-planning/command")
            + f"/wms/inventory/list?{query}"
        )
        request = urllib.request.Request(
            endpoint,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "tenant-id": str(self.tenant_id),
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"WMS inventory HTTP {error.code}: {detail}"
            ) from error
        if payload.get("code") != 0:
            raise RuntimeError(
                f"WMS inventory rejected: "
                f"{payload.get('msg') or payload.get('message') or payload}"
            )
        rows = payload.get("data") or []
        matches = [
            row for row in rows
            if int(row.get("skuId", -1)) == sku_id
            and int(row.get("warehouseId", -1)) == warehouse_id
        ]
        if len(matches) > 1:
            raise RuntimeError(
                f"WMS inventory returned duplicate rows for warehouse={warehouse_id}, sku={sku_id}"
            )
        return Decimal(str(matches[0].get("quantity", "0"))) if matches else Decimal("0")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a rotating READY replenishment execution proposal through stable APIs."
    )
    parser.add_argument("--base-url", default=os.getenv("CLOUDMOLD_BASE_URL", "http://127.0.0.1:48080"))
    parser.add_argument("--access-token", default=os.getenv("CLOUDMOLD_ACCESS_TOKEN"))
    parser.add_argument("--tenant-id", type=int, default=int(os.getenv("CLOUDMOLD_TENANT_ID", "162")))
    parser.add_argument("--scenario-file", type=Path, required=True)
    parser.add_argument("--business-date", type=dt.date.fromisoformat, default=dt.date.today())
    parser.add_argument("--run-key")
    parser.add_argument("--allow-single-scenario", action="store_true")
    parser.add_argument(
        "--source-inventory-quantity",
        type=Decimal,
        help="Governed WMS preflight result; must be paired with --target-inventory-quantity",
    )
    parser.add_argument(
        "--target-inventory-quantity",
        type=Decimal,
        help="Governed WMS preflight result; must be paired with --source-inventory-quantity",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.access_token:
        print("CLOUDMOLD_ACCESS_TOKEN or --access-token is required", file=sys.stderr)
        return 2
    document = json.loads(args.scenario_file.read_text(encoding="utf-8"))
    scenario = choose_scenario(
        document, args.business_date, allow_single_scenario=args.allow_single_scenario
    )
    run_key = args.run_key or (
        f"{args.business_date.isoformat()}-{scenario['scenarioCode']}"
    )
    client = SupplyPlanningClient(args.base_url, args.access_token, args.tenant_id)
    inventory_preflight: dict[str, str] = {}
    if scenario["targetType"] == "TRANSFER_REQUEST":
        supplied_quantities = (
            args.source_inventory_quantity is not None,
            args.target_inventory_quantity is not None,
        )
        if supplied_quantities[0] != supplied_quantities[1]:
            raise ValueError(
                "source and target inventory quantities must be supplied together"
            )
        if all(supplied_quantities):
            source_quantity = args.source_inventory_quantity
            target_quantity = args.target_inventory_quantity
            preflight_transport = "GOVERNED_INPUT"
        else:
            source_quantity = client.get_wms_inventory_quantity(
                int(scenario["sourceWarehouseId"]), int(scenario["wmsSkuId"])
            )
            target_quantity = client.get_wms_inventory_quantity(
                int(scenario["targetWarehouseId"]), int(scenario["wmsSkuId"])
            )
            preflight_transport = "ADMIN_API"
        scenario, inventory_preflight = adapt_transfer_scenario(
            scenario, source_quantity, target_quantity
        )
        inventory_preflight["transport"] = preflight_transport
    commands, ids = build_commands(args.tenant_id, args.business_date, run_key, scenario)
    outcomes = [client.execute(command) for command in commands]
    print(
        json.dumps(
            {
                "businessDate": args.business_date.isoformat(),
                "scenarioCode": scenario["scenarioCode"],
                "canonicalSkuId": scenario["canonicalSkuId"],
                "canonicalWarehouseId": scenario["canonicalWarehouseId"],
                "inventoryPreflight": inventory_preflight or None,
                "recommendationId": ids["recommendationId"],
                "proposalId": ids["proposalId"],
                "proposalStatus": outcomes[-1]["status"],
                "operations": [
                    {
                        "operation": command["operation"],
                        "aggregateId": outcome["aggregateId"],
                        "status": outcome["status"],
                        "duplicate": outcome.get("duplicate", False),
                    }
                    for command, outcome in zip(commands, outcomes)
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
