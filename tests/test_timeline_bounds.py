import unittest

from core.timeline_bounds import clamp_visible_range


class TimelineBoundsTests(unittest.TestCase):
    def test_clamps_negative_left_boundary(self):
        self.assertEqual(
            (0.0, 400.0),
            clamp_visible_range(-200.0, 200.0, 1000.0),
        )

    def test_clamps_right_boundary_to_duration(self):
        self.assertEqual(
            (600.0, 1000.0),
            clamp_visible_range(900.0, 1300.0, 1000.0),
        )

    def test_short_duration_fits_full_range(self):
        self.assertEqual(
            (0.0, 150.0),
            clamp_visible_range(100.0, 300.0, 150.0),
        )


if __name__ == "__main__":
    unittest.main()
