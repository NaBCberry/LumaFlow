import unittest

import pandas as pd

from core.data_manager import DataManager
from core.undo_manager import AdjustBrightnessInRegionCommand, UndoManager


def make_frame(frame_time_ms, offset):
    frame = {
        "frame_time_ms": frame_time_ms,
        "frame_id": int(frame_time_ms // 100) + 1,
        "frame_type": "color",
        "marker": f"M{frame_time_ms}",
    }
    for channel in range(10):
        frame[f"ch{channel}_function"] = channel % 4
        frame[f"ch{channel}_red"] = min(15, 1 + channel + offset)
        frame[f"ch{channel}_green"] = min(15, 7 + channel + offset)
        frame[f"ch{channel}_blue"] = min(15, 12 + channel + offset)
    return frame


class AdjustBrightnessInRegionCommandTests(unittest.TestCase):
    def setUp(self):
        self.manager = DataManager()
        self.manager.main_df = pd.DataFrame([
            make_frame(0.0, 0),
            make_frame(100.0, 0),
            make_frame(200.0, 1),
            make_frame(300.0, 1),
        ])
        self.rgb_columns = AdjustBrightnessInRegionCommand.RGB_COLUMNS

    def test_scales_closed_interval_and_preserves_non_rgb_data(self):
        original = self.manager.main_df.copy(deep=True)
        command = AdjustBrightnessInRegionCommand(
            self.manager,
            100.0,
            200.0,
            150,
        )

        command.execute()

        selected = self.manager.main_df["frame_time_ms"].between(100.0, 200.0)
        expected = (
            original.loc[selected, self.rgb_columns].astype(float) * 1.5 + 0.5
        ).astype(int).clip(lower=0, upper=15)
        pd.testing.assert_frame_equal(
            self.manager.main_df.loc[selected, self.rgb_columns].reset_index(drop=True),
            expected.reset_index(drop=True),
            check_dtype=False,
        )
        self.assertEqual(2, command.affected_count)

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

    def test_undo_and_redo_are_single_deterministic_operation(self):
        original = self.manager.main_df.copy(deep=True)
        undo_manager = UndoManager()
        command = AdjustBrightnessInRegionCommand(
            self.manager,
            100.0,
            300.0,
            60,
        )

        undo_manager.execute(command)
        adjusted = self.manager.main_df.copy(deep=True)
        undo_manager.undo()
        pd.testing.assert_frame_equal(self.manager.main_df, original)

        undo_manager.redo()
        pd.testing.assert_frame_equal(self.manager.main_df, adjusted)

    def test_zero_percent_sets_only_selected_rgb_values_to_zero(self):
        command = AdjustBrightnessInRegionCommand(
            self.manager,
            100.0,
            200.0,
            0,
        )

        command.execute()

        selected = self.manager.main_df["frame_time_ms"].between(100.0, 200.0)
        self.assertTrue(
            (self.manager.main_df.loc[selected, self.rgb_columns] == 0).all().all()
        )

    def test_invalid_percent_or_empty_region_does_not_modify_data(self):
        original = self.manager.main_df.copy(deep=True)

        with self.assertRaises(ValueError):
            AdjustBrightnessInRegionCommand(
                self.manager,
                0.0,
                100.0,
                201,
            ).execute()
        with self.assertRaises(ValueError):
            AdjustBrightnessInRegionCommand(
                self.manager,
                401.0,
                500.0,
                50,
            ).execute()

        pd.testing.assert_frame_equal(self.manager.main_df, original)


if __name__ == "__main__":
    unittest.main()
