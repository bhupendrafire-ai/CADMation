import os
import sys
import unittest

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from unittest.mock import MagicMock

from app.services.drafting_orientation import (  # noqa: E402
    DEFAULT_FRONT_PLANE,
    _axis_sort_key,
    _axis_xy_directions_raw,
    _basis_six_for_primary,
    front_plane_from_part,
    orthonormal_basis_from_axis_system,
)


class DraftingOrientationTests(unittest.TestCase):
    def test_front_plane_from_part_none(self):
        self.assertIsNone(front_plane_from_part(None))

    def test_default_front_plane_shape(self):
        self.assertEqual(len(DEFAULT_FRONT_PLANE), 6)

    def test_basis_six_xz_primary_differs_from_xy(self):
        ex, ey, ez = [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]
        xy = _basis_six_for_primary(ex, ey, ez, "xy")
        xz = _basis_six_for_primary(ex, ey, ez, "xz")
        self.assertNotEqual(xy, xz)
        self.assertEqual(xz[:3], (1.0, 0.0, 0.0))
        self.assertEqual(xz[3:], (0.0, 0.0, 1.0))

    def test_axis_sort_prefers_axis_prefix_over_absolute(self):
        a = _axis_sort_key("Absolute Axis System")
        b = _axis_sort_key("AXIS_LOWER_DIE")
        self.assertLess(b[0], a[0])

    def test_axis_sort_longer_axis_name_wins_among_same_tier(self):
        short = _axis_sort_key("AXIS_A")
        long = _axis_sort_key("AXIS_LOWER_PLATE")
        self.assertLess(long[1], short[1])

    def test_axis_xy_fallback_when_getvectors_zero(self):
        ax = MagicMock()

        def zero_vectors(vx, vy):
            vx[:] = [0.0, 0.0, 0.0]
            vy[:] = [0.0, 0.0, 0.0]

        ax.GetVectors.side_effect = zero_vectors
        xa = MagicMock()
        ya = MagicMock()
        ax.XAxis = xa
        ax.YAxis = ya
        xa.GetDirection = lambda o: o.__setitem__(slice(None), [1.0, 0.0, 0.0])
        ya.GetDirection = lambda o: o.__setitem__(slice(None), [0.0, 1.0, 0.0])
        pair = _axis_xy_directions_raw(ax)
        self.assertIsNotNone(pair)
        self.assertEqual(pair[0], [1.0, 0.0, 0.0])
        self.assertEqual(pair[1], [0.0, 1.0, 0.0])

    def test_orthonormal_basis_uses_xz_when_y_direction_zero(self):
        ax = MagicMock()

        def zero_vectors(vx, vy):
            vx[:] = [0.0, 0.0, 0.0]
            vy[:] = [0.0, 0.0, 0.0]

        ax.GetVectors.side_effect = zero_vectors
        xa, ya, za = MagicMock(), MagicMock(), MagicMock()
        ax.XAxis, ax.YAxis, ax.ZAxis = xa, ya, za
        xa.GetDirection = lambda o: o.__setitem__(slice(None), [1.0, 0.0, 0.0])
        ya.GetDirection = lambda o: o.__setitem__(slice(None), [0.0, 0.0, 0.0])
        za.GetDirection = lambda o: o.__setitem__(slice(None), [0.0, 0.0, 1.0])
        basis = orthonormal_basis_from_axis_system(ax)
        self.assertIsNotNone(basis)
        ex, ey, ez = basis
        self.assertEqual(len(ex), 3)
        self.assertEqual(len(ey), 3)
        self.assertEqual(len(ez), 3)


if __name__ == "__main__":
    unittest.main()
