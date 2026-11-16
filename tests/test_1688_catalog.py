import unittest

from yj64_engineering_core.economics.catalog import Nexscope1688SearchAdapter


def response():
    return {
        "code": 0,
        "time": "2026-11-17T10:00:00Z",
        "data": {
            "products": [{
                "offerId": "1050125350953",
                "asin": "1050125350953",
                "title": "Aluminium foil roll",
                "company": "Shenzhen Example Materials Co.",
                "shopId": "shop-123",
                "currency": "¥",
                "price": 0.02,
                "quantityBegin": 100,
                "quantityPrices": '[{"quantity":"100~19999","value":"0.06"},{"quantity":"20000~599999","value":"0.03"},{"quantity":"≥600000","value":"0.02"}]',
                "unit": "kg",
                "asinUrl": "https://detail.1688.com/offer/1050125350953.html",
                "deliveryTime": "48",
            }]
        },
    }


class Nexscope1688AdapterTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        def fake_post(url, payload, headers, timeout):
            self.calls.append((url, payload, headers, timeout))
            return response()
        self.adapter = Nexscope1688SearchAdapter("test-api-key", credit_budget_per_call=19, post_json=fake_post)

    def test_maps_chinese_marketplace_result_and_quantity_tiers(self):
        result = self.adapter.search(
            "铝箔卷", item_id="aluminium-foil", tax_included=False
        )
        self.assertEqual(len(result.offers), 3)
        self.assertEqual([o.minimum_order_quantity for o in result.offers], [100, 20000, 600000])
        self.assertEqual([o.unit_price for o in result.offers], [0.06, 0.03, 0.02])
        self.assertEqual(result.offers[0].currency, "CNY")
        self.assertEqual(result.offers[0].supplier_location.country_code, "CN")
        self.assertEqual(result.offers[0].supplier_id, "1688:shop:shop-123")
        self.assertIsNone(result.offers[0].stock_quantity)
        self.assertIsNone(result.offers[0].lead_time_days)
        self.assertTrue(result.offers[0].source_uri.startswith("https://detail.1688.com/"))
        self.assertTrue(any("does not provide verified live stock" in w for w in result.warnings))
        self.assertTrue(any("no documented unit" in w for w in result.warnings))

    def test_uses_bearer_auth_and_lowest_price_sort(self):
        self.adapter.search("铝箔卷", item_id="foil", tax_included=False, company_type=2)
        url, payload, headers, timeout = self.calls[0]
        self.assertEqual(url, "https://api.nexscope.ai/dl/productSearch")
        self.assertEqual(headers["Authorization"], "Bearer test-api-key")
        self.assertEqual(payload["keyWord"], "铝箔卷")
        self.assertEqual(payload["sortField"], "price")
        self.assertEqual(payload["sortType"], "asc")
        self.assertEqual(payload["companyType"], 2)

    def test_requires_explicit_tax_treatment(self):
        with self.assertRaises(TypeError):
            self.adapter.search("铝箔卷", item_id="foil")

    def test_requires_explicit_credit_budget(self):
        with self.assertRaises(TypeError):
            Nexscope1688SearchAdapter("test-api-key")
        with self.assertRaises(ValueError):
            Nexscope1688SearchAdapter("test-api-key", credit_budget_per_call=18)

    def test_rejects_bad_page_size(self):
        with self.assertRaises(ValueError):
            self.adapter.search("铝箔卷", item_id="foil", tax_included=False, page_size=5)

    def test_rejects_api_business_error(self):
        adapter = Nexscope1688SearchAdapter(
            "test-api-key", credit_budget_per_call=19,
            post_json=lambda *args: {"code": 123, "msg": "invalid request"},
        )
        with self.assertRaises(RuntimeError):
            adapter.search("铝箔卷", item_id="foil", tax_included=False)


if __name__ == "__main__":
    unittest.main()
