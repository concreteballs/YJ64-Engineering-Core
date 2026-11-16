import unittest

from yj64_engineering_core.economics import (
    EconomicLocation, LocationSelection, LocationSelectionMode,
    MarketScope, SupplierSearchPlanner, SourcingCategory,
)


class SupplierSearchPlannerTests(unittest.TestCase):
    def setUp(self):
        self.destination = EconomicLocation(
            "workshop-1", "Selected workshop", "ES", "EUR", 36.72, -4.42
        )

    def test_map_selection_requires_coordinates(self):
        without_coords = EconomicLocation("x", "Place", "ES", "EUR")
        with self.assertRaises(ValueError):
            LocationSelection(without_coords, LocationSelectionMode.MAP)

    def test_gps_requires_explicit_permission(self):
        with self.assertRaises(ValueError):
            LocationSelection(self.destination, LocationSelectionMode.GPS)
        selection = LocationSelection(
            self.destination, LocationSelectionMode.GPS, gps_permission_granted=True
        )
        self.assertEqual(selection.mode, LocationSelectionMode.GPS)

    def test_map_selection_does_not_require_gps_permission(self):
        selection = LocationSelection(self.destination, LocationSelectionMode.MAP)
        self.assertFalse(selection.gps_permission_granted)

    def test_builds_four_market_scopes_per_category(self):
        category = SourcingCategory(
            "metals", "Metals", ("aluminium sheet", "steel tube")
        )
        tasks = SupplierSearchPlanner().build_plan(
            LocationSelection(self.destination, LocationSelectionMode.MAP),
            categories=(category,),
        )
        self.assertEqual(
            {task.market_scope for task in tasks},
            {MarketScope.LOCAL, MarketScope.DOMESTIC, MarketScope.INTERNATIONAL, MarketScope.CHINA},
        )
        china = next(task for task in tasks if task.market_scope is MarketScope.CHINA)
        self.assertTrue(china.requires_ship_to_destination)
        self.assertIn("customs", " ".join(china.notes).lower())
        local = next(task for task in tasks if task.market_scope is MarketScope.LOCAL)
        self.assertEqual(local.radius_km, 150.0)

    def test_default_plan_separates_material_and_part_categories(self):
        tasks = SupplierSearchPlanner().build_plan(
            LocationSelection(self.destination, LocationSelectionMode.MAP)
        )
        ids = {task.category_id for task in tasks}
        self.assertIn("chemicals", ids)
        self.assertIn("metals", ids)
        self.assertIn("mechanical_parts", ids)
        self.assertIn("electronics", ids)
        self.assertEqual(len(tasks), len(ids) * 4)

    def test_duplicate_category_ids_are_rejected(self):
        category = SourcingCategory("metal", "Metal", ("metal stock",))
        with self.assertRaises(ValueError):
            SupplierSearchPlanner().build_plan(
                LocationSelection(self.destination, LocationSelectionMode.MAP),
                categories=(category, category),
            )


if __name__ == "__main__":
    unittest.main()
