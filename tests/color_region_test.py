import unittest
import colorsys

import pandas as pd
from PySide6.QtWidgets import QApplication

from core.data_manager import DataManager
from core.i18n import tr
from core.undo_manager import SetColorInRegionCommand, UndoManager
from ui.dialogs import ColorPickerDialog
from utils.numba_funcs import hsv_to_rgb_4bit


app = QApplication.instance() or QApplication([])


def make_frame(frame_time_ms, offset):
    frame = {
        "frame_time_ms": frame_time_ms,
        "frame_id": int(frame_time_ms // 100) + 1,
        "frame_type": "color",
        "marker": f"M{frame_time_ms}",
    }
    for channel in range(10):
        frame[f"ch{channel}_function"] = (channel + offset) % 4
        frame[f"ch{channel}_red"] = min(15, channel + offset)
        frame[f"ch{channel}_green"] = min(15, channel + offset + 2)
        frame[f"ch{channel}_blue"] = min(15, channel + offset + 4)
    return frame


class SetColorInRegionCommandTests(unittest.TestCase):
    def setUp(self):
        self.manager = DataManager()
        self.manager.main_df = pd.DataFrame([
            make_frame(0.0, 0),
            make_frame(100.0, 0),
            make_frame(200.0, 1),
            make_frame(300.0, 1),
        ])
        self.rgb_columns = SetColorInRegionCommand.RGB_COLUMNS
        self.function_columns = [f"ch{channel}_function" for channel in range(10)]

    def test_sets_all_channels_in_closed_interval_without_changing_function(self):
        original = self.manager.main_df.copy(deep=True)
        command = SetColorInRegionCommand(
            self.manager,
            100.0,
            200.0,
            {'r': 3, 'g': 8, 'b': 14},
        )

        command.execute()

        selected = self.manager.main_df["frame_time_ms"].between(100.0, 200.0)
        for channel in range(10):
            self.assertTrue(
                (self.manager.main_df.loc[selected, f"ch{channel}_red"] == 3).all()
            )
            self.assertTrue(
                (self.manager.main_df.loc[selected, f"ch{channel}_green"] == 8).all()
            )
            self.assertTrue(
                (self.manager.main_df.loc[selected, f"ch{channel}_blue"] == 14).all()
            )
        self.assertEqual(2, command.affected_count)
        pd.testing.assert_frame_equal(
            self.manager.main_df[self.function_columns],
            original[self.function_columns],
        )

        outside = ~selected
        pd.testing.assert_frame_equal(
            self.manager.main_df.loc[outside].reset_index(drop=True),
            original.loc[outside].reset_index(drop=True),
        )
        non_rgb_columns = [
            column for column in original.columns
            if column not in self.rgb_columns
        ]
        pd.testing.assert_frame_equal(
            self.manager.main_df[non_rgb_columns],
            original[non_rgb_columns],
        )

    def test_undo_and_redo_restore_the_entire_region(self):
        original = self.manager.main_df.copy(deep=True)
        undo_manager = UndoManager()
        command = SetColorInRegionCommand(
            self.manager,
            100.0,
            300.0,
            {'r': 15, 'g': 0, 'b': 6},
        )

        undo_manager.execute(command)
        adjusted = self.manager.main_df.copy(deep=True)
        undo_manager.undo()
        pd.testing.assert_frame_equal(self.manager.main_df, original)

        undo_manager.redo()
        pd.testing.assert_frame_equal(self.manager.main_df, adjusted)

    def test_invalid_color_or_empty_region_does_not_modify_data(self):
        original = self.manager.main_df.copy(deep=True)

        with self.assertRaises(ValueError):
            SetColorInRegionCommand(
                self.manager,
                0.0,
                100.0,
                {'r': 16, 'g': 0, 'b': 0},
            ).execute()
        with self.assertRaises(ValueError):
            SetColorInRegionCommand(
                self.manager,
                401.0,
                500.0,
                {'r': 1, 'g': 2, 'b': 3},
            ).execute()

        pd.testing.assert_frame_equal(self.manager.main_df, original)


class RegionColorDialogTests(unittest.TestCase):
    def test_color_only_mode_hides_function_and_marker_options(self):
        dialog = ColorPickerDialog(
            prefill_color={'r': 2, 'g': 4, 'b': 6},
            color_only=True,
        )
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(tr("dialog.region_color.title"), dialog.windowTitle())
        self.assertTrue(dialog.options_group.isHidden())
        self.assertEqual(
            {'r': 2, 'g': 4, 'b': 6},
            dialog.get_values()['color'],
        )

    def test_prefill_color_initializes_wheel_before_brightness_adjustment(self):
        color = {'r': 9, 'g': 11, 'b': 15}
        dialog = ColorPickerDialog(prefill_color=color, color_only=True)
        self.addCleanup(dialog.deleteLater)
        expected_hue, expected_saturation, expected_value = colorsys.rgb_to_hsv(
            color['r'] / 15.0,
            color['g'] / 15.0,
            color['b'] / 15.0,
        )

        self.assertAlmostEqual(expected_hue, dialog.color_wheel.selected_hue)
        self.assertAlmostEqual(expected_saturation, dialog.color_wheel.selected_saturation)
        self.assertAlmostEqual(expected_value, dialog.color_wheel.selected_value)
        self.assertEqual(round(expected_value * 100), dialog.brightness_slider.value())

        dialog.brightness_slider.setValue(50)
        expected_rgb = hsv_to_rgb_4bit(expected_hue, expected_saturation, 0.5)
        self.assertEqual(
            {'r': expected_rgb[0], 'g': expected_rgb[1], 'b': expected_rgb[2]},
            dialog.get_values()['color'],
        )

    def test_preset_color_updates_wheel_hue_used_by_brightness(self):
        dialog = ColorPickerDialog(
            prefill_color={'r': 15, 'g': 0, 'b': 0},
            color_only=True,
        )
        self.addCleanup(dialog.deleteLater)

        dialog.set_preset_color(0, 15, 0)
        dialog.brightness_slider.setValue(50)

        self.assertEqual(
            {'r': 0, 'g': 8, 'b': 0},
            dialog.get_values()['color'],
        )


if __name__ == "__main__":
    unittest.main()
