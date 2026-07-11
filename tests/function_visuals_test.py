import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from ui.function_visuals import (
    get_function_texture_spec,
    make_function_brush,
    make_function_icon,
)
from ui.timeline_widget import FastScatterItem, RenderWorker
from ui.timeline_theme import get_visual_theme_profile


app = QApplication.instance() or QApplication([])


def make_render_frame(frame_time_ms, function):
    frame = {"frame_time_ms": frame_time_ms}
    for channel in range(10):
        frame[f"ch{channel}_function"] = function
        frame[f"ch{channel}_red"] = 8
        frame[f"ch{channel}_green"] = 8
        frame[f"ch{channel}_blue"] = 8
    return frame


def render_brush(function, color="#303030", size=64):
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    try:
        painter.fillRect(image.rect(), make_function_brush(function, QColor(color)))
    finally:
        painter.end()
    return bytes(image.constBits())


def render_scatter(function, x_scale, logical_width=100.0, include_texture=True):
    image = QImage(260, 60, QImage.Format_ARGB32)
    image.fill(QColor(255, 255, 255))
    item = FastScatterItem()
    item.setData(
        {
            "x": np.array([0.0]),
            "y": np.array([0.0]),
            "w": np.array([logical_width]),
            "r": np.array([120], dtype=np.uint8),
            "g": np.array([170], dtype=np.uint8),
            "b": np.array([210], dtype=np.uint8),
            "function": np.array([function], dtype=np.uint8),
        },
        QRectF(0.0, -0.5, logical_width, 1.0),
        True,
    )
    if not include_texture:
        item.function_brushes = {}

    painter = QPainter(image)
    try:
        painter.translate(10.0, 30.0)
        painter.scale(x_scale, 20.0)
        item.paint(painter, None, None)
    finally:
        painter.end()
    return image


def image_region_bytes(image, left, top, width, height):
    values = bytearray()
    for y in range(top, top + height):
        for x in range(left, left + width):
            values.extend(image.pixelColor(x, y).getRgb())
    return bytes(values)


class FunctionVisualTests(unittest.TestCase):
    def test_function_modes_use_expected_texture_specs(self):
        self.assertIsNone(get_function_texture_spec(0))
        expected = {
            1: ("diagonal", 32),
            2: ("crosshatch", 16),
            3: ("dots", 8),
        }
        for mode, expected_spec in expected.items():
            spec = get_function_texture_spec(mode)
            self.assertEqual(expected_spec, (spec.pattern, spec.tile_size))

    def test_actual_brush_pixels_are_distinct_in_both_themes(self):
        for theme_name in ("dark_theme", "light_theme"):
            color = get_visual_theme_profile(theme_name)["function_line"]
            rendered = [
                render_brush(mode, color=color)
                for mode in range(1, 4)
            ]
            self.assertTrue(all(any(pixel != 0 for pixel in result) for result in rendered))
            self.assertEqual(3, len(set(rendered)))

    def test_menu_icon_reuses_shared_brush_generator(self):
        with patch(
            "ui.function_visuals.make_function_brush",
            wraps=make_function_brush,
        ) as brush_factory:
            icon = make_function_icon(2, "#303030", "#2A2A2A")

        self.assertFalse(icon.isNull())
        brush_factory.assert_called_once()
        self.assertEqual(2, brush_factory.call_args.args[0])

    def test_screen_space_texture_is_stable_across_horizontal_zoom(self):
        normal = render_scatter(2, 1.0)
        zoomed = render_scatter(2, 2.0)

        normal_region = image_region_bytes(normal, 20, 26, 60, 12)
        zoomed_region = image_region_bytes(zoomed, 20, 26, 60, 12)
        self.assertEqual(normal_region, zoomed_region)

    def test_frequency_strip_pulse_density_tracks_hertz(self):
        transition_counts = []
        for mode in (1, 2, 3):
            image = render_scatter(
                mode,
                x_scale=0.2,
                logical_width=1000.0,
                include_texture=False,
            )
            row = [image.pixelColor(x, 21).rgba() for x in range(15, 205)]
            transition_counts.append(
                sum(left != right for left, right in zip(row, row[1:]))
            )

        self.assertLess(transition_counts[0], transition_counts[1])
        self.assertLess(transition_counts[1], transition_counts[2])

    def test_adjacent_frames_merge_into_one_function_run(self):
        item = FastScatterItem()
        item.setData(
            {
                "x": np.array([0.0, 100.0, 200.0, 300.0]),
                "y": np.array([9.0, 9.0, 9.0, 9.0]),
                "w": np.array([100.0, 100.0, 100.0, 100.0]),
                "r": np.array([120] * 4, dtype=np.uint8),
                "g": np.array([170] * 4, dtype=np.uint8),
                "b": np.array([210] * 4, dtype=np.uint8),
                "function": np.array([1, 1, 2, 2], dtype=np.uint8),
            },
            QRectF(0.0, 8.5, 400.0, 1.0),
            True,
        )

        self.assertEqual(
            [(0.0, 200.0, 9, 1), (200.0, 400.0, 9, 2)],
            item._iter_function_runs(),
        )

    def test_function_activity_and_transitions_raise_aggregation_importance(self):
        frames = pd.DataFrame([
            make_render_frame(0.0, 0),
            make_render_frame(100.0, 0),
            make_render_frame(200.0, 2),
            make_render_frame(300.0, 2),
            make_render_frame(400.0, 0),
        ])
        worker = RenderWorker()

        scores = worker._calculate_frame_importance_vectorized(frames)

        self.assertGreater(scores.iloc[2], scores.iloc[0])
        self.assertGreater(scores.iloc[1], scores.iloc[0])
        self.assertGreater(scores.iloc[4], scores.iloc[0])

    def test_aggregated_view_retains_a_blink_frame(self):
        frames = pd.DataFrame([
            make_render_frame(0.0, 0),
            make_render_frame(100.0, 0),
            make_render_frame(200.0, 3),
            make_render_frame(300.0, 3),
            make_render_frame(400.0, 0),
        ])
        worker = RenderWorker()

        aggregated, is_raw = worker._aggregate_data(frames, num_bins=2, full_df=frames)

        self.assertFalse(is_raw)
        self.assertTrue((aggregated["ch0_function"] == 3).any())


if __name__ == "__main__":
    unittest.main()
