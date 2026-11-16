"""Location selection and multi-market supplier discovery planning.

This module creates search tasks only. It does not geolocate the user,
scrape supplier sites, verify stock, or place orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .sourcing import EconomicLocation, _number, _text


class LocationSelectionMode(str, Enum):
    MAP = "map"
    GPS = "gps"
    MANUAL = "manual"


class MarketScope(str, Enum):
    LOCAL = "local"
    DOMESTIC = "domestic"
    INTERNATIONAL = "international"
    CHINA = "china"


@dataclass(frozen=True, slots=True)
class LocationSelection:
    """Destination selected by map, explicitly authorized GPS, or manual entry."""

    destination: EconomicLocation
    mode: LocationSelectionMode
    gps_permission_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.mode, LocationSelectionMode):
            raise TypeError("mode must be a LocationSelectionMode")
        has_coordinates = self.destination.latitude is not None
        if self.mode is LocationSelectionMode.MAP and not has_coordinates:
            raise ValueError("map selection requires destination coordinates")
        if self.mode is LocationSelectionMode.GPS:
            if not self.gps_permission_granted:
                raise ValueError("GPS mode requires explicit user permission")
            if not has_coordinates:
                raise ValueError("GPS selection requires destination coordinates")
        if self.mode is not LocationSelectionMode.GPS and self.gps_permission_granted:
            raise ValueError("GPS permission flag is only valid for GPS mode")


@dataclass(frozen=True, slots=True)
class SourcingCategory:
    category_id: str
    label: str
    search_terms: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.category_id, "category_id")
        _text(self.label, "label")
        if not self.search_terms or any(not term.strip() for term in self.search_terms):
            raise ValueError("each sourcing category requires non-empty search terms")


@dataclass(frozen=True, slots=True)
class SupplierSearchTask:
    category_id: str
    category_label: str
    market_scope: MarketScope
    destination_location_id: str
    destination_country_code: str
    currency: str
    search_terms: tuple[str, ...]
    radius_km: float | None
    requires_ship_to_destination: bool
    notes: tuple[str, ...]


DEFAULT_SOURCING_CATEGORIES: tuple[SourcingCategory, ...] = (
    SourcingCategory("chemicals", "Chemicals and reagents", ("industrial chemicals", "chemical reagents", "laboratory chemicals")),
    SourcingCategory("polymers", "Polymers, elastomers and resins", ("engineering polymers", "elastomers", "resins", "conductive polymers")),
    SourcingCategory("metals", "Metals and alloys", ("metal stock", "steel", "aluminium alloy", "copper alloy")),
    SourcingCategory("composites", "Composites and reinforcements", ("composite materials", "carbon fibre", "glass fibre", "reinforcement fabrics")),
    SourcingCategory("electronics", "Electronic components", ("electronic components", "sensors", "power electronics", "connectors")),
    SourcingCategory("mechanical_parts", "Mechanical parts", ("machined parts", "shafts", "gears", "brackets", "bearings")),
    SourcingCategory("fasteners", "Fasteners and hardware", ("fasteners", "bolts", "screws", "nuts", "washers")),
    SourcingCategory("motors_actuators", "Motors and actuators", ("electric motors", "linear actuators", "servos", "solenoids")),
    SourcingCategory("sensors_control", "Sensors and control systems", ("position sensors", "force sensors", "controllers", "encoders")),
    SourcingCategory("cables_power", "Cables and electrical materials", ("cables", "wire", "electrical insulation", "battery components")),
    SourcingCategory("ceramics_thermal", "Ceramics and thermal materials", ("technical ceramics", "refractory materials", "thermal insulation")),
    SourcingCategory("manufacturing", "Manufacturing services and equipment", ("CNC machining", "3D printing service", "sheet metal fabrication", "manufacturing equipment")),
)


class SupplierSearchPlanner:
    """Build category-specific local, domestic, worldwide and China search tasks."""

    version = "0.1.0"

    def __init__(self, local_radius_km: float = 150.0) -> None:
        _number(local_radius_km, "local_radius_km", 0.1)
        self.local_radius_km = float(local_radius_km)

    def build_plan(
        self,
        selection: LocationSelection,
        categories: Iterable[SourcingCategory] | None = None,
    ) -> tuple[SupplierSearchTask, ...]:
        selected_categories = tuple(categories or DEFAULT_SOURCING_CATEGORIES)
        if not selected_categories:
            raise ValueError("at least one sourcing category is required")
        if len({category.category_id for category in selected_categories}) != len(selected_categories):
            raise ValueError("sourcing category IDs must be unique")

        destination = selection.destination
        tasks: list[SupplierSearchTask] = []
        scopes = (
            (MarketScope.LOCAL, self.local_radius_km, False,
             ("Find suppliers physically near the selected destination; calculate distance from verified supplier coordinates.",
              "Include pickup and local delivery only when explicitly offered.")),
            (MarketScope.DOMESTIC, None, True,
             ("Search the destination country beyond the local radius.",
              "Compare domestic shipping, tax and delivery terms.")),
            (MarketScope.INTERNATIONAL, None, True,
             ("Search worldwide suppliers outside the destination country and China.",
              "Require shipping coverage, import charges and currency normalization.")),
            (MarketScope.CHINA, None, True,
             ("Search Chinese manufacturers, wholesalers and marketplaces explicitly.",
              "Include platform fees, international freight, customs, import VAT, MOQ, quality evidence and lead time.")),
        )
        for category in selected_categories:
            for scope, radius, requires_shipping, notes in scopes:
                tasks.append(SupplierSearchTask(
                    category_id=category.category_id,
                    category_label=category.label,
                    market_scope=scope,
                    destination_location_id=destination.location_id,
                    destination_country_code=destination.country_code,
                    currency=destination.currency,
                    search_terms=category.search_terms,
                    radius_km=radius,
                    requires_ship_to_destination=requires_shipping,
                    notes=notes,
                ))
        return tuple(tasks)
