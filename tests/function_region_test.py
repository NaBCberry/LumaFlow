import unittest

import pandas as pd

from core.data_manager import DataManager
from core.undo_manager import SetFunctionInRegionCommand, UndoManager


def make_frame(frame_time_ms, function):
    frame = {
        "frame_time_ms": frame_time_ms,
        "frame_id": int(frame_time_ms // 100) + 1,
        "frame_type": "color",
        "marker": f"M{frame_time_ms}",
    }
    for channel in range(10):
        frame[f"ch{channel}_function"] = function + (channel % 2)
        frame[f"ch{channel}_red"] = channel % 16
        frame[f"ch{channel}_green"] = (channel + 1) % 16
        frame[f"ch{channel}_blue"] = (channel + 2) % 16
    return frame


class SetFunctionInRegionCommandTests(unittest.TestCase):
    def setUp(self):
        self.manager = DataManager()
        self.manager.main_df = pd.DataFrame([
            make_frame(0.0, 0),
            make_frame(100.0, 0),
            make_frame(200.0, 1),
            make_frame(300.0, 1),
        ])
        self.function_columns = [f"ch{i}_function" for i in range(10)]

    def test_execute_updates_closed_interval_and_only_function_columns(self):
        original = self.manager.main_df.copy(deep=True)
        command = SetFunctionInRegionCommand(self.manager, 100.0, 200.0, 3)

        command.execute()

        selected = self.manager.main_df["frame_time_ms"].isin([100.0, 200.0])
        outside = ~selected
        self.assertEqual(2, command.affected_count)
        self.assertTrue((self.manager.main_df.loc[selected, self.function_columns] == 3).all().all())
        pd.testing.assert_frame_equal(
            self.manager.main_df.loc[outside].reset_index(drop=True),
            original.loc[outside].reset_index(drop=True),
        )
        non_function_columns = [
            column for column in original.columns
            if column not in self.function_columns
        ]
        pd.testing.assert_frame_equal(
            self.manager.main_df[non_function_columns],
            original[non_function_columns],
        )

    def test_undo_and_redo_restore_all_original_channel_values(self):
        original = self.manager.main_df.copy(deep=True)
        undo_manager = UndoManager()
        command = SetFunctionInRegionCommand(self.manager, 100.0, 300.0, 2)

        undo_manager.execute(command)
        undo_manager.undo()
        pd.testing.assert_frame_equal(self.manager.main_df, original)

        undo_manager.redo()
        selected = self.manager.main_df["frame_time_ms"].between(100.0, 300.0)
        self.assertTrue((self.manager.main_df.loc[selected, self.function_columns] == 2).all().all())

    def test_rejects_invalid_function(self):
        command = SetFunctionInRegionCommand(self.manager, 0.0, 100.0, 4)
        with self.assertRaises(ValueError):
            command.execute()

    def test_rejects_empty_or_frame_free_selection(self):
        with self.assertRaises(ValueError):
            SetFunctionInRegionCommand(self.manager, 100.0, 100.0, 1).execute()
        with self.assertRaises(ValueError):
            SetFunctionInRegionCommand(self.manager, 401.0, 500.0, 1).execute()


if __name__ == "__main__":
    unittest.main()
