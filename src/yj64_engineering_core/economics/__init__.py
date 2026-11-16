"""Shared economic and procurement discipline pack."""
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
    "ECONOMICS_PACK_ID", "ECONOMICS_PACK_VERSION", "AssemblyCost",
    "BillOfMaterialsLine", "EconomicLocation", "EconomicOption",
    "EconomicReport", "EconomicRequest", "EconomicScreeningEngine",
    "ShippingQuote", "SupplierOffer",
]
