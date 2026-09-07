import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QSlider

from core.media_formats import is_audio_file
from ui.video_player_widget import VideoPlayerWidget


app = QApplication.instance() or QApplication([])


class _TimerStub:
    def __init__(self):
        self.start_calls = 0
        self.stop_calls = 0

    def start(self):
        self.start_calls += 1

    def stop(self):
        self.stop_calls += 1


class _MediaPlayerStub:
    def __init__(self, *, length=5000, time_ms=0, playing=False):
        self.length = length
        self.time_ms = time_ms
        self.playing = playing
        self.set_time_calls = []
        self.stop_calls = 0
        self.media = None

    def get_length(self):
        return self.length

    def get_time(self):
        return self.time_ms

    def set_time(self, position_ms):
        self.time_ms = position_ms
        self.set_time_calls.append(position_ms)

    def is_playing(self):
        return self.playing

    def pause(self):
        self.playing = False

    def play(self):
        self.playing = True

    def video_set_scale(self, _scale):
        pass

    def stop(self):
        self.playing = False
        self.time_ms = 0
        self.stop_calls += 1

    def set_media(self, media):
        self.media = media


class _InstanceStub:
    def __init__(self):
        self.paths = []

    def media_new(self, path):
        self.paths.append(path)
        return SimpleNamespace(path=path)


def build_player(*, length=5000, time_ms=0, playing=False):
    player = VideoPlayerWidget.__new__(VideoPlayerWidget)
    player.time_label = QLabel()
    player.percentage_label = QLabel()
    player.play_button = QPushButton()
    player.volume_slider = QSlider()
    player.style = lambda: QApplication.style()
    player.media_player = _MediaPlayerStub(length=length, time_ms=time_ms, playing=playing)
    player.instance = _InstanceStub()
    player.master_clock_timer = _TimerStub()
    player.position_changed_manually_events = []
    player.position_changed_playback_events = []
    player.playback_stopped_events = []
    player.playback_started_events = []
    player.media_loaded_events = []
    player.position_changed_manually = SimpleNamespace(
        emit=lambda value: player.position_changed_manually_events.append(value)
    )
    player.position_changed_during_playback = SimpleNamespace(
        emit=lambda value: player.position_changed_playback_events.append(value)
    )
    player.playback_stopped = SimpleNamespace(
        emit=lambda: player.playback_stopped_events.append(True)
    )
    player.playback_started = SimpleNamespace(
        emit=lambda: player.playback_started_events.append(True)
    )
    player.media_loaded = SimpleNamespace(
        emit=lambda value: player.media_loaded_events.append(value)
    )
    player._is_media_loaded = True
    player._is_playing = playing
    player._is_fullscreen = False
    player._auto_pause_on_play = False
    player._video_output_generation = 0
    player._video_output_visible = True
    player._last_video_handle = None
    player._has_reached_end = False
    player._restoring_end_frame = False
    player._media_restart_generation = 0
    player._pending_media_reload = None
    player._emit_media_loaded_on_ready = False
    player._is_audio_only = False
    player._attach_video_to_frame = lambda: True
    player._current_video_path = "demo.mp4"
    player.current_time_ms = time_ms
    player.total_duration_ms = length
    player.playback_start_time = 0.0
    player.playback_start_offset_ms = 0
    player.last_vlc_time_ms = -1
    player.vlc_read_counter = 0
    player.last_reported_vlc_time = -1
    player.smooth_drift = 0.0
    player.last_tick_perf = 1.0
    return player


class VideoPlayerWidgetTests(unittest.TestCase):
    def test_vlc_time_callback_only_emits_a_qt_signal(self):
        player = SimpleNamespace(_vlc_time_changed_signal=Mock())
        VideoPlayerWidget._on_vlc_time_changed(player, SimpleNamespace(u=SimpleNamespace(new_time=1250)))
        player._vlc_time_changed_signal.emit.assert_called_once_with(1250)

    def test_vlc_error_callback_only_emits_a_qt_signal(self):
        player = SimpleNamespace(_vlc_error_signal=Mock())
        VideoPlayerWidget._on_vlc_error(player)
        player._vlc_error_signal.emit.assert_called_once_with()

    def test_vlc_time_updates_require_loaded_paused_media(self):
        player = build_player()
        player._update_position_widgets = Mock()
        player._handle_vlc_time_changed(1200)
        player._update_position_widgets.assert_called_once_with(1200)
        player._update_position_widgets.reset_mock()
        player._is_playing = True
        player._handle_vlc_time_changed(1300)
        player._is_playing = False
        player._is_media_loaded = False
        player._handle_vlc_time_changed(1400)
        player._update_position_widgets.assert_not_called()

    def test_loading_audio_exits_fullscreen_and_cancels_old_callbacks(self):
        player = build_player()
        player._is_fullscreen = True
        player.exit_fullscreen = Mock()
        player._single_click_timer = Mock()
        old_timer = Mock()
        player._media_load_timer = old_timer
        player.video_frame = Mock()
        player.fullscreen_button = Mock()
        player.file_label = Mock()
        player.media_player.get_media = Mock(return_value=None)
        player.instance.media_new = Mock(return_value=Mock())
        with patch('ui.video_player_widget.QTimer'):
            player.load_media('reference.MP3')
        player.exit_fullscreen.assert_called_once()
        player._single_click_timer.stop.assert_called_once()
        old_timer.stop.assert_called_once()
        old_timer.deleteLater.assert_called_once()
        player.video_frame.setVisible.assert_called_once_with(False)
        player.fullscreen_button.setVisible.assert_called_once_with(False)
        self.assertTrue(player._is_audio_only)
        self.assertEqual(1, player._video_output_generation)
        self.assertEqual(1, player.master_clock_timer.stop_calls)

    def test_audio_ignores_pending_paused_video_refresh(self):
        player = build_player()
        callbacks = []
        with patch('ui.video_player_widget.QTimer.singleShot',
                   side_effect=lambda delay, callback: callbacks.append(callback)):
            player._refresh_paused_video_frame(2500, 0)
        player._is_audio_only = True
        callbacks[0]()
        self.assertEqual([], player.media_player.set_time_calls)

    def test_common_audio_extensions_are_detected(self):
        self.assertTrue(is_audio_file("reference.MP3"))
        self.assertTrue(is_audio_file("reference.flac"))
        self.assertFalse(is_audio_file("reference.mp4"))

    def test_legacy_video_loader_delegates_to_media_loader(self):
        player = build_player()
        with patch.object(player, "load_media") as load_media:
            player.load_video("reference.mp3")

        load_media.assert_called_once_with("reference.mp3")

    def test_apply_loaded_media_state_updates_time_label_and_percentage(self):
        player = build_player(length=3_723_004, time_ms=0)

        player._apply_loaded_media_state(3_723_004)

        self.assertEqual(3_723_004, player.total_duration_ms)
        self.assertEqual(
            "00:00:00.000 / 01:02:03.004",
            player.time_label.text(),
        )
        self.assertEqual("0.0%", player.percentage_label.text())

    def test_initial_media_load_emits_duration_only_once(self):
        player = build_player(length=5000)
        player._emit_media_loaded_on_ready = True

        player._apply_loaded_media_state(5000)
        player._apply_loaded_media_state(5000)

        self.assertEqual([5000], player.media_loaded_events)

    def test_seek_to_time_clamps_and_emits_manual_position_change(self):
        player = build_player(length=5000, time_ms=1000)

        actual_time = player.seek_to_time(6000)

        self.assertEqual(4999, actual_time)
        self.assertEqual([4999], player.media_player.set_time_calls)
        self.assertEqual([4999], player.position_changed_manually_events)
        self.assertEqual("00:00:04.999 / 00:00:05.000", player.time_label.text())
        self.assertEqual("100.0%", player.percentage_label.text())

    def test_master_tick_updates_time_display_percentage_and_playback_signal(self):
        player = build_player(length=5000, time_ms=1000, playing=True)
        player.last_tick_perf = 1.0
        player.media_player.time_ms = 1250

        with patch("ui.video_player_widget.time.perf_counter", return_value=1.01):
            player._on_master_tick()

        self.assertEqual([1012], player.position_changed_playback_events)
        self.assertEqual("00:00:01.012 / 00:00:05.000", player.time_label.text())
        self.assertEqual("20.2%", player.percentage_label.text())

    def test_handle_vlc_paused_syncs_time_label_from_vlc(self):
        player = build_player(length=5000, time_ms=1000, playing=True)
        player.media_player.time_ms = 2345

        player._handle_vlc_paused()

        self.assertEqual(1, player.master_clock_timer.stop_calls)
        self.assertFalse(player._is_playing)
        self.assertEqual(2345, player.current_time_ms)
        self.assertEqual("00:00:02.345 / 00:00:05.000", player.time_label.text())
        self.assertEqual("46.9%", player.percentage_label.text())

    def test_stop_resets_current_position_but_keeps_total_duration_display(self):
        player = build_player(length=5000, time_ms=2345, playing=True)

        player.stop()

        self.assertEqual(1, player.master_clock_timer.stop_calls)
        self.assertEqual(1, player.media_player.stop_calls)
        self.assertFalse(player._is_playing)
        self.assertEqual(0, player.current_time_ms)
        self.assertEqual("00:00:00.000 / 00:00:05.000", player.time_label.text())
        self.assertEqual("0.0%", player.percentage_label.text())

    def test_hidden_output_invalidates_pending_restore(self):
        player = build_player()
        player._video_output_generation = 4

        player.set_output_visible(False)

        self.assertFalse(player._video_output_visible)
        self.assertEqual(5, player._video_output_generation)

    def test_restore_is_scheduled_after_dock_becomes_visible(self):
        player = build_player()
        scheduled = []

        with patch(
            "ui.video_player_widget.QTimer.singleShot",
            side_effect=lambda delay, callback: scheduled.append((delay, callback)),
        ):
            player.set_output_visible(True)

        self.assertEqual([0, 80, 250], [delay for delay, _callback in scheduled])
        self.assertEqual(1, player._video_output_generation)

    def test_audio_only_media_skips_video_output_restore(self):
        player = build_player()
        player._is_audio_only = True

        with patch("ui.video_player_widget.QTimer.singleShot") as single_shot:
            player.set_output_visible(True)

        single_shot.assert_not_called()

    def test_end_reloads_media_and_keeps_final_frame_visible(self):
        player = build_player(length=5000, time_ms=5000, playing=True)

        with patch(
            "ui.video_player_widget.QTimer.singleShot",
            side_effect=lambda _delay, callback: callback(),
        ):
            player._handle_vlc_end_reached()

        self.assertTrue(player._has_reached_end)
        self.assertFalse(player._is_playing)
        self.assertEqual([4900], player.media_player.set_time_calls)
        self.assertEqual(5000, player.current_time_ms)
        self.assertEqual([True], player.playback_stopped_events)

    def test_audio_end_stays_seekable_without_reloading_a_final_frame(self):
        player = build_player(length=5000, time_ms=5000, playing=True)
        player._is_audio_only = True

        with patch.object(player, "_reload_media_at") as reload_media:
            player._handle_vlc_end_reached()

        reload_media.assert_not_called()
        self.assertTrue(player._has_reached_end)
        self.assertFalse(player._restoring_end_frame)
        self.assertEqual(5000, player.current_time_ms)

    def test_seek_after_end_reloads_at_requested_position(self):
        player = build_player(length=5000, time_ms=5000)
        player._has_reached_end = True

        with patch.object(player, "_reload_media_at") as reload_media:
            actual_time = player.seek_to_time(2300)

        reload_media.assert_called_once_with(2300, play_after_reload=False)
        self.assertEqual(2300, actual_time)
        self.assertFalse(player._has_reached_end)

    def test_play_after_end_restarts_from_beginning(self):
        player = build_player(length=5000, time_ms=5000)
        player._has_reached_end = True

        with patch.object(player, "_reload_media_at") as reload_media:
            player.play_clicked()

        reload_media.assert_called_once_with(0, play_after_reload=True)
        self.assertEqual([True], player.playback_started_events)


if __name__ == "__main__":
    unittest.main()
