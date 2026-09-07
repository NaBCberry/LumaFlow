import unittest

import pandas as pd

from core.data_manager import DataManager
from core.undo_manager import AddMarkerCommand, UpdateFrameCommand, UpdateMarkerCommand


class MarkerDtypeTests(unittest.TestCase):
    def setUp(self):
        self.manager = DataManager()
        self.manager.main_df = pd.DataFrame(
            {
                "frame_time_ms": [0.0, 100.0],
                "marker": [0, 0],
                **{
                    f"ch{channel}_{component}": [0, 0]
                    for channel in range(10)
                    for component in ("function", "red", "green", "blue")
                },
            }
        )

    def test_add_hex_marker_to_numeric_marker_column(self):
        command = AddMarkerCommand(self.manager, 100.0, "66CCFF")

        command.execute()

        self.assertEqual("66CCFF", self.manager.main_df.loc[1, "marker"])
        self.assertEqual(object, self.manager.main_df["marker"].dtype)
        self.assertEqual("", self.manager.main_df.loc[0, "marker"])
        command.undo()
        self.assertEqual("", self.manager.main_df.loc[1, "marker"])

    def test_update_marker_and_frame_share_safe_string_write(self):
        UpdateMarkerCommand(self.manager, 0.0, "Intro").execute()
        self.assertEqual("Intro", self.manager.main_df.loc[0, "marker"])

        UpdateFrameCommand(
            self.manager,
            100.0,
            {"r": 1, "g": 2, "b": 3},
            0,
            "66CCFF",
        ).execute()
        self.assertEqual("66CCFF", self.manager.main_df.loc[1, "marker"])


if __name__ == "__main__":
    unittest.main()
