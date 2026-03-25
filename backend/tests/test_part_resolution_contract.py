"""
Contract tests for GeometryService._resolve_to_part (no CATIA required).
Prevents regression: assembly Product must resolve to Document.Part, not a bare Product chain.
"""
import os
import sys
import unittest

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.services.geometry_service import GeometryService


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


if __name__ == "__main__":
    unittest.main()
