import unittest
from types import SimpleNamespace

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from core.timeline_bounds import clamp_visible_range
from ui.main_window import (
    AUTO_ROLL_FOLLOW_ANCHOR_RATIO,
    AUTO_ROLL_FOLLOW_MIN_SHIFT_MS,
    AUTO_ROLL_MODE_FOLLOW_PLAYHEAD,
    AUTO_ROLL_MODE_PAGEWISE,
    AUTO_ROLL_PAGE_RATIO,
    AUTO_ROLL_THRESHOLD_RATIO,
    MainWindow,
)


app = QApplication.instance() or QApplication([])


class _ActionStub:
    def __init__(self, checked=False):
        self.checked = checked
        self.checked_values = []

    def isChecked(self):
        return self.checked

    def setChecked(self, value):
        self.checked = value
        self.checked_values.append(value)


class AutoRollTests(unittest.TestCase):
    def _build_window(self, enabled=True, mode=AUTO_ROLL_MODE_PAGEWISE):
        window = MainWindow.__new__(MainWindow)
        window.auto_roll_action = _ActionStub(enabled)
        window.auto_roll_pagewise_action = _ActionStub(mode == AUTO_ROLL_MODE_PAGEWISE)
        window.auto_roll_follow_playhead_action = _ActionStub(
            mode == AUTO_ROLL_MODE_FOLLOW_PLAYHEAD
        )
        return window

    def _build_timeline(self, *, view_range, limit_ms, calls):
        return SimpleNamespace(
            plot_item=SimpleNamespace(viewRange=lambda: [view_range, (0.0, 1.0)]),
            _get_timeline_limit_ms=lambda: limit_ms,
            set_view_range_clamped=lambda start, end: calls.append((start, end)),
        )

    def test_auto_roll_does_nothing_when_disabled(self):
        window = self._build_window(enabled=False)
        calls = []
        timeline = self._build_timeline(view_range=(0.0, 100.0), limit_ms=1000.0, calls=calls)

        window._maybe_auto_roll_timeline(SimpleNamespace(timeline=timeline), 90.0)

        self.assertEqual([], calls)

    def test_auto_roll_does_nothing_when_already_fit_all(self):
        window = self._build_window()
        calls = []
        timeline = self._build_timeline(view_range=(0.0, 1000.0), limit_ms=1000.0, calls=calls)

        window._maybe_auto_roll_timeline(SimpleNamespace(timeline=timeline), 900.0)

        self.assertEqual([], calls)

    def test_pagewise_mode_waits_until_playhead_reaches_threshold(self):
        window = self._build_window(mode=AUTO_ROLL_MODE_PAGEWISE)
        calls = []
        timeline = self._build_timeline(view_range=(100.0, 300.0), limit_ms=1000.0, calls=calls)

        threshold = 100.0 + (300.0 - 100.0) * AUTO_ROLL_THRESHOLD_RATIO
        window._maybe_auto_roll_timeline(SimpleNamespace(timeline=timeline), threshold - 1.0)

        self.assertEqual([], calls)

    def test_pagewise_mode_pages_forward_when_playhead_crosses_threshold(self):
        window = self._build_window(mode=AUTO_ROLL_MODE_PAGEWISE)
        calls = []
        timeline = self._build_timeline(view_range=(100.0, 300.0), limit_ms=1000.0, calls=calls)

        threshold = 100.0 + (300.0 - 100.0) * AUTO_ROLL_THRESHOLD_RATIO
        window._maybe_auto_roll_timeline(SimpleNamespace(timeline=timeline), threshold)

        expected_start = 100.0 + (300.0 - 100.0) * AUTO_ROLL_PAGE_RATIO
        expected_end = expected_start + (300.0 - 100.0)
        self.assertEqual([(expected_start, expected_end)], calls)

    def test_follow_playhead_mode_keeps_playhead_at_left_anchor(self):
        window = self._build_window(mode=AUTO_ROLL_MODE_FOLLOW_PLAYHEAD)
        calls = []
        timeline = self._build_timeline(view_range=(100.0, 300.0), limit_ms=1000.0, calls=calls)

        window._maybe_auto_roll_timeline(SimpleNamespace(timeline=timeline), 250.0)

        expected_start = 250.0 - (300.0 - 100.0) * AUTO_ROLL_FOLLOW_ANCHOR_RATIO
        expected_end = expected_start + (300.0 - 100.0)
        self.assertEqual([(expected_start, expected_end)], calls)

    def test_follow_playhead_mode_skips_sub_threshold_view_shifts(self):
        window = self._build_window(mode=AUTO_ROLL_MODE_FOLLOW_PLAYHEAD)
        calls = []
        view_range = (100.0, 300.0)
        timeline = SimpleNamespace(
            plot_item=SimpleNamespace(
                viewRange=lambda: [view_range, (0.0, 1.0)],
                vb=SimpleNamespace(width=lambda: 1000.0),
            ),
            _get_timeline_limit_ms=lambda: 1000.0,
            set_view_range_clamped=lambda start, end: calls.append((start, end)),
        )

        small_target_start = view_range[0] + AUTO_ROLL_FOLLOW_MIN_SHIFT_MS - 1.0
        time_ms = small_target_start + (view_range[1] - view_range[0]) * AUTO_ROLL_FOLLOW_ANCHOR_RATIO
        window._maybe_auto_roll_timeline(SimpleNamespace(timeline=timeline), time_ms)

        self.assertEqual([], calls)

    def test_follow_playhead_mode_updates_after_threshold_view_shift(self):
        window = self._build_window(mode=AUTO_ROLL_MODE_FOLLOW_PLAYHEAD)
        calls = []
        view_range = (100.0, 300.0)
        timeline = SimpleNamespace(
            plot_item=SimpleNamespace(
                viewRange=lambda: [view_range, (0.0, 1.0)],
                vb=SimpleNamespace(width=lambda: 1000.0),
            ),
            _get_timeline_limit_ms=lambda: 1000.0,
            set_view_range_clamped=lambda start, end: calls.append((start, end)),
        )

        target_start = view_range[0] + AUTO_ROLL_FOLLOW_MIN_SHIFT_MS
        time_ms = target_start + (view_range[1] - view_range[0]) * AUTO_ROLL_FOLLOW_ANCHOR_RATIO
        window._maybe_auto_roll_timeline(SimpleNamespace(timeline=timeline), time_ms)

        self.assertEqual([(target_start, target_start + (view_range[1] - view_range[0]))], calls)

    def test_follow_playhead_mode_clamps_near_timeline_end(self):
        window = self._build_window(mode=AUTO_ROLL_MODE_FOLLOW_PLAYHEAD)
        calls = []
        limit_ms = 1000.0

        def set_view_range_clamped(start, end):
            calls.append(clamp_visible_range(start, end, limit_ms))

        timeline = SimpleNamespace(
            plot_item=SimpleNamespace(viewRange=lambda: [(800.0, 1000.0), (0.0, 1.0)]),
            _get_timeline_limit_ms=lambda: limit_ms,
            set_view_range_clamped=set_view_range_clamped,
        )

        window._maybe_auto_roll_timeline(SimpleNamespace(timeline=timeline), 980.0)

        self.assertEqual([(800.0, 1000.0)], calls)

    def test_restore_window_state_recovers_auto_roll_setting_and_mode(self):
        settings = QSettings("LumaFlow", "LumaFlow")
        settings.clear()
        settings.setValue("view/auto_roll", True)
        settings.setValue("view/auto_roll_mode", AUTO_ROLL_MODE_FOLLOW_PLAYHEAD)

        window = MainWindow.__new__(MainWindow)
        window.auto_roll_action = _ActionStub(False)
        window.auto_roll_pagewise_action = _ActionStub(True)
        window.auto_roll_follow_playhead_action = _ActionStub(False)
        window.restoreGeometry = lambda geometry: None
        window.restoreState = lambda state: None

        window._restore_window_state()

        self.assertEqual([True], window.auto_roll_action.checked_values)
        self.assertFalse(window.auto_roll_pagewise_action.isChecked())
        self.assertTrue(window.auto_roll_follow_playhead_action.isChecked())
        settings.clear()


if __name__ == "__main__":
    unittest.main()
