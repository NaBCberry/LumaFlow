import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from PySide6.QtWidgets import QApplication

from app_logic import AppLogic
from core.effects import EffectGenerator
from core.i18n import tr
from ui.main_window import MainWindow


app = QApplication.instance() or QApplication([])


def build_anchor_df(times, channel_values):
    rows = []
    for index, frame_time in enumerate(times):
        row = {
            "frame_time_ms": float(frame_time),
            "frame_id": index + 1,
            "frame_type": "color",
            "marker": f"m{index}",
        }
        for channel in range(10):
            values = channel_values[index].get(channel, {})
            row[f"ch{channel}_function"] = values.get("function", 0)
            row[f"ch{channel}_red"] = values.get("r", 0)
            row[f"ch{channel}_green"] = values.get("g", 0)
            row[f"ch{channel}_blue"] = values.get("b", 0)
        rows.append(row)
    return pd.DataFrame(rows)


class IntermediateFrameGeneratorTests(unittest.TestCase):
    def test_generator_adds_forward_hold_frames_between_two_anchors(self):
        anchor_df = build_anchor_df(
            [0.0, 500.0],
            [
                {channel: {"r": 15, "g": 0, "b": 0} for channel in range(10)},
                {channel: {"r": 0, "g": 0, "b": 15} for channel in range(10)},
            ],
        )

        result = EffectGenerator.create_intermediate_fill_df(anchor_df, 200.0, anchor_df.columns)

        self.assertEqual([0.0, 200.0, 400.0, 500.0], result["frame_time_ms"].tolist())
        self.assertEqual([15, 15, 15, 0], result["ch0_red"].tolist())
        self.assertEqual([0, 0, 0, 15], result["ch0_blue"].tolist())
        self.assertEqual(["m0", "", "", "m1"], result["marker"].tolist())
        self.assertEqual(["color", "intermediate_fill", "intermediate_fill", "color"], result["frame_type"].tolist())

    def test_generator_uses_all_anchors_and_keeps_channels_independent(self):
        anchor_df = build_anchor_df(
            [0.0, 500.0, 1000.0],
            [
                {0: {"r": 15}, 1: {"b": 1}},
                {0: {"r": 7}, 1: {"b": 9}},
                {0: {"r": 0}, 1: {"b": 15}},
            ],
        )

        result = EffectGenerator.create_intermediate_fill_df(anchor_df, 200.0, anchor_df.columns)

        self.assertEqual(
            [0.0, 200.0, 400.0, 500.0, 700.0, 900.0, 1000.0],
            result["frame_time_ms"].tolist(),
        )
        self.assertEqual([15, 15, 15, 7, 7, 7, 0], result["ch0_red"].tolist())
        self.assertEqual([1, 1, 1, 9, 9, 9, 15], result["ch1_blue"].tolist())

    def test_generator_does_not_duplicate_existing_anchor_times(self):
        anchor_df = build_anchor_df(
            [0.0, 400.0],
            [
                {channel: {"r": 15} for channel in range(10)},
                {channel: {"r": 0} for channel in range(10)},
            ],
        )

        result = EffectGenerator.create_intermediate_fill_df(anchor_df, 200.0, anchor_df.columns)

        self.assertEqual([0.0, 200.0, 400.0], result["frame_time_ms"].tolist())

    def test_generator_skips_segments_smaller_than_interval(self):
        anchor_df = build_anchor_df(
            [0.0, 100.0, 500.0],
            [
                {channel: {"r": 15} for channel in range(10)},
                {channel: {"r": 7} for channel in range(10)},
                {channel: {"r": 0} for channel in range(10)},
            ],
        )

        result = EffectGenerator.create_intermediate_fill_df(anchor_df, 200.0, anchor_df.columns)

        self.assertEqual([0.0, 100.0, 300.0, 500.0], result["frame_time_ms"].tolist())


class IntermediateFrameUiTests(unittest.TestCase):
    def test_generate_intermediate_frames_requires_region(self):
        window = MainWindow.__new__(MainWindow)
        messages = []
        window.edit_timeline = SimpleNamespace(get_selected_region=lambda: (0.0, 0.0))
        window.set_status_message = messages.append

        window.on_generate_intermediate_frames()

        self.assertEqual([tr("status.generate_intermediate_requires_region")], messages)

    def test_generate_intermediate_frames_requires_two_frames_in_region(self):
        window = MainWindow.__new__(MainWindow)
        messages = []
        emitted = []
        window.edit_timeline = SimpleNamespace(get_selected_region=lambda: (100.0, 500.0))
        window.logic = SimpleNamespace(
            data_manager=SimpleNamespace(get_segment=lambda start, end: pd.DataFrame([{"frame_time_ms": 100.0}]))
        )
        window.generate_intermediate_frames_requested = SimpleNamespace(emit=lambda params: emitted.append(params))
        window.set_status_message = messages.append

        window.on_generate_intermediate_frames()

        self.assertEqual([tr("status.generate_intermediate_requires_two_frames")], messages)
        self.assertEqual([], emitted)

    def test_generate_intermediate_frames_emits_params_when_dialog_accepts(self):
        window = MainWindow.__new__(MainWindow)
        emitted = []
        anchor_df = pd.DataFrame([{"frame_time_ms": 100.0}, {"frame_time_ms": 500.0}])
        window.edit_timeline = SimpleNamespace(get_selected_region=lambda: (100.0, 500.0))
        window.logic = SimpleNamespace(data_manager=SimpleNamespace(get_segment=lambda start, end: anchor_df))
        window.generate_intermediate_frames_requested = SimpleNamespace(emit=lambda params: emitted.append(params))
        window.set_status_message = lambda message: self.fail(f"Unexpected status message: {message}")

        class FakeDialog:
            def __init__(self, *args, **kwargs):
                pass

            def exec(self):
                return True

            def get_params(self):
                return {"interval": 200.0}

        with patch("ui.main_window.EffectDialog", FakeDialog):
            window.on_generate_intermediate_frames()

        self.assertEqual(
            [{"interval": 200.0, "start_ms": 100.0, "end_ms": 500.0}],
            emitted,
        )


class IntermediateFrameLogicTests(unittest.TestCase):
    def test_app_logic_builds_insert_effect_command_for_intermediate_frames(self):
        logic = AppLogic.__new__(AppLogic)
        anchor_df = build_anchor_df(
            [0.0, 500.0, 1000.0],
            [
                {channel: {"r": 15} for channel in range(10)},
                {channel: {"r": 7} for channel in range(10)},
                {channel: {"r": 0} for channel in range(10)},
            ],
        )
        captured = {}
        logic.data_manager = SimpleNamespace(
            get_segment=lambda start, end: anchor_df,
            main_df=anchor_df.copy(),
        )
        logic._execute_command = lambda command, success_message_key=None, failure_message_key=None: captured.update(
            {
                "command": command,
                "success_message_key": success_message_key,
                "failure_message_key": failure_message_key,
            }
        )

        AppLogic.generate_intermediate_frames(
            logic,
            {"start_ms": 0.0, "end_ms": 1000.0, "interval": 200.0},
        )

        self.assertEqual("status.generate_intermediate_success", captured["success_message_key"])
        self.assertEqual("status.generate_intermediate_failed", captured["failure_message_key"])
        self.assertEqual(
            [0.0, 200.0, 400.0, 500.0, 700.0, 900.0, 1000.0],
            captured["command"].effect_df["frame_time_ms"].tolist(),
        )


if __name__ == "__main__":
    unittest.main()
