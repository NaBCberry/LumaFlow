import re
import unittest
from pathlib import Path


class ThemeStyleTests(unittest.TestCase):
    @staticmethod
    def _style_rule(stylesheet, selector):
        match = re.search(
            rf"{re.escape(selector)}\s*\{{(?P<body>.*?)\}}",
            stylesheet,
            re.DOTALL,
        )
        if match is None:
            raise AssertionError(f"Missing stylesheet rule: {selector}")
        return match.group("body")

    def test_widget_chrome_is_explicitly_themed(self):
        expected_colors = {
            "light_theme": ("#FFFFFF", "#333333", "#EAEAEA"),
            "dark_theme": ("#2A2A2A", "#DCDCDC", "#3C3C3C"),
        }

        for theme_name, (field_bg, text_color, title_bg) in expected_colors.items():
            stylesheet = Path(f"resources/styles/{theme_name}.qss").read_text(
                encoding="utf-8"
            )
            combo_rule = self._style_rule(stylesheet, "QComboBox")
            popup_rule = self._style_rule(stylesheet, "QComboBox QAbstractItemView")
            dock_title_rule = self._style_rule(stylesheet, "QDockWidget::title")

            self.assertIn(f"background-color: {field_bg}", combo_rule)
            self.assertIn(f"color: {text_color}", combo_rule)
            self.assertIn(f"background-color: {field_bg}", popup_rule)
            self.assertIn(f"color: {text_color}", popup_rule)
            self.assertIn(f"background-color: {title_bg}", dock_title_rule)
            self.assertIn(f"color: {text_color}", dock_title_rule)


if __name__ == "__main__":
    unittest.main()
