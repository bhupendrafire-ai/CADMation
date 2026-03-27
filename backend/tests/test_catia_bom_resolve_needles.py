import os
import sys
import unittest

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.services.catia_bom_resolve import needle_matches_product  # noqa: E402


class NeedleMatchTests(unittest.TestCase):
    def test_202_lower_plate(self):
        self.assertTrue(needle_matches_product("202_LOWER PLATE", "202_LOWER PLATE", "202_LOWER PLATE.1"))

    def test_lower_steel_space(self):
        self.assertTrue(needle_matches_product("LOWER STEEL", "LOWER STEEL", "LOWER STEEL .1"))

    def test_buck_insert_prefix(self):
        self.assertTrue(needle_matches_product("BUCK_INSERT", "PART_BUCK_INSERT_01", "PART_BUCK_INSERT_01.1"))

    def test_main_body(self):
        self.assertTrue(needle_matches_product("MAIN_BODY", "MAIN_BODY", "MAIN_BODY.2"))

    def test_no_match(self):
        self.assertFalse(needle_matches_product("OTHER", "X", "Y.1"))


if __name__ == "__main__":
    unittest.main()
