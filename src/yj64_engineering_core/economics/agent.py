"""Agent-authored sourcing request contract.

The engineering agent chooses categories, quantities, technical limits, budget,
markets and delivery urgency. The destination is supplied by the user-selected
map/GPS/manual location context. This module plans searches; it does not place
orders or claim to retrieve live offers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .discovery import (
    DEFAULT_SOURCING_CATEGORIES,
    LocationSelection,
    LocationSelectionMode,
    MarketScope,
    SourcingCategory,
    SupplierSearchPlanner,
    SupplierSearchTask,
)
from .sourcing import EconomicLocation, _number, _text


@dataclass(frozen=True, slots=True)
class TechnicalRequirement:
    property_name: str
    unit: str
    minimum: float | None = None
    maximum: float | None = None

    def __post_init__(self) -> None:
        _text(self.property_name, "property_name")
        _text(self.unit, "unit")
        if self.minimum is None and self.maximum is None:
            raise ValueError("technical requirement needs a minimum or maximum")
        if self.minimum is not None:
            _number(self.minimum, "minimum")
        if self.maximum is not None:
            _number(self.maximum, "maximum")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("technical requirement minimum cannot exceed maximum")


@dataclass(frozen=True, slots=True)
class AgentSourcingRequest:
    request_id: str
    agent_id: str
    task_description: str
    destination: EconomicLocation
    location_mode: LocationSelectionMode
    categories: tuple[SourcingCategory, ...]
    market_scopes: tuple[MarketScope, ...]
    required_quantity: float
    quantity_unit: str
    technical_requirements: tuple[TechnicalRequirement, ...] = ()
    maximum_total_budget: float | None = None
    budget_currency: str | None = None
    local_radius_km: float = 150.0
    maximum_delivery_days: float | None = None
    gps_permission_granted: bool = False

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        _text(self.agent_id, "agent_id")
        _text(self.task_description, "task_description")
        _text(self.quantity_unit, "quantity_unit")
        _number(self.required_quantity, "required_quantity", 0.0000001)
        _number(self.local_radius_km, "local_radius_km", 0.1)
        if not self.categories:
            raise ValueError("agent must specify at least one sourcing category")
        if len({c.category_id for c in self.categories}) != len(self.categories):
            raise ValueError("category IDs must be unique")
        if not self.market_scopes:
            raise ValueError("agent must specify at least one market scope")
        if MarketScope.LOCAL in self.market_scopes and self.destination.latitude is None:
            raise ValueError("local-radius sourcing requires destination coordinates")
        if len(set(self.market_scopes)) != len(self.market_scopes):
            raise ValueError("market scopes must be unique")
        if self.maximum_total_budget is not None:
            _number(self.maximum_total_budget, "maximum_total_budget")
            if self.budget_currency != self.destination.currency:
                raise ValueError("budget currency must match destination currency; convert explicitly first")
        elif self.budget_currency is not None:
            raise ValueError("budget_currency requires maximum_total_budget")
        if self.maximum_delivery_days is not None:
            _number(self.maximum_delivery_days, "maximum_delivery_days", 0.0000001)
        LocationSelection(
            self.destination,
            self.location_mode,
            gps_permission_granted=self.gps_permission_granted,
        )

    def build_search_plan(self) -> tuple[SupplierSearchTask, ...]:
        selection = LocationSelection(
            self.destination,
            self.location_mode,
            gps_permission_granted=self.gps_permission_granted,
        )
        all_tasks = SupplierSearchPlanner(self.local_radius_km).build_plan(
            selection, self.categories
        )
        return tuple(task for task in all_tasks if task.market_scope in self.market_scopes)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AgentSourcingRequest":
        if not isinstance(payload, dict):
            raise TypeError("request body must be a JSON object")
        allowed = {
            "schema", "request_id", "agent_id", "task_description", "destination",
            "location_mode", "gps_permission_granted", "categories", "market_scopes",
            "required_quantity", "quantity_unit", "technical_requirements",
            "maximum_total_budget", "budget_currency", "local_radius_km",
            "maximum_delivery_days",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise ValueError(f"unknown request fields: {', '.join(sorted(unknown))}")
        if payload.get("schema") != "yj64.agent-sourcing-request.v1":
            raise ValueError("unsupported or missing schema")
        destination_data = payload.get("destination")
        if not isinstance(destination_data, dict):
            raise ValueError("destination must be an object")
        destination = EconomicLocation(**destination_data)
        category_data = payload.get("categories")
        if not isinstance(category_data, list):
            raise ValueError("categories must be a list")
        if any(not isinstance(item, dict) for item in category_data):
            raise ValueError("each category must be an object")
        categories_list = []
        for item in category_data:
            terms = item.get("search_terms")
            if not isinstance(terms, list) or not all(isinstance(term, str) for term in terms):
                raise ValueError("category search_terms must be a list of strings")
            categories_list.append(SourcingCategory(
                category_id=item["category_id"],
                label=item["label"],
                search_terms=tuple(terms),
            ))
        categories = tuple(categories_list)
        requirement_data = payload.get("technical_requirements", [])
        if not isinstance(requirement_data, list):
            raise ValueError("technical_requirements must be a list")
        requirements = tuple(TechnicalRequirement(**item) for item in requirement_data)
        return cls(
            request_id=payload["request_id"],
            agent_id=payload["agent_id"],
            task_description=payload["task_description"],
            destination=destination,
            location_mode=LocationSelectionMode(payload["location_mode"]),
            gps_permission_granted=payload.get("gps_permission_granted", False),
            categories=categories,
            market_scopes=tuple(MarketScope(value) for value in payload["market_scopes"]),
            required_quantity=payload["required_quantity"],
            quantity_unit=payload["quantity_unit"],
            technical_requirements=requirements,
            maximum_total_budget=payload.get("maximum_total_budget"),
            budget_currency=payload.get("budget_currency"),
            local_radius_km=payload.get("local_radius_km", 150.0),
            maximum_delivery_days=payload.get("maximum_delivery_days"),
        )


@dataclass(frozen=True, slots=True)
class AgentSourcingPlan:
    request_id: str
    agent_id: str
    tasks: tuple[SupplierSearchTask, ...]
    technical_requirements: tuple[TechnicalRequirement, ...]
    required_quantity: float
    quantity_unit: str
    maximum_total_budget: float | None
    budget_currency: str | None
    maximum_delivery_days: float | None


def plan_agent_request(request: AgentSourcingRequest) -> AgentSourcingPlan:
    return AgentSourcingPlan(
        request_id=request.request_id,
        agent_id=request.agent_id,
        tasks=request.build_search_plan(),
        technical_requirements=request.technical_requirements,
        required_quantity=request.required_quantity,
        quantity_unit=request.quantity_unit,
        maximum_total_budget=request.maximum_total_budget,
        budget_currency=request.budget_currency,
        maximum_delivery_days=request.maximum_delivery_days,
    )
