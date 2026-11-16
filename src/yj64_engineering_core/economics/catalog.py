"""Supplier catalog adapters with explicit provenance and no order execution."""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .sourcing import EconomicLocation, SupplierOffer


@dataclass(frozen=True, slots=True)
class CatalogSearchResult:
    offers: tuple[SupplierOffer, ...]
    supplier_product_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    observed_at: str


class MouserSearchAdapter:
    """Read-only Mouser Search API adapter.

    The caller supplies the canonical engineering item ID, expected ISO currency,
    and a verified supplier location. This adapter never creates carts or orders.
    """

    supplier_id = "mouser"
    supplier_name = "Mouser Electronics"
    endpoint = "https://api.mouser.com/api/v1/search/keyword"

    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: float = 20.0,
        post_json: Callable[[str, dict, float], dict] | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("Mouser Search API key is required")
        if isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._api_key = api_key.strip()
        self._timeout = float(timeout_seconds)
        self._post_json = post_json or self._default_post_json

    @staticmethod
    def _default_post_json(url: str, payload: dict, timeout: float) -> dict:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _price(value: object, expected_currency: str) -> float:
        if not isinstance(value, str):
            raise ValueError("price is not a string")
        raw = value.strip()
        symbol_currency = None
        for symbol, code in (("€", "EUR"), ("£", "GBP"), ("¥", "JPY")):
            if symbol in raw:
                symbol_currency = code
                raw = raw.replace(symbol, "")
        if "$" in raw:
            raise ValueError("ambiguous dollar price; currency cannot be verified")
        if symbol_currency and symbol_currency != expected_currency:
            raise ValueError(f"price symbol indicates {symbol_currency}, expected {expected_currency}")
        raw = raw.replace(" ", "")
        if "," in raw and "." in raw:
            if raw.rfind(",") > raw.rfind("."):
                raw = raw.replace(".", "").replace(",", ".")
            else:
                raw = raw.replace(",", "")
        else:
            raw = raw.replace(",", ".")
        raw = re.sub(r"[^0-9.]", "", raw)
        if not raw or raw.count(".") > 1:
            raise ValueError("price format is not supported")
        amount = float(raw)
        if amount < 0:
            raise ValueError("price must not be negative")
        return amount

    @staticmethod
    def _parts(payload: dict) -> list[dict]:
        results = payload.get("SearchResults") or {}
        parts = results.get("Parts") or []
        if not isinstance(parts, list):
            raise ValueError("Mouser response SearchResults.Parts is not a list")
        errors = results.get("Errors") or payload.get("Errors") or []
        if errors:
            messages = "; ".join(
                str(item.get("Message", item)) if isinstance(item, dict) else str(item)
                for item in errors
            )
            raise RuntimeError(f"Mouser Search API returned errors: {messages}")
        return [part for part in parts if isinstance(part, dict)]

    def search(
        self,
        keyword: str,
        *,
        item_id: str,
        supplier_location: EconomicLocation,
        currency: str,
        limit: int = 50,
        in_stock_only: bool = True,
        tax_included: bool = False,
    ) -> CatalogSearchResult:
        for value, name in ((keyword, "keyword"), (item_id, "item_id"), (currency, "currency")):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(tax_included, bool):
            raise TypeError("tax_included must be boolean")
        if len(currency) != 3 or currency != supplier_location.currency:
            raise ValueError("currency must be an ISO-4217 code matching supplier location currency")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
            raise ValueError("limit must be an integer between 1 and 50")
        query = urllib.parse.urlencode({"apiKey": self._api_key})
        url = f"{self.endpoint}?{query}"
        payload = {
            "SearchByKeywordRequest": {
                "keyword": keyword.strip(),
                "records": limit,
                "startingRecord": 0,
                "searchOptions": "InStock" if in_stock_only else "None",
            }
        }
        response = self._post_json(url, payload, self._timeout)
        if not isinstance(response, dict):
            raise ValueError("Mouser response must be a JSON object")
        observed_at = datetime.now(timezone.utc).isoformat()
        offers: list[SupplierOffer] = []
        product_ids: list[str] = []
        warnings: list[str] = []
        for index, part in enumerate(self._parts(response)):
            product_id = str(part.get("MouserPartNumber") or "").strip()
            if not product_id:
                warnings.append(f"Result {index + 1}: missing Mouser part number; skipped")
                continue
            product_ids.append(product_id)
            breaks = part.get("PriceBreaks") or []
            if not isinstance(breaks, list) or not breaks:
                warnings.append(f"{product_id}: no price breaks returned")
                continue
            parsed_breaks = []
            for price_break in breaks:
                if not isinstance(price_break, dict):
                    continue
                try:
                    minimum_quantity = float(price_break.get("Quantity") or 1)
                    unit_price = self._price(price_break.get("Price"), currency)
                    parsed_breaks.append((minimum_quantity, unit_price))
                except (TypeError, ValueError) as exc:
                    warnings.append(f"{product_id}: price break skipped ({exc})")
            if not parsed_breaks:
                continue
            parsed_breaks.sort(key=lambda entry: (entry[0], entry[1]))
            minimum_order = part.get("Min") or part.get("Moq") or 1
            try:
                minimum_order = float(minimum_order)
            except (TypeError, ValueError):
                minimum_order = 1.0
                warnings.append(f"{product_id}: MOQ unavailable; provisional minimum of 1 used")
            availability = str(part.get("Availability") or "").strip()
            stock_quantity = None
            stock_match = re.search(r"(\d[\d,]*)\s+in stock", availability, re.IGNORECASE)
            if stock_match:
                stock_quantity = float(stock_match.group(1).replace(",", ""))
            lead_text = str(part.get("LeadTime") or "").strip()
            lead_match = re.search(r"(\d+(?:\.\d+)?)", lead_text)
            lead_days = float(lead_match.group(1)) if lead_match else None
            detail_url = str(part.get("ProductDetailUrl") or "").strip() or None
            description = str(part.get("Description") or product_id).strip()
            manufacturer = str(part.get("Manufacturer") or "").strip()
            warnings.append(
                f"{product_id}: availability text is '{availability or 'not supplied'}'; "
                "shipping, tax and delivery to the requested destination require separate quotes."
            )
            # Price breaks are preserved as individual quantity-tier offers. The
            # economic engine can then compare a tier against the actual BOM quantity.
            for tier_index, (tier_quantity, unit_price) in enumerate(parsed_breaks):
                offers.append(SupplierOffer(
                    offer_id=f"mouser:{product_id}:tier:{tier_index + 1}",
                    item_id=item_id,
                    supplier_id=self.supplier_id,
                    supplier_name=self.supplier_name,
                    supplier_location=supplier_location,
                    unit_price=unit_price,
                    currency=currency,
                    unit="piece",
                    stock_quantity=stock_quantity,
                    minimum_order_quantity=max(minimum_order, tier_quantity),
                    lead_time_days=lead_days,
                    tax_included=tax_included,
                    source_uri=detail_url or f"https://www.mouser.es/ProductDetail/{urllib.parse.quote(product_id)}",
                    observed_at=observed_at,
                ))
        return CatalogSearchResult(
            offers=tuple(offers),
            supplier_product_ids=tuple(product_ids),
            warnings=tuple(warnings),
            observed_at=observed_at,
        )
