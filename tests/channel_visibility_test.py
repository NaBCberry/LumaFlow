import unittest
from unittest.mock import patch

import pandas as pd
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMainWindow

from core.color_calibration import color_calibration
from ui.main_window import MainWindow, VISIBLE_CHANNELS_SETTING_KEY
from ui.dialogs import ChannelVisibilityDialog
from ui.timeline_widget import (
    AUXILIARY_TRACK_SCALE,
    CHANNEL_TRACK_HEIGHT,
    RenderWorker,
    TimelineWidget,
)


app = QApplication.instance() or QApplication([])


def make_frame(time_ms, marker=""):
    frame = {"frame_time_ms": time_ms, "marker": marker}
    for channel in range(10):
        frame[f"ch{channel}_function"] = channel % 4
        frame[f"ch{channel}_red"] = channel + 1
        frame[f"ch{channel}_green"] = channel + 2
        frame[f"ch{channel}_blue"] = channel + 3
    return frame


class FakeSettings:
    def __init__(self):
        self.values = {}

    def setValue(self, key, value):
        self.values[key] = value


class TimelineStub:
    def __init__(self):
        self.calls = []

    def set_visible_channels(self, channels):
        self.calls.append(tuple(channels))


class ChannelVisibilityHarness(QMainWindow):
    _normalize_visible_channels = staticmethod(MainWindow._normalize_visible_channels)
    _apply_visible_channels = MainWindow._apply_visible_channels
    on_show_channel_visibility_dialog = MainWindow.on_show_channel_visibility_dialog

    def __init__(self):
        super().__init__()
        self.visible_channels = (0,)
        self.edit_timeline = TimelineStub()
        self.source_timeline = TimelineStub()


class RenderWorkerChannelTests(unittest.TestCase):
    def test_sparse_channel_selection_uses_compact_rows_and_correct_columns(self):
        frames = pd.DataFrame([make_frame(0.0), make_frame(100.0)])
        worker = RenderWorker()
        results = []
        worker.finished.connect(lambda *args: results.append(args))

        worker.process_data(frames, (0.0, 100.0), 1000.0, (0, 3), 7)

        render_data, bounds, is_raw, render_range, generation = results[-1]
        self.assertEqual([0, 1, 0, 1], render_data["y"].tolist())
        self.assertEqual(
            [color_calibration.r_lut[1], color_calibration.r_lut[4]],
            render_data["r"][:2].tolist(),
        )
        self.assertEqual(2.0, bounds.height())
        self.assertTrue(is_raw)
        self.assertEqual((0.0, 100.0), render_range)
        self.assertEqual(7, generation)

    def test_hidden_channels_do_not_affect_frame_importance(self):
        baseline = pd.DataFrame([make_frame(0.0), make_frame(100.0), make_frame(200.0)])
        changed_hidden_channel = baseline.copy()
        changed_hidden_channel.loc[1, ["ch9_red", "ch9_green", "ch9_blue"]] = 15
        worker = RenderWorker()

        baseline_scores = worker._calculate_frame_importance_vectorized(baseline, (0,))
        changed_scores = worker._calculate_frame_importance_vectorized(
            changed_hidden_channel,
            (0,),
        )

        self.assertEqual(baseline_scores.tolist(), changed_scores.tolist())


class TimelineChannelLayoutTests(unittest.TestCase):
    def setUp(self):
        self.timeline = TimelineWidget()
        self.addCleanup(self.timeline.shutdown)
        self.addCleanup(self.timeline.deleteLater)

    def test_default_and_sparse_channel_layout(self):
        self.assertEqual((0,), self.timeline.visible_channels)

        y_min, y_max = self.timeline.plot_item.viewRange()[1]
        self.assertAlmostEqual(-0.6, y_min)
        self.assertAlmostEqual(0.6, y_max)
        self.assertAlmostEqual(
            CHANNEL_TRACK_HEIGHT / (y_max - y_min),
            1 / 1.2,
        )

        self.timeline.set_visible_channels((0, 3))

        self.assertEqual((0, 3), self.timeline.visible_channels)
        y_min, y_max = self.timeline.plot_item.viewRange()[1]
        self.assertAlmostEqual(-0.7, y_min)
        self.assertAlmostEqual(1.7, y_max)
        ticks = self.timeline.y_axis._tickLevels[0]
        tick_labels = [label for _, label in ticks]
        self.assertEqual(["CH0", "CH3", "MARK", "IDX"], tick_labels)
        tick_positions = {label: position for position, label in ticks}
        self.assertAlmostEqual(1.6, tick_positions["MARK"])
        self.assertAlmostEqual(-0.6, tick_positions["IDX"])

        idx_item = self.timeline.idx_indicators_item
        self.assertAlmostEqual(-0.6, idx_item.track_y)
        self.assertAlmostEqual(
            2 * CHANNEL_TRACK_HEIGHT * AUXILIARY_TRACK_SCALE,
            idx_item.boundingRect().height(),
        )
        self.assertAlmostEqual(-0.7, idx_item.boundingRect().top())

    def test_empty_or_out_of_range_selection_is_rejected(self):
        with self.assertRaises(ValueError):
            self.timeline.set_visible_channels(())
        with self.assertRaises(ValueError):
            self.timeline.set_visible_channels((10,))

    def test_marker_track_follows_visible_channel_count(self):
        self.timeline.set_visible_channels((0, 3, 7))
        self.timeline.show_markers(
            pd.DataFrame([{"frame_time_ms": 50.0, "marker": "Beat"}])
        )

        marker = self.timeline.marker_items[0]
        self.assertAlmostEqual(2.65, marker.pos().y())
        self.assertAlmostEqual(-3.15, marker.boundingRect().top())

    def test_null_marker_placeholders_are_not_rendered(self):
        self.timeline.show_markers(
            pd.DataFrame(
                {
                    "frame_time_ms": [0.0, 10.0, 20.0, 30.0, 40.0],
                    "marker": [0, None, "null", "0.0", "66CCFF"],
                }
            )
        )

        self.assertEqual(1, len(self.timeline.marker_items))
        self.assertEqual("66CCFF", self.timeline.marker_items[0].marker_text)


class ChannelVisibilityDialogTests(unittest.TestCase):
    def setUp(self):
        self.dialog = ChannelVisibilityDialog((0, 3), channel_count=10)
        self.addCleanup(self.dialog.deleteLater)

    def test_initial_selection_and_quick_buttons(self):
        self.assertEqual((0, 3), self.dialog.selected_channels())

        self.dialog.select_all()
        self.assertEqual(tuple(range(10)), self.dialog.selected_channels())

        self.dialog.select_only_ch0()
        self.assertEqual((0,), self.dialog.selected_channels())

    def test_apply_is_disabled_when_no_channel_is_selected(self):
        for checkbox in self.dialog.channel_checkboxes:
            checkbox.setChecked(False)

        self.assertFalse(self.dialog.ok_button.isEnabled())


class MainWindowChannelVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.window = ChannelVisibilityHarness()
        self.addCleanup(self.window.deleteLater)

    def test_selection_applies_to_both_timelines_and_persists(self):
        settings = FakeSettings()
        with patch("ui.main_window.QSettings", return_value=settings):
            self.window._apply_visible_channels((3, 0))

        self.assertEqual((0, 3), self.window.visible_channels)
        self.assertEqual([(0, 3)], self.window.edit_timeline.calls)
        self.assertEqual([(0, 3)], self.window.source_timeline.calls)
        self.assertEqual([0, 3], settings.values[VISIBLE_CHANNELS_SETTING_KEY])

    def test_dialog_applies_all_selected_channels_once(self):
        with (
            patch("ui.main_window.ChannelVisibilityDialog") as dialog_class,
            patch("ui.main_window.QSettings", return_value=FakeSettings()),
        ):
            dialog = dialog_class.return_value
            dialog.exec.return_value = True
            dialog.selected_channels.return_value = (1, 4, 7)
            self.window.on_show_channel_visibility_dialog()

        self.assertEqual((1, 4, 7), self.window.visible_channels)
        self.assertEqual([(1, 4, 7)], self.window.edit_timeline.calls)
        self.assertEqual([(1, 4, 7)], self.window.source_timeline.calls)

    def test_invalid_saved_values_fall_back_to_ch0(self):
        self.assertEqual((0,), self.window._normalize_visible_channels([]))
        self.assertEqual((0,), self.window._normalize_visible_channels("2,99"))
        self.assertEqual((0, 3), self.window._normalize_visible_channels([3, "0", 3]))


if __name__ == "__main__":
    unittest.main()
