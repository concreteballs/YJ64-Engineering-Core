import unittest
from dataclasses import replace

from yj64_engineering_core.economics import (
    AssemblyCost, BillOfMaterialsLine, EconomicLocation, EconomicRequest,
    EconomicScreeningEngine, ShippingQuote, SupplierOffer,
)


def loc(location_id, name, currency="EUR"):
    return EconomicLocation(location_id, name, "ES", currency)


def offer(offer_id, item_id, supplier_id, name, price, *, stock=100, currency="EUR"):
    return SupplierOffer(
        offer_id=offer_id, item_id=item_id, supplier_id=supplier_id,
        supplier_name=name, supplier_location=EconomicLocation(f"origin-{supplier_id}", name, "ES", currency),
        unit_price=price, currency=currency, unit="piece",
        stock_quantity=stock, minimum_order_quantity=1,
        lead_time_days=2, source_uri=f"https://supplier.example/{offer_id}",
    )


class EconomicSourcingTests(unittest.TestCase):
    def setUp(self):
        self.engine = EconomicScreeningEngine()
        self.destination = loc("workshop", "Málaga workshop")
        self.request = EconomicRequest(
            request_id="cost-001", destination=self.destination,
            quantity=1, tax_rate_fraction=0.21,
            assembly=AssemblyCost(labor_hours=2, labor_rate_per_hour=15,
                                  tooling_cost=5, consumables_cost=2, energy_cost=1),
        )

    def test_buy_complete_item_includes_tax_and_shipping(self):
        complete = offer("complete-1", "actuator", "vendor-a", "Local supplier", 80)
        shipping = ShippingQuote("vendor-a", "workshop", 6, "EUR", 1)
        report = self.engine.evaluate(self.request, "actuator", (complete,), shipping_quotes=(shipping,))
        self.assertEqual(report.status, "screening_only")
        self.assertAlmostEqual(report.cheapest.total_landed_cost, 102.8)
        self.assertEqual(report.cheapest.procurement_mode, "buy_complete")

    def test_assembly_from_parts_counts_shipping_once_per_supplier(self):
        offers = (
            offer("bearing-1", "bearing", "vendor-a", "Parts shop", 8),
            offer("shaft-1", "shaft", "vendor-a", "Parts shop", 12),
            offer("coil-1", "coil", "vendor-b", "Coil shop", 10),
        )
        quotes = (
            ShippingQuote("vendor-a", "workshop", 5, "EUR", 1),
            ShippingQuote("vendor-b", "workshop", 4, "EUR", 2),
        )
        bom = (
            BillOfMaterialsLine("bearing", 2, "piece", 0.1),
            BillOfMaterialsLine("shaft", 1, "piece", 0.5),
            BillOfMaterialsLine("coil", 1, "piece", 0.2),
        )
        report = self.engine.evaluate(self.request, "actuator", bill_of_materials=bom,
                                      part_offers=offers, shipping_quotes=quotes)
        assembled = next(x for x in report.options if x.procurement_mode == "assemble_from_parts")
        self.assertAlmostEqual(assembled.item_cost, 38)
        self.assertAlmostEqual(assembled.shipping_cost, 9)
        self.assertAlmostEqual(assembled.assembly_cost, 38)
        self.assertAlmostEqual(assembled.total_landed_cost, 38 + 7.98 + 9 + 38)

    def test_cheapest_supplier_combination_is_selected(self):
        offers = (
            offer("bearing-a", "bearing", "vendor-a", "A", 12),
            offer("bearing-b", "bearing", "vendor-b", "B", 7),
        )
        quotes = (
            ShippingQuote("vendor-a", "workshop", 2, "EUR", 1),
            ShippingQuote("vendor-b", "workshop", 3, "EUR", 1),
        )
        bom = (BillOfMaterialsLine("bearing", 1, "piece"),)
        report = self.engine.evaluate(self.request, "assembly", bill_of_materials=bom,
                                      part_offers=offers, shipping_quotes=quotes)
        self.assertEqual(report.cheapest.supplier_ids, ("vendor-b",))

    def test_missing_shipping_quote_is_not_treated_as_zero(self):
        complete = offer("complete-1", "actuator", "vendor-a", "Supplier", 80)
        report = self.engine.evaluate(self.request, "actuator", (complete,))
        self.assertEqual(report.status, "insufficient_market_data")
        self.assertIsNone(report.cheapest)

    def test_currency_mismatch_is_not_silently_converted(self):
        foreign = offer("complete-usd", "actuator", "vendor-a", "Supplier", 80, currency="USD")
        report = self.engine.evaluate(self.request, "actuator", (foreign,))
        self.assertEqual(report.status, "insufficient_market_data")
        self.assertTrue(any("convert explicitly" in x for x in report.warnings))

    def test_insufficient_stock_is_excluded(self):
        complete = offer("complete-1", "actuator", "vendor-a", "Supplier", 80, stock=0)
        report = self.engine.evaluate(self.request, "actuator", (complete,),
                                      shipping_quotes=(ShippingQuote("vendor-a", "workshop", 4, "EUR", 1),))
        self.assertIsNone(report.cheapest)

    def test_minimum_order_quantity_is_included_in_cost(self):
        minimum_order = SupplierOffer(
            offer_id="min-order", item_id="actuator", supplier_id="vendor-a",
            supplier_name="Supplier", supplier_location=loc("origin-a", "Supplier"),
            unit_price=10, currency="EUR", unit="piece", stock_quantity=10,
            minimum_order_quantity=5,
        )
        shipping = ShippingQuote("vendor-a", "workshop", 4, "EUR", 1)
        report = self.engine.evaluate(self.request, "actuator", (minimum_order,),
                                      shipping_quotes=(shipping,))
        self.assertAlmostEqual(report.cheapest.item_cost, 50)
        self.assertTrue(any("surplus" in warning for warning in report.cheapest.warnings))

    def test_destination_currency_must_be_iso_code(self):
        with self.assertRaises(ValueError):
            EconomicLocation("x", "Place", "ES", "EURO")

    def test_supplier_distance_is_reported_and_used_as_tie_breaker(self):
        near = replace(
            offer("near", "part", "near-vendor", "Near", 10),
            supplier_location=EconomicLocation("nearby", "Nearby", "ES", "EUR", 36.72, -4.42),
        )
        far = replace(
            offer("far", "part", "far-vendor", "Far", 10),
            supplier_location=EconomicLocation("faraway", "Faraway", "ES", "EUR", 40.42, -3.70),
        )
        destination = EconomicLocation("workshop", "Málaga", "ES", "EUR", 36.72, -4.42)
        request = EconomicRequest("distance-test", destination)
        quotes = (
            ShippingQuote("near-vendor", "workshop", 3, "EUR", 1, service_type="pickup"),
            ShippingQuote("far-vendor", "workshop", 3, "EUR", 1),
        )
        report = self.engine.evaluate(request, "part", (far, near), shipping_quotes=quotes)
        self.assertEqual(report.cheapest.supplier_ids, ("near-vendor",))
        self.assertAlmostEqual(report.cheapest.supplier_distances_km[0][1], 0.0)
        self.assertEqual(report.cheapest.shipping_services, ("pickup",))


if __name__ == "__main__":
    unittest.main()
