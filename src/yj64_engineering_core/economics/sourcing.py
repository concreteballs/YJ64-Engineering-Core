"""Location-aware economic screening for materials, parts and assemblies.

All commercial offers are supplied by a caller or a future supplier adapter.
This module does not scrape stores or invent current market prices.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Sequence


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _number(value: float, name: str, minimum: float = 0.0) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    if not math.isfinite(float(value)) or value < minimum:
        raise ValueError(f"{name} must be finite and >= {minimum}")


@dataclass(frozen=True, slots=True)
class EconomicLocation:
    location_id: str
    name: str
    country_code: str
    currency: str
    latitude: float | None = None
    longitude: float | None = None
    region_code: str | None = None

    def __post_init__(self) -> None:
        for name in ("location_id", "name", "country_code", "currency"):
            _text(getattr(self, name), name)
        if len(self.country_code) != 2 or len(self.currency) != 3:
            raise ValueError("country_code must be ISO-3166 alpha-2 and currency ISO-4217 alpha-3")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        if self.latitude is not None:
            _number(self.latitude, "latitude", -90.0)
            _number(self.longitude, "longitude", -180.0)
            if self.latitude > 90 or self.longitude > 180:
                raise ValueError("coordinates are outside geographic bounds")


@dataclass(frozen=True, slots=True)
class SupplierOffer:
    offer_id: str
    item_id: str
    supplier_id: str
    supplier_name: str
    supplier_location: EconomicLocation
    unit_price: float
    currency: str
    unit: str
    stock_quantity: float | None = None
    minimum_order_quantity: float = 1.0
    lead_time_days: float | None = None
    tax_included: bool = False
    source_uri: str | None = None
    observed_at: str | None = None
    price_valid_until: str | None = None

    def __post_init__(self) -> None:
        for name in ("offer_id", "item_id", "supplier_id", "supplier_name", "currency", "unit"):
            _text(getattr(self, name), name)
        _number(self.unit_price, "unit_price")
        _number(self.minimum_order_quantity, "minimum_order_quantity", 0.0000001)
        if self.currency != self.supplier_location.currency:
            raise ValueError("offer currency must match supplier location currency")
        if self.stock_quantity is not None:
            _number(self.stock_quantity, "stock_quantity")
        if self.lead_time_days is not None:
            _number(self.lead_time_days, "lead_time_days")
        if not isinstance(self.tax_included, bool):
            raise TypeError("tax_included must be boolean")


@dataclass(frozen=True, slots=True)
class ShippingQuote:
    supplier_id: str
    destination_location_id: str
    cost: float
    currency: str
    delivery_days: float
    source_uri: str | None = None
    maximum_shipment_mass_kg: float | None = None
    observed_at: str | None = None

    def __post_init__(self) -> None:
        for name in ("supplier_id", "destination_location_id", "currency"):
            _text(getattr(self, name), name)
        _number(self.cost, "shipping cost")
        _number(self.delivery_days, "delivery_days")
        if self.maximum_shipment_mass_kg is not None:
            _number(self.maximum_shipment_mass_kg, "maximum_shipment_mass_kg", 0.0000001)


@dataclass(frozen=True, slots=True)
class BillOfMaterialsLine:
    item_id: str
    quantity: float
    unit: str
    mass_per_unit_kg: float = 0.0

    def __post_init__(self) -> None:
        _text(self.item_id, "item_id")
        _text(self.unit, "unit")
        _number(self.quantity, "quantity", 0.0000001)
        _number(self.mass_per_unit_kg, "mass_per_unit_kg")


@dataclass(frozen=True, slots=True)
class AssemblyCost:
    labor_hours: float = 0.0
    labor_rate_per_hour: float = 0.0
    tooling_cost: float = 0.0
    consumables_cost: float = 0.0
    energy_cost: float = 0.0

    def __post_init__(self) -> None:
        for name in ("labor_hours", "labor_rate_per_hour", "tooling_cost", "consumables_cost", "energy_cost"):
            _number(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class EconomicRequest:
    request_id: str
    destination: EconomicLocation
    quantity: float = 1.0
    tax_rate_fraction: float = 0.0
    assembly: AssemblyCost = AssemblyCost()
    maximum_combinations: int = 4096

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        _number(self.quantity, "quantity", 0.0000001)
        _number(self.tax_rate_fraction, "tax_rate_fraction")
        if self.tax_rate_fraction > 1:
            raise ValueError("tax_rate_fraction must be between 0 and 1")
        if isinstance(self.maximum_combinations, bool) or not isinstance(self.maximum_combinations, int) or self.maximum_combinations < 1:
            raise ValueError("maximum_combinations must be a positive integer")


@dataclass(frozen=True, slots=True)
class EconomicOption:
    option_id: str
    description: str
    procurement_mode: str
    currency: str
    item_cost: float
    tax_estimate: float
    shipping_cost: float
    assembly_cost: float
    total_landed_cost: float
    supplier_ids: tuple[str, ...]
    supplier_names: tuple[str, ...]
    delivery_days_estimate: float | None
    source_uris: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EconomicReport:
    request_id: str
    destination_location_id: str
    currency: str
    options: tuple[EconomicOption, ...]
    status: str
    warnings: tuple[str, ...]

    @property
    def cheapest(self) -> EconomicOption | None:
        return self.options[0] if self.options else None


class EconomicScreeningEngine:
    """Compare buying a complete item with assembling it from sourced BOM parts."""

    name = "YJ64 location-aware economic screening"
    version = "0.1.0"

    @staticmethod
    def _check_offer(offer: SupplierOffer, request: EconomicRequest) -> str | None:
        if offer.currency != request.destination.currency:
            return f"{offer.offer_id}: currency {offer.currency} differs from destination {request.destination.currency}; convert explicitly first"
        if offer.stock_quantity is not None and offer.stock_quantity < offer.minimum_order_quantity:
            return f"{offer.offer_id}: stock is below minimum order quantity"
        if offer.minimum_order_quantity > request.quantity and offer.stock_quantity is not None and offer.stock_quantity < offer.minimum_order_quantity:
            return f"{offer.offer_id}: minimum order cannot be fulfilled from stated stock"
        return None

    @staticmethod
    def _quote_for(supplier_id: str, destination_id: str, quotes: Sequence[ShippingQuote]) -> ShippingQuote | None:
        matches = [q for q in quotes if q.supplier_id == supplier_id and q.destination_location_id == destination_id]
        return min(matches, key=lambda q: q.cost) if matches else None

    def evaluate(
        self,
        request: EconomicRequest,
        complete_item_id: str,
        complete_item_offers: Sequence[SupplierOffer] = (),
        bill_of_materials: Sequence[BillOfMaterialsLine] = (),
        part_offers: Sequence[SupplierOffer] = (),
        shipping_quotes: Sequence[ShippingQuote] = (),
    ) -> EconomicReport:
        _text(complete_item_id, "complete_item_id")
        options: list[EconomicOption] = []
        warnings: list[str] = []
        currency = request.destination.currency
        assembly_cost = (
            request.assembly.labor_hours * request.assembly.labor_rate_per_hour
            + request.assembly.tooling_cost + request.assembly.consumables_cost
            + request.assembly.energy_cost
        )

        for offer in complete_item_offers:
            if offer.item_id != complete_item_id:
                continue
            issue = self._check_offer(offer, request)
            if issue:
                warnings.append(issue)
                continue
            if offer.stock_quantity is not None and offer.stock_quantity < request.quantity:
                warnings.append(f"{offer.offer_id}: insufficient stock for requested quantity")
                continue
            if offer.minimum_order_quantity > request.quantity:
                warnings.append(f"{offer.offer_id}: quantity is below supplier minimum order")
                continue
            quote = self._quote_for(offer.supplier_id, request.destination.location_id, shipping_quotes)
            if quote is None:
                warnings.append(f"{offer.offer_id}: no shipping quote to destination")
                continue
            if quote.currency != currency:
                warnings.append(f"{offer.offer_id}: shipping currency mismatch")
                continue
            mass = 0.0
            if quote.maximum_shipment_mass_kg is not None and mass > quote.maximum_shipment_mass_kg:
                warnings.append(f"{offer.offer_id}: shipment exceeds quoted mass capacity")
                continue
            items = offer.unit_price * request.quantity
            tax = 0.0 if offer.tax_included else items * request.tax_rate_fraction
            shipping = quote.cost
            lead = max(offer.lead_time_days or 0.0, quote.delivery_days)
            options.append(EconomicOption(
                option_id=f"buy:{offer.offer_id}", description=f"Buy complete item from {offer.supplier_name}",
                procurement_mode="buy_complete", currency=currency, item_cost=items,
                tax_estimate=tax, shipping_cost=shipping, assembly_cost=0.0,
                total_landed_cost=items + tax + shipping, supplier_ids=(offer.supplier_id,),
                supplier_names=(offer.supplier_name,), delivery_days_estimate=lead,
                source_uris=tuple(x for x in (offer.source_uri, quote.source_uri) if x),
                warnings=("Supplier price/tax treatment and shipping quote are supplied inputs, not live-verified market data.",),
            ))

        if bill_of_materials:
            choices: list[list[SupplierOffer]] = []
            valid_bom = True
            for line in bill_of_materials:
                line_offers = []
                for offer in part_offers:
                    if offer.item_id != line.item_id:
                        continue
                    issue = self._check_offer(offer, request)
                    if issue:
                        warnings.append(issue)
                        continue
                    required = line.quantity * request.quantity
                    if offer.stock_quantity is not None and offer.stock_quantity < required:
                        continue
                    if offer.minimum_order_quantity > required:
                        continue
                    line_offers.append(offer)
                if not line_offers:
                    warnings.append(f"{line.item_id}: no compatible supplier offer with sufficient stock and currency")
                    valid_bom = False
                    break
                choices.append(line_offers)
            if valid_bom:
                combinations = math.prod(len(items) for items in choices)
                if combinations > request.maximum_combinations:
                    warnings.append(
                        f"BOM has {combinations} supplier combinations; exceeds search cap "
                        f"{request.maximum_combinations}; no assembled option ranked"
                    )
                else:
                    for combo_index, combo in enumerate(itertools.product(*choices)):
                        selected = tuple(combo)
                        supplier_ids = tuple(sorted({o.supplier_id for o in selected}))
                        shipping_by_supplier: dict[str, ShippingQuote] = {}
                        missing_quote = False
                        for supplier_id in supplier_ids:
                            quote = self._quote_for(supplier_id, request.destination.location_id, shipping_quotes)
                            if quote is None or quote.currency != currency:
                                warnings.append(f"{supplier_id}: no usable shipping quote to destination")
                                missing_quote = True
                                break
                            shipping_by_supplier[supplier_id] = quote
                        if missing_quote:
                            continue
                        supplier_mass: dict[str, float] = {}
                        item_cost = 0.0
                        tax = 0.0
                        lead_days: list[float] = []
                        sources: list[str] = []
                        for line, offer in zip(bill_of_materials, selected):
                            required = line.quantity * request.quantity
                            item_cost += required * offer.unit_price
                            if not offer.tax_included:
                                tax += required * offer.unit_price * request.tax_rate_fraction
                            supplier_mass[offer.supplier_id] = supplier_mass.get(offer.supplier_id, 0.0) + required * line.mass_per_unit_kg
                            if offer.lead_time_days is not None:
                                lead_days.append(offer.lead_time_days)
                            if offer.source_uri:
                                sources.append(offer.source_uri)
                        shipping = 0.0
                        for supplier_id, quote in shipping_by_supplier.items():
                            mass = supplier_mass.get(supplier_id, 0.0)
                            if quote.maximum_shipment_mass_kg is not None and mass > quote.maximum_shipment_mass_kg:
                                missing_quote = True
                                warnings.append(f"{supplier_id}: BOM shipment mass {mass} kg exceeds quoted capacity")
                                break
                            shipping += quote.cost
                            lead_days.append(quote.delivery_days)
                            if quote.source_uri:
                                sources.append(quote.source_uri)
                        if missing_quote:
                            continue
                        supplier_names = tuple(sorted({o.supplier_name for o in selected}))
                        options.append(EconomicOption(
                            option_id=f"assemble:{combo_index + 1}",
                            description="Assemble locally from sourced bill-of-materials parts",
                            procurement_mode="assemble_from_parts", currency=currency,
                            item_cost=item_cost, tax_estimate=tax, shipping_cost=shipping,
                            assembly_cost=assembly_cost,
                            total_landed_cost=item_cost + tax + shipping + assembly_cost,
                            supplier_ids=supplier_ids, supplier_names=supplier_names,
                            delivery_days_estimate=max(lead_days) if lead_days else None,
                            source_uris=tuple(dict.fromkeys(sources)),
                            warnings=("BOM and assembly inputs are caller-supplied; verify compatibility, tooling, labour and taxes.",),
                        ))

        options.sort(key=lambda item: (item.total_landed_cost, item.delivery_days_estimate or float("inf"), item.option_id))
        if not options:
            status = "insufficient_market_data"
            warnings.append("No fully costed procurement route: missing offers, stock, compatible currency or destination shipping quote.")
        else:
            status = "screening_only"
        return EconomicReport(
            request_id=request.request_id, destination_location_id=request.destination.location_id,
            currency=currency, options=tuple(options), status=status,
            warnings=tuple(dict.fromkeys(warnings)),
        )
