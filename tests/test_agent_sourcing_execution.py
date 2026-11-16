import unittest

from yj64_engineering_core.economics.agent import AgentSourcingRequest, plan_agent_request
from yj64_engineering_core.economics.discovery import LocationSelectionMode, MarketScope, SourcingCategory
from yj64_engineering_core.economics.execution import AgentSourcingExecutor
from yj64_engineering_core.economics.catalog import CatalogSearchResult
from yj64_engineering_core.economics.sourcing import EconomicLocation


class Fake1688Adapter:
    def __init__(self):
        self.keywords = []

    def search(self, keyword, *, item_id, tax_included, page_index=1, page_size=20, company_type=None):
        self.keywords.append((keyword, item_id, tax_included))
        return CatalogSearchResult(offers=(), supplier_product_ids=(), warnings=(), observed_at="2026-11-17T00:00:00Z")


def plan():
    request = AgentSourcingRequest(
        request_id="exec-1", agent_id="robot-design-agent",
        task_description="Find actuator material",
        destination=EconomicLocation("dest", "Workshop", "ES", "EUR", 36.7, -4.4),
        location_mode=LocationSelectionMode.MAP,
        categories=(SourcingCategory("polymers", "Polymers", ("介电弹性体", "硅橡胶")),),
        market_scopes=(MarketScope.LOCAL, MarketScope.CHINA),
        required_quantity=2, quantity_unit="kg",
    )
    return plan_agent_request(request)


class AgentSourcingExecutorTests(unittest.TestCase):
    def test_no_adapter_means_no_paid_call(self):
        report = AgentSourcingExecutor().execute(plan())
        self.assertEqual(report.calls_made, 0)
        self.assertEqual(report.executions, ())
        self.assertTrue(any("not enabled" in warning for warning in report.warnings))

    def test_requires_explicit_credit_budget_for_paid_calls(self):
        adapter = Fake1688Adapter()
        with self.assertRaises(ValueError):
            AgentSourcingExecutor(
                china_adapter=adapter, maximum_external_calls=2,
                maximum_external_credits=37, china_tax_included=False,
            )
        with self.assertRaises(ValueError):
            AgentSourcingExecutor(
                china_adapter=adapter, maximum_external_calls=0,
                maximum_external_credits=0, china_tax_included=False,
            )

    def test_executes_only_china_tasks_within_call_and_credit_caps(self):
        adapter = Fake1688Adapter()
        executor = AgentSourcingExecutor(
            china_adapter=adapter, maximum_external_calls=1,
            maximum_external_credits=19, china_tax_included=False,
        )
        report = executor.execute(plan())
        self.assertEqual(report.calls_made, 1)
        self.assertEqual(report.maximum_credits_spent, 19)
        self.assertEqual(adapter.keywords, [("介电弹性体", "polymers", False)])
        self.assertEqual(len(report.executions), 1)
        self.assertTrue(any("budget exhausted" in warning for warning in report.warnings))

    def test_rejects_missing_tax_treatment_when_provider_enabled(self):
        with self.assertRaises(TypeError):
            AgentSourcingExecutor(
                china_adapter=Fake1688Adapter(), maximum_external_calls=1,
                maximum_external_credits=19,
            )


if __name__ == "__main__":
    unittest.main()
