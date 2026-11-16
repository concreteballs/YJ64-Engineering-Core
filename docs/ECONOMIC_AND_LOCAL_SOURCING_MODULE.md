# Shared Economic & Local Sourcing Module

## Purpose

The economic pack is a cross-cutting service used by every discipline pack. It compares the total local cost of buying a finished component against sourcing a bill of materials and assembling it, with the objective of finding the lowest-cost feasible option for a declared destination.

The same contracts are intended for engineering agents and a future trade/procurement agent. The economic pack owns cost normalization and comparison; supplier discovery, live stock checks, checkout and purchasing are separate adapters/agents.

## First executable capability

Package: `yj64_engineering_core.economics`

- `EconomicLocation`: destination or supplier location, ISO country/currency codes and optional coordinates.
- `SupplierOffer`: item/part price, supplier identity, currency, unit, stock, minimum order, lead time, tax-inclusion flag, source URL and observation/validity metadata.
- `ShippingQuote`: supplier-to-destination price, currency, delivery time and optional mass capacity.
- `BillOfMaterialsLine`: part identifier, quantity, unit and mass per unit.
- `AssemblyCost`: explicit labour, tooling, consumables and energy cost.
- `EconomicRequest`: target location, required quantity, tax rate and bounded supplier-combination search.
- `EconomicScreeningEngine`: compares complete-item purchase options with BOM assembly options, groups shipping once per supplier, estimates tax on prices marked tax-exclusive, and sorts by total landed cost with delivery time as a tie-breaker.

All prices in one comparison must use the destination currency. Currency conversion is deliberately not guessed; a future exchange-rate adapter must supply a timestamped rate and provenance. Supplier and shipping data are explicit inputs. The engine does not claim to browse shops, verify current prices, reserve stock or place orders.

## Optimization target

Primary objective: minimize total landed cost for the declared location and quantity, subject to available offers, stock, minimum order quantities, currency compatibility and usable delivery quotes.

Total cost currently includes:
- part or finished-item purchase price;
- estimated tax for prices explicitly marked tax-exclusive;
- one shipping charge per supplier shipment;
- declared assembly labour, tooling, consumables and energy.

The first version does not yet calculate customs/import duties, packaging, insurance, payment fees, returns, warranty risk, repairability, lifecycle cost, carbon impact, local pickup cost or supplier reliability. These must be added as explicit fields rather than hidden multipliers.

## Locality and data freshness

Location is a first-class request field, not a global preference. A request can target a workshop, city, region or country. Coordinates are optional and enable future distance/radius filtering. Each offer should preserve supplier location, source URI, observation timestamp and price validity. An adapter must distinguish:
- physically nearby pickup;
- domestic delivery;
- cross-border delivery;
- import with customs/duty exposure.

No supplier is considered nearby merely because its country matches. Distance and logistics must be sourced or calculated from declared coordinates and actual service coverage.

## Future integration sequence

1. Add explicit tax jurisdiction, tax category, customs and landed-import-cost handling.
2. Add currency conversion with rate timestamp, source and uncertainty.
3. Add distance/radius filtering, local pickup and multiple shipping-service quotes.
4. Add supplier reliability, lead-time confidence, warranty, returns and lifecycle cost.
5. Add supplier search adapters and normalized product/part identity matching.
6. Add quote refresh, price expiry, stock revalidation and comparison history.
7. Expose a read-only procurement recommendation interface to the trade agent; purchasing actions require separate permissions and confirmation.

## Safety and evidence boundary

An inexpensive item is not automatically a valid engineering substitute. The economic engine does not relax material, dimensional, electrical, structural, safety or compatibility requirements. Engineering packs must first identify technically acceptable candidates; economics ranks only those candidates. Unknown costs remain unknown and are not silently set to zero.
