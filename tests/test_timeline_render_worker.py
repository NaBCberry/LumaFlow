import unittest

import pandas as pd
from PySide6.QtWidgets import QApplication

from ui.timeline_widget import RenderWorker


app = QApplication.instance() or QApplication([])


def build_timeline_df(times):
    rows = []
    for frame_index, frame_time in enumerate(times):
        row = {"frame_time_ms": float(frame_time)}
        for channel in range(10):
            row[f"ch{channel}_red"] = (frame_index + channel) % 16
            row[f"ch{channel}_green"] = (frame_index * 2 + channel) % 16
            row[f"ch{channel}_blue"] = (frame_index * 3 + channel) % 16
            row[f"ch{channel}_function"] = 0
        rows.append(row)
    return pd.DataFrame(rows)


class RenderWorkerTailWidthTests(unittest.TestCase):
    def test_legacy_positional_channel_count_is_supported(self):
        worker = RenderWorker()
        results = []
        worker.finished.connect(lambda *args: results.append(args))
        worker.process_data(build_timeline_df([0, 100]), (0, 100), 1000, 1, 8)
        self.assertEqual([0, 0], results[0][0]['y'].tolist())
        self.assertEqual(8, results[0][-1])

    def _render(self, times, view_range, view_width_pixels):
        worker = RenderWorker()
        results = []
        worker.finished.connect(
            lambda render_data, _rect, is_raw, _range, _generation: results.append((render_data, is_raw))
        )
        worker.process_data(
            build_timeline_df(times),
            view_range,
            view_width_pixels,
            num_channels=1,
            generation=1,
        )
        self.assertEqual(1, len(results))
        return results[0]

    def _tail_end(self, render_data, view_end):
        return max(
            x + w
            for x, w in zip(render_data["x"], render_data["w"])
            if x <= view_end
        )

    def test_merged_view_extends_tail_to_next_real_frame(self):
        render_data, is_raw = self._render(
            [100.0, 200.0, 300.0, 400.0],
            (100.0, 350.0),
            12,
        )

        self.assertFalse(is_raw)
        self.assertEqual(400.0, self._tail_end(render_data, 350.0))

    def test_merged_view_extends_tail_to_view_edge_when_no_next_frame_exists(self):
        render_data, is_raw = self._render(
            [100.0, 200.0, 300.0],
            (100.0, 350.0),
            12,
        )

        self.assertFalse(is_raw)
        self.assertEqual(350.0, self._tail_end(render_data, 350.0))

    def test_raw_and_merged_views_share_same_tail_boundary(self):
        raw_render_data, is_raw = self._render(
            [100.0, 200.0, 300.0, 400.0],
            (100.0, 350.0),
            1000,
        )
        merged_render_data, is_merged_raw = self._render(
            [100.0, 200.0, 300.0, 400.0],
            (100.0, 350.0),
            12,
        )

        self.assertTrue(is_raw)
        self.assertFalse(is_merged_raw)
        self.assertEqual(
            self._tail_end(raw_render_data, 350.0),
            self._tail_end(merged_render_data, 350.0),
        )


if __name__ == "__main__":
    unittest.main()
