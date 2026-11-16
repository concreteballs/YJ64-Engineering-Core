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
- `EconomicRequest`: target location, required quantity, tax rate, optional maximum supplier radius and bounded supplier-combination search.
- `EconomicScreeningEngine`: compares complete-item purchase options with BOM assembly options, groups shipping once per supplier, estimates tax on prices marked tax-exclusive, reports supplier distance when coordinates are known, supports a maximum local radius, and sorts by total landed cost with delivery time and distance as tie-breakers.

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

Location is a first-class request field, not a global preference. A request can target a workshop, city, region or country. Coordinates are optional; when present the engine calculates great-circle supplier distance. A request may set `maximum_supplier_distance_km` to exclude suppliers outside a local radius. If a radius is requested but coordinates are missing, that offer is excluded with an explicit warning. A shipping quote also identifies its service type (delivery, courier, freight or pickup). Each offer should preserve supplier location, source URI, observation timestamp and price validity. An adapter must distinguish:
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


## First supplier catalog adapter — Mouser Search API

An additive, read-only adapter is implemented in `src/yj64_engineering_core/economics/catalog.py`:

- `MouserSearchAdapter` uses the documented Mouser Search API keyword endpoint and requires an API key supplied by the runtime. Never commit the key to the repository; store it in the deployment secret store and inject it at runtime.
- The adapter maps Mouser part numbers, product URLs, availability text, stock quantity when the response explicitly states a number, lead time with recognized units, minimum order and price breaks into provenance-bearing `SupplierOffer` records.
- Price tiers remain separate offers so the economic engine can compare the quantity threshold with the requested BOM quantity. European decimal/thousands separators are normalized. Ambiguous dollar symbols and currency mismatches are rejected rather than guessed.
- Supplier location, expected currency and tax-inclusion treatment are explicit caller inputs. The adapter does not invent a warehouse address, infer delivery cost, convert currencies, or submit carts/orders. A valid destination shipping quote is still required before a complete landed-cost option can rank.
- The adapter is tested with a deterministic fake HTTP transport; the tests do not claim that a live Mouser API key or account has been exercised.

Official API information: [Mouser API Hub](https://www.mouser.es/es/api-hub/) and [Search API documentation](https://eu.mouser.com/en/api-search/). Mouser documents product availability and pricing access, API-key registration, and limits of up to 50 results per call, 30 calls per minute and 1,000 calls per day.

## Global location selection and multi-market discovery

The destination is selected at runtime by the user; it is not a deployment default or a hard-coded city.

- **Map:** the user selects a point on the map. The page exports coordinates and selection provenance.
- **GPS:** the user explicitly presses the GPS button; only then does the browser request location permission. The page exports coordinates and records GPS provenance.

The executable contract is `LocationSelection` in `economics/discovery.py`. The map/GPS page is implemented in the repository root `index.html`. Reverse geocoding and currency resolution are not yet implemented; the agent/API request currently supplies the resolved country and currency.

SupplierSearchPlanner creates separate search tasks for every requested category and four market scopes:

1. **Local radius** around the selected destination (default planning radius: 150 km; configurable).
2. **Domestic** suppliers elsewhere in the destination country.
3. **International** suppliers worldwide outside the destination country and the separately tracked China scope.
4. **China** — a dedicated global search scope for Chinese manufacturers, wholesalers and marketplaces.

The default taxonomy separates chemicals/reagents, polymers/elastomers/resins, metals/alloys, composites, electronics, mechanical parts, fasteners, motors/actuators, sensors/control, cables/power, ceramics/thermal materials, and manufacturing services/equipment. The engineering agent may instead define task-specific categories and exact search terms; the user does not manually choose procurement categories.

The planner creates typed tasks; it does not itself crawl websites or claim current prices. Actual supplier connectors must execute those tasks and normalize each result into SupplierOffer with a product identity, supplier location, currency, stock semantics, MOQ, source URL and observation timestamp. Chinese and other cross-border offers must additionally provide shipping coverage and a landed-import estimate (freight, customs, import VAT, platform/payment fees where applicable). A low catalogue price without a credible delivered-cost quote cannot win the comparison.

China is not automatically excluded for distance. It is compared as a separate sourcing market and ranked by total landed cost, delivery time, technical acceptance and evidence quality. Local suppliers can still win when pickup, short lead time, lower freight or easier returns outweigh a lower overseas unit price.

## Next adapter sequence

1. Add a validated quote-import format for local supplier web listings and written quotations, including source URL/file, observation time, VAT treatment, delivery/pickup and quote validity.
2. Add separate shipping quote adapters or structured manual capture; supplier catalog price is not a shipping price.
3. Confirm actual supplier locations and delivery coverage before enabling local-radius ranking.
4. Add other catalog APIs (for example, electronics distributors) only after their API terms, response currency and stock semantics are verified.


## Destination picker prototype

The repository root now contains `index.html`, a mobile-friendly static destination-selection page. It provides an OpenStreetMap/Leaflet map click picker and an explicit GPS button; the browser location prompt is requested only after the user presses that button. It lets the user choose sourcing categories and local/domestic/international/China market scopes, set a local radius, and generate/copy a versioned JSON discovery request. No GPS location is collected automatically and no purchase action is enabled.

The page is deliberately limited to destination selection. It outputs only coordinates and selection provenance; it does not ask the user to choose categories, budget, technical limits or search markets. Those parameters belong to the engineering agent.


## Agent-authored sourcing contract and API

The engineering agent owns sourcing decisions. `economics/agent.py` accepts an agent ID and task description plus agent-authored category labels/search terms, market scopes, required quantity and unit, typed technical property bounds, maximum total budget and currency, local search radius and maximum delivery time. Budget currency must match the destination currency; explicit FX conversion is required before comparison. Local-radius searches require destination coordinates. GPS origin is accepted only with an explicit permission flag.

The Vercel function `api/discovery.py` exposes authenticated `POST /api/discovery`. Configure `YJ64_AGENT_API_TOKEN` in Vercel Environment Variables; do not put it in browser code or commit it. The endpoint validates the JSON schema and returns a typed category × market plan. It is currently planning-only: it does not query suppliers, store a durable job, or place orders. See [AGENT_SOURCING_API.md](AGENT_SOURCING_API.md) for the full contract and example. The destination page outputs only the location context for the agent; it no longer asks the user to set procurement parameters.


## China catalogue adapter — 1688

An optional read-only adapter, `Nexscope1688SearchAdapter`, now connects to Nexscope's documented 1688 product-search endpoint. It maps product/listing IDs, supplier/shop identity, listing URLs, wholesale price, currency, MOQ and quantity price breaks into `SupplierOffer` records. It preserves CNY rather than silently converting it and does not invent stock or delivery days when the source omits units. Supplier coordinates, destination freight, import VAT/customs and FX conversion remain separate inputs.

**External service and cost gate:** Nexscope is a third-party API, not the official 1688 platform API. Its current documentation states an estimated cost of 10–19 credits per search call. The adapter therefore requires an explicit `credit_budget_per_call` of at least 19 as well as an API key; no API request is made during tests or deployment setup. Configure credentials only in a secret store. Do not enable calls until a credit budget is deliberately authorized. Nexscope's API documentation does not specify source-data freshness, so returned records are discovery candidates, not guaranteed live inventory or binding quotations.

References: [Nexscope 1688 Product Search API documentation](https://www.nexscope.ai/api-docs/1688-product-search). Alibaba's official Open Platform requires developer registration, application approval and API permissions; seller business data can require seller authorization. That official platform should be integrated only against the approved buyer/product scope, not assumed to be an unrestricted public product-search API: [Alibaba.com Open Platform getting started](https://openapi.alibaba.com/doc/doc.htm?docId=118729&nodeId=27493) and [Taobao Global Open Platform authorization guide](https://developer.alibaba.com/docs/doc.htm?articleId=121120&docType=1&source=search&treeId=735).
