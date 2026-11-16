# Agent Sourcing API

## Purpose

The engineering agent, not the end user, defines procurement criteria. An agent should derive the required materials/parts, category, search terms, quantity, technical limits, budget, delivery deadline and relevant markets from its engineering task.

The user supplies only the delivery destination context by selecting a map point or explicitly granting one-time GPS access. The destination context can be passed to the agent as a small JSON object. The agent resolves destination country and currency (using a trusted geocoding/currency source) and constructs the request below.

## Endpoint

- Method: `POST`
- URL: `/api/discovery`
- Authentication: `Authorization: Bearer <YJ64_AGENT_API_TOKEN>`
- Deployment secret: configure `YJ64_AGENT_API_TOKEN` in Vercel Environment Variables. Never commit the token or put it in browser JavaScript.
- Schema: `yj64.agent-sourcing-request.v1`

The endpoint is read-only and currently returns a validated search plan. It does not execute live supplier searches, persist jobs, reserve stock, create carts or place orders.

## Agent-authored request example

```json
{
  "schema": "yj64.agent-sourcing-request.v1",
  "request_id": "muscle-materials-prototype-001",
  "agent_id": "artificial-muscle-design-agent",
  "task_description": "Find candidate dielectric elastomer materials for a low-voltage artificial muscle prototype",
  "destination": {
    "location_id": "user-selected-destination",
    "name": "Workshop destination",
    "country_code": "ES",
    "currency": "EUR",
    "latitude": 36.72,
    "longitude": -4.42
  },
  "location_mode": "map",
  "categories": [
    {
      "category_id": "polymers",
      "label": "Dielectric elastomer polymers",
      "search_terms": ["silicone dielectric elastomer film", "acrylic dielectric elastomer", "high permittivity elastomer"]
    },
    {
      "category_id": "electrodes",
      "label": "Stretchable electrodes",
      "search_terms": ["stretchable conductive electrode", "carbon grease electrode", "conductive elastomer electrode"]
    }
  ],
  "market_scopes": ["local", "domestic", "international", "china"],
  "required_quantity": 2,
  "quantity_unit": "kg",
  "technical_requirements": [
    {"property_name": "dielectric_strength", "unit": "kV/mm", "minimum": 20},
    {"property_name": "elongation_at_break", "unit": "%", "minimum": 100},
    {"property_name": "operating_temperature_max", "unit": "degC", "minimum": 60}
  ],
  "maximum_total_budget": 150,
  "budget_currency": "EUR",
  "local_radius_km": 100,
  "maximum_delivery_days": 30
}
```

The example is illustrative; actual requirements must come from the engineering design and must not be guessed by the procurement module.

## Agent decision responsibilities

The agent chooses:
- category labels and exact search terms, including multiple material/part groups in one request;
- required quantity and units;
- technical property limits and evidence requirements;
- total budget and destination currency;
- delivery deadline;
- which market scopes to search: local, domestic, international and/or China;
- local radius, when local suppliers are relevant.

The user does not manually tune these engineering/procurement parameters in the location page.

## Location context from the map page

The map page emits only destination context, for example:

```json
{
  "schema": "yj64.destination-context.v1",
  "selection_mode": "map",
  "coordinates": {"latitude": 36.72, "longitude": -4.42},
  "permission_scope": "user_selected_map_point"
}
```

For GPS, `selection_mode` is `gps` and the page requests permission only after the user presses the GPS button. The agent must preserve this provenance and must not claim GPS permission if the context came from a map click.

The current endpoint expects the agent to add the resolved country code and currency to `destination`. Automatic reverse geocoding and currency resolution are planned, not yet implemented.

## Response and limitations

A successful response contains the validated request identity and expanded category × market search tasks. It carries technical requirements, quantity, budget and delivery deadline forward for supplier adapters.

The current response status is `planned`, with `execution_mode: planning_only`. It is not a supplier quote or completed search. Live marketplace/distributor connectors, price/stock freshness checks, product identity matching, shipping quotes, customs/import VAT, FX conversion and durable queue execution are follow-up implementation stages.

The endpoint requires an API token and returns 503 until `YJ64_AGENT_API_TOKEN` is configured. No purchasing capability exists in this API.


## Execution boundary

`POST /api/discovery` only validates and plans. A cloud worker may use `AgentSourcingExecutor` after explicit provider registration and a per-run credit ceiling have been configured. The current paid China provider is capped at 19 credits per call; the executor requires a maximum call count and matching credit ceiling. Do not expose the Nexscope API key to the agent or browser. No third-party calls are made by the planning endpoint.
