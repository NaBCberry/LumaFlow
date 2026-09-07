import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from app_logic import AppLogic


def make_logic(source='shared.mp3', edit='shared.mp3'):
    return SimpleNamespace(
        current_source_video_path=source,
        current_edit_video_path=edit,
        source_audio_duration_ms=None,
        edit_audio_duration_ms=None,
        audio_channel_modes={'source': 'mono', 'edit': 'mono'},
        audio_manager=Mock(),
        _timeline_display_name=Mock(return_value='edit'),
        source_audio_processed=Mock(),
        edit_audio_processed=Mock(),
        audio_processing_failed=Mock(),
        audio_progress=Mock(),
        status_message_changed=Mock(),
    )


class MediaRoutingTests(unittest.TestCase):
    def test_shared_reference_updates_both_workspaces(self):
        logic = make_logic()
        data = SimpleNamespace(duration_ms=5000, sample_rate=44100, channel_mode='mono')
        AppLogic._on_audio_processed(logic, 'shared.mp3', data)
        logic.source_audio_processed.emit.assert_called_once_with(data)
        logic.edit_audio_processed.emit.assert_called_once_with(data)
        self.assertEqual(5000, logic.source_audio_duration_ms)
        self.assertEqual(5000, logic.edit_audio_duration_ms)

    def test_shared_reference_routes_progress_and_errors_to_both(self):
        logic = make_logic()
        AppLogic._on_audio_progress(logic, 'shared.mp3', 'decode', 20)
        AppLogic._on_audio_failed(logic, 'shared.mp3', 'decode failed')
        self.assertEqual(
            [('source', 'decode', 20), ('edit', 'decode', 20)],
            [call.args for call in logic.audio_progress.emit.call_args_list],
        )
        self.assertEqual(
            [('source', 'decode failed'), ('edit', 'decode failed')],
            [call.args for call in logic.audio_processing_failed.emit.call_args_list],
        )

    def test_shared_reference_preserves_independent_channel_modes(self):
        logic = make_logic()
        logic.audio_channel_modes = {'source': 'left', 'edit': 'right'}
        left = SimpleNamespace(duration_ms=5000, sample_rate=44100, channel_mode='left')
        right = SimpleNamespace(duration_ms=5000, sample_rate=44100, channel_mode='right')
        stale = SimpleNamespace(duration_ms=5000, sample_rate=44100, channel_mode='mono')
        for data in (left, right, stale):
            AppLogic._on_audio_processed(logic, 'shared.mp3', data)
        logic.source_audio_processed.emit.assert_called_once_with(left)
        logic.edit_audio_processed.emit.assert_called_once_with(right)

    def test_mode_is_recorded_before_synchronous_cache_result(self):
        logic = make_logic()
        data = SimpleNamespace(duration_ms=5000, sample_rate=44100, channel_mode='right')
        logic.audio_manager.extract_audio.side_effect = (
            lambda path, mode: AppLogic._on_audio_processed(logic, path, data)
        )
        AppLogic.change_audio_channel_mode(logic, 'edit', 'shared.mp3', 'right')
        logic.edit_audio_processed.emit.assert_called_once_with(data)
        logic.source_audio_processed.emit.assert_not_called()

    def test_new_reference_resets_mode_and_duration(self):
        logic = make_logic()
        logic.audio_channel_modes['edit'] = 'left'
        logic.edit_audio_duration_ms = 5000
        AppLogic.load_video_audio(logic, 'new.mp3', 'edit')
        self.assertEqual('new.mp3', logic.current_edit_video_path)
        self.assertEqual('mono', logic.audio_channel_modes['edit'])
        self.assertIsNone(logic.edit_audio_duration_ms)
        logic.audio_manager.extract_audio.assert_called_once_with('new.mp3', 'mono')

    def test_replaced_reference_callbacks_are_ignored(self):
        logic = make_logic()
        AppLogic._on_audio_processed(logic, 'old.mp3', Mock())
        AppLogic._on_audio_failed(logic, 'old.mp3', 'failed')
        AppLogic._on_audio_progress(logic, 'old.mp3', 'decode', 90)
        for signal in (
            logic.source_audio_processed, logic.edit_audio_processed,
            logic.audio_processing_failed, logic.audio_progress,
            logic.status_message_changed,
        ):
            signal.emit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
