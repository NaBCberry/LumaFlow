import unittest
from types import SimpleNamespace

import numpy as np
import pandas as pd

from ui.audio_track_widget import AudioTrackWidget
from ui.main_window import MainWindow
from ui.timeline_group_widget import TimelineGroupWidget


class _AxisStub:
    def __init__(self):
        self.mel_frequencies = None

    def setTicks(self, _ticks):
        pass

    def update(self):
        pass


class _PlotStub:
    def __init__(self, x_range=(250.0, 750.0)):
        self.x_range = list(x_range)
        self.x_range_calls = []
        self.y_range_calls = []

    def viewRange(self):
        return [self.x_range, [0.0, 128.0]]

    def setXRange(self, start, end, padding=0):
        self.x_range_calls.append((start, end, padding))

    def setYRange(self, start, end, padding=0):
        self.y_range_calls.append((start, end, padding))


class AudioViewFitTests(unittest.TestCase):
    def test_audio_widget_data_refresh_does_not_set_x_range(self):
        widget = SimpleNamespace(
            audio_viz_item=SimpleNamespace(setAudioData=lambda _data: None),
            freq_axis=_AxisStub(),
            plot_item=_PlotStub(),
            _syncing=False,
        )
        syncing_during_y_update = []
        original_set_y_range = widget.plot_item.setYRange
        widget.plot_item.setYRange = lambda *args, **kwargs: (
            syncing_during_y_update.append(widget._syncing),
            original_set_y_range(*args, **kwargs),
        )[-1]
        audio_data = SimpleNamespace(
            frequencies=np.arange(8),
            spectrogram=np.zeros((8, 4)),
            duration_ms=5000,
        )

        AudioTrackWidget.set_audio_data(widget, audio_data)

        self.assertEqual([], widget.plot_item.x_range_calls)
        self.assertEqual([(0, 8, 0)], widget.plot_item.y_range_calls)
        self.assertEqual([True], syncing_during_y_update)
        self.assertFalse(widget._syncing)

    def test_timeline_group_keeps_timeline_range_when_audio_arrives(self):
        audio_calls = []
        group = SimpleNamespace(
            timeline=SimpleNamespace(plot_item=_PlotStub((1200.0, 1800.0))),
            audio_track=SimpleNamespace(
                set_audio_data=lambda data: audio_calls.append(("data", data)),
                set_x_range=lambda start, end: audio_calls.append(("range", start, end)),
            ),
        )
        audio_data = object()

        TimelineGroupWidget.set_audio_data(group, audio_data)

        self.assertEqual(
            [("data", audio_data), ("range", 1200.0, 1800.0)],
            audio_calls,
        )


class _TimelineStub:
    def __init__(self):
        self.data_calls = []
        self.range_calls = []

    def set_data(self, df, auto_zoom=False):
        self.data_calls.append((df, auto_zoom))

    def set_view_range_clamped(self, start, end):
        self.range_calls.append((start, end))


class MainWindowFitTriggerTests(unittest.TestCase):
    def setUp(self):
        self.window = SimpleNamespace(
            edit_timeline=_TimelineStub(),
            source_timeline=_TimelineStub(),
            data_table=SimpleNamespace(set_data=lambda _df: None),
            _fit_edit_on_next_data_change=False,
            _fit_source_on_next_data_change=False,
        )
        self.data = pd.DataFrame({"frame_time_ms": [0.0, 1000.0]})

    def test_normal_data_refresh_does_not_fit(self):
        MainWindow.on_timeline_data_changed(self.window, self.data)
        MainWindow.on_source_data_changed(self.window, self.data)

        self.assertFalse(self.window.edit_timeline.data_calls[-1][1])
        self.assertFalse(self.window.source_timeline.data_calls[-1][1])

    def test_resource_load_flag_enables_one_data_fit(self):
        self.window._fit_edit_on_next_data_change = True

        MainWindow.on_timeline_data_changed(self.window, self.data)

        self.assertTrue(self.window.edit_timeline.data_calls[-1][1])

    def test_video_loaded_fits_matching_timeline_to_duration(self):
        MainWindow._on_source_video_loaded(self.window, 6000)
        MainWindow._on_edit_video_loaded(self.window, 7000)

        self.assertEqual([(0, 6000)], self.window.source_timeline.range_calls)
        self.assertEqual([(0, 7000)], self.window.edit_timeline.range_calls)


if __name__ == "__main__":
    unittest.main()
