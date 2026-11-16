"""Shared economic and procurement discipline pack."""
from .catalog import CatalogSearchResult, MouserSearchAdapter
from .agent import AgentSourcingPlan, AgentSourcingRequest, TechnicalRequirement, plan_agent_request
from .discovery import (
    DEFAULT_SOURCING_CATEGORIES, LocationSelection, LocationSelectionMode,
    MarketScope, SourcingCategory, SupplierSearchPlanner, SupplierSearchTask,
)
from .sourcing import (
    AssemblyCost,
    BillOfMaterialsLine,
    EconomicLocation,
    EconomicOption,
    EconomicReport,
    EconomicRequest,
    EconomicScreeningEngine,
    ShippingQuote,
    SupplierOffer,
)

ECONOMICS_PACK_ID = "economic-sourcing"
ECONOMICS_PACK_VERSION = "0.1.0"

__all__ = [
    "ECONOMICS_PACK_ID", "ECONOMICS_PACK_VERSION", "CatalogSearchResult", "MouserSearchAdapter",
    "AgentSourcingPlan", "AgentSourcingRequest", "TechnicalRequirement", "plan_agent_request",
    "DEFAULT_SOURCING_CATEGORIES", "LocationSelection", "LocationSelectionMode",
    "MarketScope", "SourcingCategory", "SupplierSearchPlanner", "SupplierSearchTask", "AssemblyCost",
    "BillOfMaterialsLine", "EconomicLocation", "EconomicOption",
    "EconomicReport", "EconomicRequest", "EconomicScreeningEngine",
    "ShippingQuote", "SupplierOffer",
]
