import unittest

from yj64_engineering_core.economics.agent import (
    AgentSourcingRequest, TechnicalRequirement, plan_agent_request,
)
from yj64_engineering_core.economics.discovery import LocationSelectionMode, MarketScope, SourcingCategory
from yj64_engineering_core.economics.sourcing import EconomicLocation


class AgentSourcingContractTests(unittest.TestCase):
    def setUp(self):
        self.destination = EconomicLocation("dest-1", "Workshop", "ES", "EUR", 36.72, -4.42)
        self.category = SourcingCategory("polymers", "Polymers", ("conductive polymer", "elastomer"))

    def make_request(self, **overrides):
        values = dict(
            request_id="req-1", agent_id="muscle-design-agent",
            task_description="Find a compliant dielectric elastomer for an actuator prototype",
            destination=self.destination, location_mode=LocationSelectionMode.MAP,
            categories=(self.category,),
            market_scopes=(MarketScope.LOCAL, MarketScope.INTERNATIONAL, MarketScope.CHINA),
            required_quantity=2.5, quantity_unit="kg",
            technical_requirements=(TechnicalRequirement("dielectric_strength", "kV/mm", minimum=20),),
            maximum_total_budget=180.0, budget_currency="EUR",
            local_radius_km=80.0, maximum_delivery_days=30.0,
        )
        values.update(overrides)
        return AgentSourcingRequest(**values)

    def test_agent_controls_category_markets_quantity_budget_and_limits(self):
        request = self.make_request()
        plan = plan_agent_request(request)
        self.assertEqual(plan.agent_id, "muscle-design-agent")
        self.assertEqual(plan.required_quantity, 2.5)
        self.assertEqual(plan.maximum_total_budget, 180.0)
        self.assertEqual({task.market_scope for task in plan.tasks},
                         {MarketScope.LOCAL, MarketScope.INTERNATIONAL, MarketScope.CHINA})
        self.assertTrue(all(task.radius_km == 80.0 if task.market_scope is MarketScope.LOCAL
                            else task.radius_km is None for task in plan.tasks))

    def test_budget_currency_must_match_destination(self):
        with self.assertRaises(ValueError):
            self.make_request(budget_currency="USD")

    def test_gps_requires_explicit_permission(self):
        with self.assertRaises(ValueError):
            self.make_request(location_mode=LocationSelectionMode.GPS)
        request = self.make_request(location_mode=LocationSelectionMode.GPS, gps_permission_granted=True)
        self.assertEqual(request.location_mode, LocationSelectionMode.GPS)

    def test_local_scope_requires_destination_coordinates(self):
        destination = EconomicLocation("remote", "Unknown", "ES", "EUR")
        with self.assertRaises(ValueError):
            self.make_request(destination=destination)

    def test_technical_requirement_needs_bound(self):
        with self.assertRaises(ValueError):
            TechnicalRequirement("strength", "MPa")

    def test_invalid_requirement_range_rejected(self):
        with self.assertRaises(ValueError):
            TechnicalRequirement("strength", "MPa", minimum=20, maximum=10)

    def test_json_contract_rejects_unknown_fields(self):
        with self.assertRaises(ValueError):
            AgentSourcingRequest.from_dict({"schema":"yj64.agent-sourcing-request.v1","unexpected":True})

    def test_json_contract_parses_agent_generated_request(self):
        payload = {
            "schema": "yj64.agent-sourcing-request.v1",
            "request_id": "req-2",
            "agent_id": "chemistry-agent",
            "task_description": "Source aluminium foil",
            "destination": {
                "location_id": "dest-1", "name": "Workshop",
                "country_code": "ES", "currency": "EUR",
                "latitude": 36.72, "longitude": -4.42,
            },
            "location_mode": "map",
            "categories": [{"category_id":"metals","label":"Metals","search_terms":["aluminium foil"]}],
            "market_scopes": ["domestic", "china"],
            "required_quantity": 5,
            "quantity_unit": "kg",
            "technical_requirements": [{"property_name":"purity","unit":"%","minimum":99}],
            "maximum_total_budget": 75,
            "budget_currency": "EUR",
        }
        request = AgentSourcingRequest.from_dict(payload)
        self.assertEqual(request.categories[0].search_terms, ("aluminium foil",))
        self.assertEqual({t.market_scope for t in request.build_search_plan()},
                         {MarketScope.DOMESTIC, MarketScope.CHINA})


if __name__ == "__main__":
    unittest.main()
