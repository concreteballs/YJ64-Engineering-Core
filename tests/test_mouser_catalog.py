import unittest

from yj64_engineering_core.economics import EconomicLocation, MouserSearchAdapter


def response():
    return {
        "SearchResults": {
            "Parts": [{
                "MouserPartNumber": "595-STM32F4",
                "ManufacturerPartNumber": "STM32F4",
                "Manufacturer": "STMicroelectronics",
                "Description": "Microcontroller",
                "Availability": "120 In Stock",
                "Min": "1",
                "LeadTime": "12 Weeks",
                "ProductDetailUrl": "https://www.mouser.es/ProductDetail/example",
                "PriceBreaks": [
                    {"Quantity": "1", "Price": "€ 8,50"},
                    {"Quantity": "10", "Price": "€ 7,90"},
                ],
            }]
        }
    }


class MouserAdapterTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        def fake_post(url, payload, timeout):
            self.calls.append((url, payload, timeout))
            return response()
        self.adapter = MouserSearchAdapter("test-key", post_json=fake_post)
        self.location = EconomicLocation(
            "mouser-eu", "Mouser EU distribution", "ES", "EUR"
        )

    def test_maps_search_results_to_supplier_offers(self):
        result = self.adapter.search(
            "STM32", item_id="controller", supplier_location=self.location,
            currency="EUR",
        )
        self.assertEqual(len(result.offers), 2)
        self.assertEqual(result.offers[0].item_id, "controller")
        self.assertEqual(result.offers[0].unit_price, 8.5)
        self.assertEqual(result.offers[1].unit_price, 7.9)
        self.assertEqual(result.offers[0].stock_quantity, 120)
        self.assertEqual(result.offers[0].supplier_id, "mouser")
        self.assertTrue(result.offers[0].source_uri.startswith("https://"))

    def test_uses_read_only_keyword_search_and_caps_limit(self):
        self.adapter.search(
            "motor driver", item_id="driver", supplier_location=self.location,
            currency="EUR", limit=25,
        )
        url, payload, timeout = self.calls[0]
        self.assertIn("/api/v1/search/keyword?", url)
        self.assertIn("apiKey=test-key", url)
        self.assertEqual(payload["SearchByKeywordRequest"]["records"], 25)
        self.assertEqual(payload["SearchByKeywordRequest"]["searchOptions"], "InStock")

    def test_rejects_ambiguous_dollar_price(self):
        class DollarAdapter(MouserSearchAdapter):
            @staticmethod
            def _price(value, expected_currency):
                return MouserSearchAdapter._price(value, expected_currency)
        with self.assertRaises(ValueError):
            DollarAdapter._price("$1.20", "EUR")

    def test_rejects_currency_location_mismatch(self):
        with self.assertRaises(ValueError):
            self.adapter.search(
                "STM32", item_id="controller", supplier_location=self.location,
                currency="USD",
            )

    def test_rejects_invalid_limit(self):
        with self.assertRaises(ValueError):
            self.adapter.search(
                "STM32", item_id="controller", supplier_location=self.location,
                currency="EUR", limit=51,
            )


if __name__ == "__main__":
    unittest.main()
