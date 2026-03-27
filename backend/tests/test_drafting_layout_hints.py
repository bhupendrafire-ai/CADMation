import os
import sys
import unittest
from unittest.mock import MagicMock

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.services import drafting_service as ds  # noqa: E402
from app.services.drafting_service import _try_set_view_angle_deg  # noqa: E402


class BomLayoutHintsTests(unittest.TestCase):
    def test_sanitize_sheet_title(self):
        self.assertEqual(ds._sanitize_sheet_title("202_LOWER PLATE"), "202_LOWER PLATE")
        self.assertEqual(ds._sanitize_sheet_title('bad<>name'), "bad__name")

    def test_try_set_view_angle_deg(self):
        class FakeView:
            def __init__(self):
                self.Angle = 0.0
                self.GenerativeBehavior = MagicMock()

        view = FakeView()
        self.assertTrue(_try_set_view_angle_deg(view, 90.0, None))
        self.assertAlmostEqual(view.Angle, 1.5707963267948966, places=5)
        view.GenerativeBehavior.ForceUpdate.assert_called()

    def test_parse_three_numbers(self):
        self.assertEqual(ds._parse_bom_dimensions_mm({"size": "200 x 150 x 20"}), (200.0, 150.0, 20.0))

    def test_parse_milling_size(self):
        self.assertEqual(ds._parse_bom_dimensions_mm({"millingSize": "980 x 650 x 205"}), (980.0, 650.0, 205.0))

    def test_hints_scale_with_part(self):
        small = ds._bom_layout_hints_mm({"size": "50 x 40 x 10"})
        large = ds._bom_layout_hints_mm({"size": "400 x 300 x 25"})
        self.assertLess(small[0], large[0])
        self.assertLess(small[1], large[1])


if __name__ == "__main__":
    unittest.main()
