"""No CATIA: resolution map lookup for BOM body names."""
import os
import sys
import unittest

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.services.body_name_disambiguation_service import (  # noqa: E402
    _norm_fp,
    effective_body_name_for_bom_row,
)


class BodyNameDisambiguationTests(unittest.TestCase):
    def test_effective_maps_when_key_in_resolution_map(self):
        fp = _norm_fp(r"C:\temp\sample_plate.CATPart")
        doc = type("Doc", (), {"FullName": r"C:\temp\sample_plate.CATPart"})()
        part_scope = type("Part", (), {"Parent": doc})()
        m = {(fp, "203_UPPER PLATE", "MAIN_BODY"): "MAIN_BODY__CADM1"}
        out = effective_body_name_for_bom_row(
            m, part_scope, "203_UPPER PLATE", "MAIN_BODY"
        )
        self.assertEqual(out, "MAIN_BODY__CADM1")

    def test_effective_passthrough_when_no_map(self):
        doc = type("Doc", (), {"FullName": r"C:\temp\x.CATPart"})()
        part_scope = type("Part", (), {"Parent": doc})()
        self.assertEqual(
            effective_body_name_for_bom_row({}, part_scope, "A", "LOWER_PLATE"),
            "LOWER_PLATE",
        )


if __name__ == "__main__":
    unittest.main()
