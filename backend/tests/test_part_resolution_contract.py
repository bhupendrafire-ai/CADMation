"""
Contract tests for GeometryService._resolve_to_part (no CATIA required).
Prevents regression: assembly Product must resolve to Document.Part, not a bare Product chain.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.services import geometry_service as _geo_mod
from app.services.geometry_service import GeometryService
from app.services.rough_stock_service import RoughStockService


class _MockBodies:
    Count = 1

    def Item(self, i):
        assert i == 1
        return self

    @property
    def Name(self):
        return "MAIN_BODY"


class _MockPart:
    def __init__(self):
        self.Bodies = _MockBodies()


class _MockDoc:
    def __init__(self, part):
        self.Part = part


class _MockRef:
    def __init__(self, doc):
        self.Parent = doc


class _MockAssemblyProduct:
    """Product under CATProduct: has ReferenceProduct -> PartDocument, not Part.Bodies."""

    def __init__(self):
        self._part = _MockPart()
        self._doc = _MockDoc(self._part)
        self.ReferenceProduct = _MockRef(self._doc)


class PartResolutionContractTests(unittest.TestCase):
    def test_assembly_product_resolves_via_reference_parent_part(self):
        """Without Parent.Part, Bodies on Product are empty/wrong; dropdown must get real Part."""
        svc = GeometryService()
        prod = _MockAssemblyProduct()
        out = svc._resolve_to_part(prod)
        self.assertIs(out, prod._part)
        self.assertEqual(out.Bodies.Count, 1)
        self.assertEqual(out.Bodies.Item(1).Name, "MAIN_BODY")

    def test_part_with_bodies_returns_self(self):
        svc = GeometryService()
        part = _MockPart()
        self.assertIs(svc._resolve_to_part(part), part)

    def test_rough_stock_dialog_target_keeps_partdesign_body(self):
        """BOM passes Body; Rough Stock must not collapse to Part-only target."""
        svc = GeometryService()
        part = _MockPart()
        body = _MockBodies()
        body.Parent = part
        body.Bodies = None  # not a Part root
        resolved_part = part
        self.assertIs(svc._rough_stock_dialog_target(body, resolved_part), body)

    def test_rough_stock_dialog_target_part_root_uses_raw_pop(self):
        svc = GeometryService()
        part = _MockPart()
        self.assertIs(svc._rough_stock_dialog_target(part, part), part)

    def test_rough_stock_dialog_target_assembly_product_stays_part(self):
        """Product node resolves to Part; Rough Stock target stays Part-shaped, not Product."""
        svc = GeometryService()
        prod = _MockAssemblyProduct()
        part = prod._part
        self.assertIs(svc._rough_stock_dialog_target(prod, part), part)

    def test_resolve_targets_via_selection_keeps_named_body_not_slots_first(self):
        """If Item(1) is not the BOM body, still return [target_obj] when names match."""

        class _Bodies:
            Count = 2

            def Item(self, i):
                if i == 1:
                    return type("O", (), {"Name": "FIRST_BODY"})()
                return type("M", (), {"Name": "MAIN_BODY"})()

        part = type("P", (), {"Name": "202_LOWER PLATE", "Bodies": _Bodies()})()
        body = type("B", (), {"Name": "MAIN_BODY", "Parent": part})()

        catia = MagicMock()
        doc = MagicMock()
        catia.ActiveDocument = doc
        doc.Selection = MagicMock()

        root, targets = RoughStockService._resolve_targets_via_selection(catia, body)
        self.assertIs(root, part)
        self.assertEqual(len(targets), 1)
        self.assertIs(targets[0], body)
        self.assertEqual(getattr(targets[0], "Name", None), "MAIN_BODY")

    def test_resolve_targets_parent_walk_bodies_collection(self):
        """CATIA: Body.Parent is often Bodies collection; Part is one level above."""

        class _Bodies:
            Count = 2

            def Item(self, i):
                if i == 1:
                    return type("O", (), {"Name": "FIRST_BODY"})()
                return type("M", (), {"Name": "MAIN_BODY"})()

        part = type("P", (), {"Name": "PART1", "Bodies": _Bodies()})()
        coll = type("Coll", (), {"Parent": part})()
        body = type("B", (), {"Name": "MAIN_BODY", "Parent": coll})()

        catia = MagicMock()
        doc = MagicMock()
        catia.ActiveDocument = doc
        doc.Selection = MagicMock()

        root, targets = RoughStockService._resolve_targets_via_selection(catia, body)
        self.assertIs(root, part)
        self.assertEqual(len(targets), 1)
        self.assertIs(targets[0], body)

    def test_selection_hit_rejects_inertia_name(self):
        class I:
            Name = "INERTIA_VOLUME_1"

        self.assertTrue(
            RoughStockService._selection_hit_is_wrong_for_rough_stock(I(), object())
        )

    def test_selection_hit_requires_com_identity_when_target_body_set(self):
        class O:
            pass

        a, b = O(), O()
        with patch.object(RoughStockService, "_com_same_object", return_value=False):
            self.assertTrue(RoughStockService._selection_hit_is_wrong_for_rough_stock(a, b))
        with patch.object(RoughStockService, "_com_same_object", return_value=True):
            self.assertFalse(RoughStockService._selection_hit_is_wrong_for_rough_stock(a, b))

    def test_measurement_cache_part_plus_body_suffix_not_colliding(self):
        """Two CATParts with a body both named MAIN_BODY must not share one cache slot."""
        svc = GeometryService()

        class _Doc:
            def __init__(self, fp):
                self.FullName = fp

        class _Part:
            def __init__(self, name, fp):
                self.Name = name
                self.PartNumber = ""
                self.Parent = _Doc(fp)

        p_lo = _Part("202_LOWER PLATE", r"H:\p202.CATPart")
        p_hi = _Part("203_UPPER PLATE", r"H:\p203.CATPart")
        ver = getattr(_geo_mod, "_MEASUREMENT_CACHE_KEY_VER", "rs4")
        k_lo = f"{ver}::{svc._measurement_cache_key(p_lo, 'ROUGH_STOCK')}::body=MAIN_BODY"
        k_hi = f"{ver}::{svc._measurement_cache_key(p_hi, 'ROUGH_STOCK')}::body=MAIN_BODY"
        self.assertNotEqual(k_lo, k_hi)

    def test_meas_target_for_isolated_part_matches_body_name(self):
        class _Bodies:
            Count = 2

            def Item(self, i):
                if i == 1:
                    return type("B", (), {"Name": "OTHER"})()
                return type("B", (), {"Name": "MAIN_BODY"})()

        iso = type("P", (), {"Name": "202_LOWER PLATE", "Bodies": _Bodies()})()
        leaf = type("L", (), {"Name": "MAIN_BODY", "Parent": object()})()
        out = RoughStockService._meas_target_for_isolated_part(iso, leaf)
        self.assertEqual(getattr(out, "Name", None), "MAIN_BODY")

    def test_resolve_catpart_path_from_body_parent_part(self):
        import tempfile

        fd, path = tempfile.mkstemp(suffix=".CATPart")
        os.close(fd)
        try:

            class _Doc:
                pass

            d = _Doc()
            d.FullName = path

            class _Part:
                Bodies = object()
                Parent = d

            body = type("B", (), {"Name": "MAIN_BODY", "Parent": _Part()})()
            p = RoughStockService._resolve_catpart_path_from_target(body)
            self.assertEqual(os.path.normcase(os.path.abspath(path)), os.path.normcase(p))
        finally:
            try:
                os.remove(path)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
