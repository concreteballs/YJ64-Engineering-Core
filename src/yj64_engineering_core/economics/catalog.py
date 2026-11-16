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
        tax_included: bool,
    ) -> CatalogSearchResult:
        for value, name in ((keyword, "keyword"), (item_id, "item_id"), (currency, "currency")):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(tax_included, bool):
            raise TypeError("tax_included must be boolean")
        if not isinstance(in_stock_only, bool):
            raise TypeError("in_stock_only must be boolean")
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
            raw_minimum_order = part.get("Min") or part.get("Moq")
            if raw_minimum_order is None:
                minimum_order = 1.0
                warnings.append(f"{product_id}: MOQ not supplied; provisional minimum of 1 used")
            else:
                try:
                    minimum_order = float(raw_minimum_order)
                except (TypeError, ValueError):
                    minimum_order = 1.0
                    warnings.append(f"{product_id}: MOQ is invalid; provisional minimum of 1 used")
            availability = str(part.get("Availability") or "").strip()
            stock_quantity = None
            stock_match = re.search(r"(\d[\d,]*)\s+in stock", availability, re.IGNORECASE)
            if stock_match:
                stock_quantity = float(stock_match.group(1).replace(",", ""))
            lead_text = str(part.get("LeadTime") or "").strip()
            lead_match = re.search(
                r"(\d+(?:\.\d+)?)\s*(day|week|month|hour)s?",
                lead_text,
                re.IGNORECASE,
            )
            lead_days = None
            if lead_match:
                value = float(lead_match.group(1))
                unit = lead_match.group(2).lower()
                lead_days = value * {
                    "hour": 1 / 24, "day": 1, "week": 7, "month": 30
                }[unit]
            elif lead_text:
                warnings.append(
                    f"{product_id}: lead time unit is unknown ('{lead_text}'); omitted"
                )
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


class Nexscope1688SearchAdapter:
    """Read-only 1688 product-search adapter through Nexscope's paid API.

    This is an optional connector. Each call consumes Nexscope credits. It
    returns catalogue offers only; it does not verify stock, import charges or
    shipping to the destination, and it never places orders.
    """

    supplier_id = "1688"
    supplier_name = "1688 marketplace"
    endpoint = "https://api.nexscope.ai/dl/productSearch"

    def __init__(
        self,
        api_key: str,
        *,
        credit_budget_per_call: int,
        timeout_seconds: float = 25.0,
        post_json: Callable[[str, dict, dict, float], dict] | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("Nexscope API key is required")
        if isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if isinstance(credit_budget_per_call, bool) or not isinstance(credit_budget_per_call, int) or credit_budget_per_call < 19:
            raise ValueError("credit_budget_per_call must explicitly authorize at least 19 credits")
        self._api_key = api_key.strip()
        self._credit_budget_per_call = credit_budget_per_call
        self._timeout = float(timeout_seconds)
        self._post_json = post_json or self._default_post_json

    @staticmethod
    def _default_post_json(url: str, payload: dict, headers: dict, timeout: float) -> dict:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                **headers,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _currency(value: object) -> str:
        raw = str(value or "").strip().upper()
        if raw in {"¥", "CN¥", "RMB", "CNY"}:
            return "CNY"
        if re.fullmatch(r"[A-Z]{3}", raw):
            return raw
        raise ValueError("1688 result has no unambiguous ISO currency")

    @staticmethod
    def _quantity_tiers(raw: object, base_moq: float, fallback_price: object):
        tiers: list[tuple[float, float]] = []
        if isinstance(raw, str) and raw.strip():
            try:
                entries = json.loads(raw)
            except json.JSONDecodeError:
                entries = []
            if isinstance(entries, list):
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    quantity_text = str(entry.get("quantity") or "")
                    quantity_match = re.search(r"\d+(?:\.\d+)?", quantity_text.replace(",", ""))
                    try:
                        minimum = float(quantity_match.group(0)) if quantity_match else base_moq
                        price = float(entry.get("value"))
                    except (TypeError, ValueError):
                        continue
                    if minimum > 0 and price >= 0:
                        tiers.append((max(base_moq, minimum), price))
        if not tiers:
            try:
                price = float(fallback_price)
            except (TypeError, ValueError):
                return []
            if price < 0:
                return []
            tiers.append((base_moq, price))
        return sorted(set(tiers), key=lambda pair: (pair[0], pair[1]))

    def search(
        self,
        keyword: str,
        *,
        item_id: str,
        tax_included: bool,
        page_index: int = 1,
        page_size: int = 20,
        company_type: int | None = None,
    ) -> CatalogSearchResult:
        for value, name in ((keyword, "keyword"), (item_id, "item_id")):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(tax_included, bool):
            raise TypeError("tax_included must be explicitly set to boolean")
        if isinstance(page_index, bool) or not isinstance(page_index, int) or page_index < 1:
            raise ValueError("page_index must be a positive integer")
        if isinstance(page_size, bool) or not isinstance(page_size, int) or not 10 <= page_size <= 100:
            raise ValueError("page_size must be between 10 and 100")
        if company_type is not None and company_type not in {0, 1, 2}:
            raise ValueError("company_type must be 0 (any), 1 (shop) or 2 (factory)")
        payload = {
            "keyWord": keyword.strip(),
            "pageIndex": page_index,
            "pageSize": page_size,
            "searchType": 1,
            "sortField": "price",
            "sortType": "asc",
        }
        if company_type is not None:
            payload["companyType"] = company_type
        response = self._post_json(
            self.endpoint,
            payload,
            {"Authorization": f"Bearer {self._api_key}"},
            self._timeout,
        )
        if not isinstance(response, dict):
            raise ValueError("Nexscope response must be a JSON object")
        if response.get("code") != 0:
            raise RuntimeError(
                f"Nexscope 1688 search failed with code {response.get('code')}: "
                f"{response.get('msg') or 'no message'}"
            )
        data = response.get("data") or {}
        products = data.get("products") or []
        if not isinstance(products, list):
            raise ValueError("Nexscope response data.products must be a list")
        observed_at = str(response.get("time") or datetime.now(timezone.utc).isoformat())
        offers: list[SupplierOffer] = []
        product_ids: list[str] = []
        warnings: list[str] = []
        for index, product in enumerate(products):
            if not isinstance(product, dict):
                warnings.append(f"Result {index + 1}: product record is not an object; skipped")
                continue
            product_id = str(product.get("offerId") or product.get("asin") or "").strip()
            if not product_id:
                warnings.append(f"Result {index + 1}: missing 1688 offer ID; skipped")
                continue
            product_ids.append(product_id)
            try:
                currency = self._currency(product.get("currency"))
                base_moq = float(product.get("quantityBegin") or 1)
                if base_moq <= 0:
                    raise ValueError("minimum batch size must be positive")
                tiers = self._quantity_tiers(
                    product.get("quantityPrices"), base_moq, product.get("price")
                )
                if not tiers:
                    raise ValueError("no usable wholesale price or quantity price tiers")
            except (TypeError, ValueError) as exc:
                warnings.append(f"{product_id}: skipped ({exc})")
                continue
            company = str(product.get("company") or "").strip()
            shop_id = str(product.get("shopId") or "").strip()
            supplier_name = company or shop_id or f"1688 seller {product_id}"
            supplier_id = f"1688:shop:{shop_id}" if shop_id else f"1688:company:{company}" if company else f"1688:offer:{product_id}"
            supplier_location = EconomicLocation(
                location_id=supplier_id,
                name=supplier_name,
                country_code="CN",
                currency=currency,
            )
            unit = str(product.get("unit") or "").strip()
            if not unit:
                warnings.append(f"{product_id}: unit not supplied; provisional unit 'piece' used")
                unit = "piece"
            source_uri = str(product.get("asinUrl") or "").strip() or None
            if not source_uri and product_id.isdigit():
                source_uri = f"https://detail.1688.com/offer/{product_id}.html"
            if product.get("deliveryTime"):
                warnings.append(
                    f"{product_id}: marketplace deliveryTime '{product.get('deliveryTime')}' "
                    "has no documented unit; not converted to days"
                )
            warnings.append(
                f"{product_id}: 1688 search does not provide verified live stock or destination "
                "shipping/customs; obtain separate supplier and freight confirmation. "
                "Source data freshness is not specified by the API documentation."
            )
            for tier_index, (minimum_quantity, unit_price) in enumerate(tiers):
                offers.append(SupplierOffer(
                    offer_id=f"1688:{product_id}:tier:{tier_index + 1}",
                    item_id=item_id,
                    supplier_id=supplier_id,
                    supplier_name=supplier_name,
                    supplier_location=supplier_location,
                    unit_price=unit_price,
                    currency=currency,
                    unit=unit,
                    stock_quantity=None,
                    minimum_order_quantity=minimum_quantity,
                    lead_time_days=None,
                    tax_included=tax_included,
                    source_uri=source_uri,
                    observed_at=observed_at,
                ))
        return CatalogSearchResult(
            offers=tuple(offers),
            supplier_product_ids=tuple(product_ids),
            warnings=tuple(warnings),
            observed_at=observed_at,
        )
