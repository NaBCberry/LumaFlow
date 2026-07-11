import unittest

from PySide6.QtWidgets import QApplication

from core.i18n import tr
from ui.timeline_widget import TimelineWidget


app = QApplication.instance() or QApplication([])


class FunctionMenuTests(unittest.TestCase):
    def _capture_context_menu(self, timeline_type):
        timeline = TimelineWidget(timeline_type=timeline_type)
        timeline.set_selected_region(0.0, 100.0)
        menu = timeline._create_context_menu(50.0)
        self.addCleanup(timeline.shutdown)
        self.addCleanup(menu.deleteLater)
        return menu

    def test_edit_context_menu_contains_enabled_function_submenu(self):
        menu = self._capture_context_menu("edit")
        function_actions = [
            action for action in menu.actions()
            if action.menu() and action.menu().title() == tr("menu.set_function")
        ]

        self.assertEqual(1, len(function_actions))
        submenu = function_actions[0].menu()
        self.assertTrue(submenu.isEnabled())
        self.assertEqual(
            [tr(f"function.mode_{mode}") for mode in range(4)],
            [action.text() for action in submenu.actions()],
        )
        self.assertTrue(all(not action.icon().isNull() for action in submenu.actions()))

        brightness_actions = [
            action for action in menu.actions()
            if action.text() == tr("action.adjust_region_brightness")
        ]
        self.assertEqual(1, len(brightness_actions))
        self.assertTrue(brightness_actions[0].isEnabled())

        color_actions = [
            action for action in menu.actions()
            if action.text() == tr("action.set_region_color")
        ]
        self.assertEqual(1, len(color_actions))
        self.assertTrue(color_actions[0].isEnabled())

    def test_material_context_menu_has_no_function_submenu(self):
        menu = self._capture_context_menu("source")
        submenu_titles = [
            action.menu().title()
            for action in menu.actions()
            if action.menu()
        ]
        self.assertNotIn(tr("menu.set_function"), submenu_titles)
        self.assertNotIn(
            tr("action.adjust_region_brightness"),
            [action.text() for action in menu.actions()],
        )
        self.assertNotIn(
            tr("action.set_region_color"),
            [action.text() for action in menu.actions()],
        )


if __name__ == "__main__":
    unittest.main()
