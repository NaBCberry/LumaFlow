import unittest
from unittest.mock import patch

from core.i18n import tr
from ui.main_window import LAST_WORKSPACE_SETTING_KEYS, MainWindow


class FakeSettings:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def value(self, key, default=None, value_type=None):
        value = self.values.get(key, default)
        if value_type is str:
            return str(value)
        return value

    def setValue(self, key, value):
        self.values[key] = value


class ActionStub:
    def __init__(self):
        self.enabled = None

    def setEnabled(self, enabled):
        self.enabled = bool(enabled)


class PreviewStub:
    def __init__(self):
        self.loaded = []

    def load_video(self, file_path):
        self.loaded.append(file_path)


class LogicStub:
    def __init__(self):
        self.current_file_path = None
        self.current_source_file_path = None
        self.current_edit_video_path = None
        self.current_source_video_path = None
        self.opened_edit = []
        self.opened_source = []
        self.loaded_audio = []
        self.edit_result = True
        self.source_result = True

    def open_file(self, file_path):
        self.opened_edit.append(file_path)
        return self.edit_result

    def open_source_file(self, file_path):
        self.opened_source.append(file_path)
        return self.source_result

    def load_video_audio(self, file_path, timeline_type):
        self.loaded_audio.append((file_path, timeline_type))


class WorkspaceHarness:
    _get_last_workspace_paths = MainWindow._get_last_workspace_paths
    _has_last_workspace = MainWindow._has_last_workspace
    _save_last_workspace = MainWindow._save_last_workspace
    _load_workspace_video = MainWindow._load_workspace_video
    on_open_last_workspace = MainWindow.on_open_last_workspace

    def __init__(self):
        self.logic = LogicStub()
        self.open_last_workspace_action = ActionStub()
        self.source_preview_widget = PreviewStub()
        self.edit_preview_widget = PreviewStub()
        self.status_messages = []

    def set_status_message(self, message):
        self.status_messages.append(message)


class WorkspaceRestoreTests(unittest.TestCase):
    def test_save_last_workspace_persists_all_open_resources(self):
        settings = FakeSettings()
        window = WorkspaceHarness()
        window.logic.current_file_path = "edit.csv"
        window.logic.current_source_file_path = "source.csv"
        window.logic.current_edit_video_path = "edit.mp4"
        window.logic.current_source_video_path = "source.mp4"

        with patch("ui.main_window.QSettings", return_value=settings):
            window._save_last_workspace()

        self.assertEqual(
            {
                LAST_WORKSPACE_SETTING_KEYS["edit_file"]: "edit.csv",
                LAST_WORKSPACE_SETTING_KEYS["source_file"]: "source.csv",
                LAST_WORKSPACE_SETTING_KEYS["edit_video"]: "edit.mp4",
                LAST_WORKSPACE_SETTING_KEYS["source_video"]: "source.mp4",
            },
            settings.values,
        )
        self.assertTrue(window.open_last_workspace_action.enabled)

    def test_restore_loads_files_and_videos_through_existing_paths(self):
        paths = {
            LAST_WORKSPACE_SETTING_KEYS["edit_file"]: "edit.csv",
            LAST_WORKSPACE_SETTING_KEYS["source_file"]: "source.csv",
            LAST_WORKSPACE_SETTING_KEYS["edit_video"]: "edit.mp4",
            LAST_WORKSPACE_SETTING_KEYS["source_video"]: "source.mp4",
        }
        settings = FakeSettings(paths)
        window = WorkspaceHarness()

        with patch("ui.main_window.QSettings", return_value=settings), patch(
            "ui.main_window.os.path.isfile",
            return_value=True,
        ):
            window.on_open_last_workspace()

        self.assertEqual(["edit.csv"], window.logic.opened_edit)
        self.assertEqual(["source.csv"], window.logic.opened_source)
        self.assertEqual(["source.mp4"], window.source_preview_widget.loaded)
        self.assertEqual(["edit.mp4"], window.edit_preview_widget.loaded)
        self.assertEqual(
            [("source.mp4", "source"), ("edit.mp4", "edit")],
            window.logic.loaded_audio,
        )
        self.assertEqual(
            tr("status.last_workspace_restored", count=4),
            window.status_messages[-1],
        )

    def test_restore_continues_when_resources_are_missing_or_invalid(self):
        paths = {
            LAST_WORKSPACE_SETTING_KEYS["edit_file"]: "edit.csv",
            LAST_WORKSPACE_SETTING_KEYS["source_file"]: "source.csv",
            LAST_WORKSPACE_SETTING_KEYS["edit_video"]: "missing.mp4",
        }
        settings = FakeSettings(paths)
        window = WorkspaceHarness()
        window.logic.source_result = False

        with patch("ui.main_window.QSettings", return_value=settings), patch(
            "ui.main_window.os.path.isfile",
            side_effect=lambda path: path != "missing.mp4",
        ):
            window.on_open_last_workspace()

        self.assertEqual(["edit.csv"], window.logic.opened_edit)
        self.assertEqual(["source.csv"], window.logic.opened_source)
        self.assertEqual(
            tr("status.last_workspace_partial", loaded=1, failed=2),
            window.status_messages[-1],
        )

    def test_no_saved_workspace_reports_status_without_loading(self):
        settings = FakeSettings()
        window = WorkspaceHarness()

        with patch("ui.main_window.QSettings", return_value=settings):
            window.on_open_last_workspace()

        self.assertEqual(
            tr("status.no_last_workspace"),
            window.status_messages[-1],
        )
        self.assertEqual([], window.logic.opened_edit)
        self.assertEqual([], window.logic.loaded_audio)


if __name__ == "__main__":
    unittest.main()
