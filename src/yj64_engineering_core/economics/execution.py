"""Bounded execution of agent-authored supplier search plans.

Only explicitly registered providers are called. The current built-in paid
provider is the 1688/Nexscope adapter; each call is budget-capped. This is a
library executor, not a durable background queue or public execution endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .agent import AgentSourcingPlan
from .catalog import CatalogSearchResult, Nexscope1688SearchAdapter
from .discovery import MarketScope


class _1688Search(Protocol):
    def search(self, keyword: str, *, item_id: str, tax_included: bool,
               page_index: int = 1, page_size: int = 20,
               company_type: int | None = None) -> CatalogSearchResult: ...


@dataclass(frozen=True, slots=True)
class SupplierSearchExecution:
    category_id: str
    market_scope: MarketScope
    keyword: str
    provider_id: str
    result: CatalogSearchResult


@dataclass(frozen=True, slots=True)
class AgentSourcingExecutionReport:
    request_id: str
    agent_id: str
    executions: tuple[SupplierSearchExecution, ...]
    calls_made: int
    maximum_credits_spent: int
    warnings: tuple[str, ...]


class AgentSourcingExecutor:
    """Execute only supported market scopes under an explicit external-call cap."""

    MAX_1688_CREDITS_PER_CALL = 19

    def __init__(
        self,
        *,
        china_adapter: _1688Search | None = None,
        maximum_external_calls: int = 0,
        maximum_external_credits: int = 0,
        china_tax_included: bool | None = None,
    ) -> None:
        if isinstance(maximum_external_calls, bool) or not isinstance(maximum_external_calls, int) or maximum_external_calls < 0:
            raise ValueError("maximum_external_calls must be a non-negative integer")
        if isinstance(maximum_external_credits, bool) or not isinstance(maximum_external_credits, int) or maximum_external_credits < 0:
            raise ValueError("maximum_external_credits must be a non-negative integer")
        if maximum_external_calls * self.MAX_1688_CREDITS_PER_CALL > maximum_external_credits:
            raise ValueError("external credit budget does not cover the maximum authorized call count")
        if china_adapter is not None and maximum_external_calls == 0:
            raise ValueError("a paid 1688 adapter requires an explicit positive call budget")
        if china_adapter is not None and not isinstance(china_tax_included, bool):
            raise TypeError("china_tax_included must be explicitly set when enabling 1688")
        self._china_adapter = china_adapter
        self._maximum_external_calls = maximum_external_calls
        self._maximum_external_credits = maximum_external_credits
        self._china_tax_included = china_tax_included

    def execute(self, plan: AgentSourcingPlan) -> AgentSourcingExecutionReport:
        executions: list[SupplierSearchExecution] = []
        warnings: list[str] = []
        calls = 0
        for task in plan.tasks:
            if task.market_scope is not MarketScope.CHINA:
                warnings.append(
                    f"{task.category_id}/{task.market_scope.value}: no provider is currently registered for this market scope"
                )
                continue
            if self._china_adapter is None:
                warnings.append(
                    f"{task.category_id}/china: 1688 provider is not enabled; no external call made"
                )
                continue
            for keyword in task.search_terms:
                if calls >= self._maximum_external_calls:
                    warnings.append("External search call budget exhausted; remaining tasks were not executed")
                    break
                result = self._china_adapter.search(
                    keyword,
                    item_id=task.category_id,
                    tax_included=self._china_tax_included,
                )
                executions.append(SupplierSearchExecution(
                    category_id=task.category_id,
                    market_scope=task.market_scope,
                    keyword=keyword,
                    provider_id="nexscope-1688",
                    result=result,
                ))
                calls += 1
            if calls >= self._maximum_external_calls:
                break
        return AgentSourcingExecutionReport(
            request_id=plan.request_id,
            agent_id=plan.agent_id,
            executions=tuple(executions),
            calls_made=calls,
            maximum_credits_spent=calls * self.MAX_1688_CREDITS_PER_CALL,
            warnings=tuple(warnings),
        )
