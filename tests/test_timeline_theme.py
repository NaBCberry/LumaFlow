import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.timeline_theme import THEME_PROFILES, get_visual_theme_profile


app = QApplication.instance() or QApplication([])


class TimelineThemeTests(unittest.TestCase):
    def test_theme_profiles_include_required_fields(self):
        dark = get_visual_theme_profile("dark_theme")
        light = get_visual_theme_profile("light_theme")

        self.assertEqual(set(dark.keys()), set(light.keys()))
        self.assertIn("timeline_background", dark)
        self.assertIn("audio_background", dark)
        self.assertIn("axis_text", dark)

    def test_set_theme_propagates_to_timeline_groups(self):
        window = MainWindow.__new__(MainWindow)
        source_calls = []
        edit_calls = []
        window.source_timeline_group = type(
            "GroupStub",
            (),
            {"apply_visual_theme": lambda self, theme_name: source_calls.append(theme_name)},
        )()
        window.edit_timeline_group = type(
            "GroupStub",
            (),
            {"apply_visual_theme": lambda self, theme_name: edit_calls.append(theme_name)},
        )()
        window.set_status_message = lambda message: self.fail(message)

        style_path = Path("resources/styles/dark_theme.qss").resolve()
        app_stub = type(
            "AppStub",
            (),
            {"setStyleSheet": lambda self, stylesheet: None},
        )()
        with patch("ui.main_window.resource_path", return_value=style_path):
            with patch("ui.main_window.QApplication.instance", return_value=app_stub):
                MainWindow.set_theme(window, "dark_theme")

        self.assertEqual(["dark_theme"], source_calls)
        self.assertEqual(["dark_theme"], edit_calls)

if __name__ == "__main__":
    unittest.main()
