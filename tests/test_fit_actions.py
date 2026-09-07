import unittest
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from core.i18n import tr
from ui.main_window import MainWindow


app = QApplication.instance() or QApplication([])


class FitActionTests(unittest.TestCase):
    def test_fit_to_view_requires_selection(self):
        window = MainWindow.__new__(MainWindow)
        messages = []
        timeline = SimpleNamespace(region_item=SimpleNamespace(getRegion=lambda: (0.0, 0.0)))
        window.get_active_timeline = lambda: timeline
        window.set_status_message = messages.append

        window.on_fit_to_view()

        self.assertEqual(
            [tr("status.fit_selection_requires_region")],
            messages,
        )

    def test_fit_to_view_uses_selection_without_playhead_dependency(self):
        window = MainWindow.__new__(MainWindow)
        calls = []
        timeline = SimpleNamespace(
            region_item=SimpleNamespace(getRegion=lambda: (100.0, 300.0)),
            set_view_range_clamped=lambda start, end: calls.append((start, end)),
        )
        window.get_active_timeline = lambda: timeline
        window.set_status_message = lambda message: self.fail(f"Unexpected status message: {message}")

        window.on_fit_to_view()

        self.assertEqual([(90.0, 310.0)], calls)

    def test_fit_active_timeline_to_all_uses_source_data_for_source_timeline(self):
        window = MainWindow.__new__(MainWindow)
        source_calls = []
        source_timeline = SimpleNamespace(set_data=lambda data, auto_zoom: source_calls.append((data, auto_zoom)))
        edit_timeline = SimpleNamespace(set_data=lambda data, auto_zoom: self.fail("Edit timeline should not be used"))
        window.source_timeline = source_timeline
        window.edit_timeline = edit_timeline
        window.get_active_timeline = lambda: source_timeline
        window.logic = SimpleNamespace(
            source_data_manager=SimpleNamespace(get_full_data=lambda: "source-data"),
            data_manager=SimpleNamespace(get_full_data=lambda: "edit-data"),
        )
        window.should_auto_zoom = False

        window.fit_active_timeline_to_all()

        self.assertEqual([("source-data", True)], source_calls)
        self.assertFalse(window.should_auto_zoom)


if __name__ == "__main__":
    unittest.main()
