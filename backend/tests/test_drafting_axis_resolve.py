import os
import sys
import unittest
from unittest.mock import MagicMock, patch

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.services.drafting_axis_resolve import (  # noqa: E402
    _axis_name_matches_needle,
    catpart_documents_same,
)
from app.services.drafting_orientation import front_plane_and_axis_for_row  # noqa: E402


class DraftingAxisResolveTests(unittest.TestCase):
    def test_axis_name_matches_needle_substring(self):
        ax = MagicMock()
        ax.Name = "AXIS_LOWER_DIE"
        self.assertTrue(_axis_name_matches_needle("LOWER", ax))
        self.assertTrue(_axis_name_matches_needle("axis_lower", ax))
        self.assertFalse(_axis_name_matches_needle("MISSING", ax))

    def test_catpart_documents_same_norm_path(self):
        a = MagicMock()
        b = MagicMock()
        a.FullName = r"H:\proj\Part1.CATPart"
        b.FullName = r"h:/proj/part1.catpart"
        self.assertTrue(catpart_documents_same(a, b))

    def test_catpart_documents_same_false_if_missing(self):
        a = MagicMock()
        a.FullName = "x"
        self.assertFalse(catpart_documents_same(a, None))


class FrontPlaneGlobalRowTests(unittest.TestCase):
    def test_global_axis_uses_part_plane_when_catpart_differs(self):
        gax = MagicMock()
        global_plane = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
        local_plane = (0.0, 0.0, 1.0, 0.0, 1.0, 0.0)
        part_scope = object()
        gdoc = MagicMock()
        gdoc.FullName = r"H:\asm.CATPart"
        pdoc = MagicMock()
        pdoc.FullName = r"H:\leaf.CATPart"
        local_ax = MagicMock()

        with patch(
            "app.services.drafting_orientation.catpart_document_for_part",
            return_value=pdoc,
        ):
            with patch(
                "app.services.drafting_orientation.front_plane_and_axis_from_part",
                return_value=(local_plane, local_ax),
            ):
                pl, axis_ref, cat_axis = front_plane_and_axis_for_row(
                    part_scope,
                    None,
                    global_axis=gax,
                    global_catpart_doc=gdoc,
                    global_plane_six=global_plane,
                )
        self.assertEqual(pl, local_plane)
        self.assertIs(axis_ref, local_ax)
        self.assertIs(cat_axis, pdoc)

    def test_global_axis_falls_back_to_global_plane_if_part_has_no_axis(self):
        gax = MagicMock()
        global_plane = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
        part_scope = object()
        gdoc = MagicMock()
        gdoc.FullName = r"H:\asm.CATPart"
        pdoc = MagicMock()
        pdoc.FullName = r"H:\leaf.CATPart"

        with patch(
            "app.services.drafting_orientation.catpart_document_for_part",
            return_value=pdoc,
        ):
            with patch(
                "app.services.drafting_orientation.front_plane_and_axis_from_part",
                return_value=(None, None),
            ):
                pl, axis_ref, cat_axis = front_plane_and_axis_for_row(
                    part_scope,
                    None,
                    global_axis=gax,
                    global_catpart_doc=gdoc,
                    global_plane_six=global_plane,
                )
        self.assertEqual(pl, global_plane)
        self.assertIsNone(axis_ref)
        self.assertIsNone(cat_axis)

    def test_global_axis_sets_axis_when_same_catpart(self):
        gax = MagicMock()
        plane = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
        part_scope = object()
        same = MagicMock()
        same.FullName = r"H:\same.CATPart"

        with patch(
            "app.services.drafting_orientation.catpart_document_for_part",
            return_value=same,
        ):
            pl, axis_ref, cat_axis = front_plane_and_axis_for_row(
                part_scope,
                None,
                global_axis=gax,
                global_catpart_doc=same,
                global_plane_six=plane,
            )
        self.assertEqual(pl, plane)
        self.assertIs(axis_ref, gax)
        self.assertIs(cat_axis, same)


if __name__ == "__main__":
    unittest.main()
