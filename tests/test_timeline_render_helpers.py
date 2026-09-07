import unittest

from ui.timeline_rendering import (
    build_render_cache_key,
    expand_render_range,
    is_render_cache_compatible,
    is_stale_render_result,
    is_view_range_within_buffer,
)


class TimelineRenderHelperTests(unittest.TestCase):
    def test_view_range_within_buffer_returns_true_for_reused_region(self):
        self.assertTrue(
            is_view_range_within_buffer((200.0, 300.0), (100.0, 400.0))
        )

    def test_view_range_within_buffer_returns_false_when_view_exits_buffer(self):
        self.assertFalse(
            is_view_range_within_buffer((50.0, 300.0), (100.0, 400.0))
        )

    def test_expand_render_range_adds_overscan_and_clamps_to_bounds(self):
        self.assertEqual(
            (0.0, 400.0),
            expand_render_range((0.0, 200.0), 1000.0),
        )
        self.assertEqual(
            (600.0, 1000.0),
            expand_render_range((800.0, 1000.0), 1000.0),
        )

    def test_stale_render_result_detects_outdated_generation(self):
        self.assertTrue(is_stale_render_result(2, 3))
        self.assertFalse(is_stale_render_result(3, 3))

    def test_render_cache_key_changes_when_resolution_changes(self):
        key_a = build_render_cache_key((0.0, 1000.0), 1200, 800.0, 1.0)
        key_b = build_render_cache_key((0.0, 1000.0), 1400, 800.0, 1.0)
        self.assertNotEqual(key_a, key_b)

    def test_render_cache_key_ignores_position_when_span_and_resolution_match(self):
        key_a = build_render_cache_key((0.0, 1000.0), 1200, 800.0, 1.0)
        key_b = build_render_cache_key((100.0, 1100.0), 1200, 800.0, 1.0)
        self.assertEqual(key_a, key_b)

    def test_render_cache_key_changes_when_render_span_changes(self):
        key_a = build_render_cache_key((0.0, 1000.0), 1200, 800.0, 1.0)
        key_b = build_render_cache_key((0.0, 800.0), 1200, 800.0, 1.0)
        self.assertNotEqual(key_a, key_b)

    def test_render_cache_is_not_compatible_when_zoom_changes_pixels(self):
        buffered_key = build_render_cache_key((0.0, 1000.0), 1200, 800.0, 1.0)
        request_key = build_render_cache_key((0.0, 1000.0), 1400, 800.0, 1.0)
        self.assertFalse(
            is_render_cache_compatible(
                (100.0, 900.0),
                (0.0, 1000.0),
                buffered_key,
                request_key,
            )
        )

    def test_render_cache_reuses_shifted_view_inside_buffer(self):
        buffered_key = build_render_cache_key((0.0, 1000.0), 1200, 800.0, 1.0)
        request_key = build_render_cache_key((100.0, 1100.0), 1200, 800.0, 1.0)
        self.assertTrue(
            is_render_cache_compatible(
                (200.0, 900.0),
                (0.0, 1000.0),
                buffered_key,
                request_key,
            )
        )

    def test_render_cache_is_compatible_only_when_range_and_key_match(self):
        key = build_render_cache_key((0.0, 1000.0), 1200, 800.0, 1.0)
        self.assertTrue(
            is_render_cache_compatible(
                (100.0, 900.0),
                (0.0, 1000.0),
                key,
                key,
            )
        )


if __name__ == "__main__":
    unittest.main()
