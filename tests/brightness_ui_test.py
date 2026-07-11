import unittest
from types import SimpleNamespace

import pandas as pd
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QMainWindow

from core.i18n import get_language
from ui.main_window import MainWindow


app = QApplication.instance() or QApplication([])


class DataTableStub:
    def __init__(self):
        self.data = None

    def set_data(self, data):
        self.data = data


class ActionHarness(QMainWindow):
    on_quick_adjust_region_brightness = MainWindow.on_quick_adjust_region_brightness
    _apply_region_brightness = MainWindow._apply_region_brightness

    def __init__(self):
        super().__init__()
        self.current_language = get_language()
        self.adjust_calls = []
        self.data_table = DataTableStub()
        self.logic = SimpleNamespace(
            adjust_brightness_in_region=lambda start, end, percent:
                self.adjust_calls.append((start, end, percent)),
            data_manager=SimpleNamespace(
                get_segment=lambda start, end: pd.DataFrame({
                    "frame_time_ms": [start, end],
                })
            ),
        )
        self.edit_timeline = SimpleNamespace(
            get_selected_region=lambda: (100.0, 200.0)
        )
        MainWindow.create_actions(self)

    def _has_last_workspace(self):
        return False

    def _update_function_action_icons(self, theme_name):
        return None

    def on_about(self):
        return None

    def set_status_message(self, message):
        return None


class BrightnessUiTests(unittest.TestCase):
    def setUp(self):
        self.window = ActionHarness()
        self.addCleanup(self.window.deleteLater)

    def test_quick_actions_have_expected_shortcuts_and_start_disabled(self):
        self.assertEqual(
            QKeySequence("Ctrl+Up"),
            self.window.increase_region_brightness_action.shortcut(),
        )
        self.assertEqual(
            QKeySequence("Ctrl+Down"),
            self.window.decrease_region_brightness_action.shortcut(),
        )
        self.assertFalse(self.window.increase_region_brightness_action.isEnabled())
        self.assertFalse(self.window.decrease_region_brightness_action.isEnabled())

    def test_function_actions_use_frequency_based_shortcuts(self):
        self.assertEqual(
            ["Ctrl+1", "Ctrl+2", "Ctrl+3", "Ctrl+4"],
            [action.shortcut().toString() for action in self.window.function_actions],
        )
        self.assertTrue(
            all(not action.isEnabled() for action in self.window.function_actions)
        )

    def test_region_selection_enables_all_brightness_actions(self):
        MainWindow.on_edit_region_selected(self.window, 100.0, 200.0)

        self.assertTrue(self.window.adjust_region_brightness_action.isEnabled())
        self.assertTrue(self.window.set_region_color_action.isEnabled())
        self.assertTrue(self.window.increase_region_brightness_action.isEnabled())
        self.assertTrue(self.window.decrease_region_brightness_action.isEnabled())
        self.assertTrue(
            all(action.isEnabled() for action in self.window.function_actions)
        )

    def test_quick_actions_apply_110_and_90_percent(self):
        self.window.on_quick_adjust_region_brightness(110)
        self.window.on_quick_adjust_region_brightness(90)

        self.assertEqual(
            [(100.0, 200.0, 110), (100.0, 200.0, 90)],
            self.window.adjust_calls,
        )


if __name__ == "__main__":
    unittest.main()
