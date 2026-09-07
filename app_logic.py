import time

from PySide6.QtCore import QObject, Signal, Slot, QThread
import pandas as pd

from core.data_manager import DataManager
from core.undo_manager import AdjustBrightnessInRegionCommand, SetColorInRegionCommand, UndoManager, CutCommand, CopyCommand, PasteCommand, DeleteCommand, InsertEffectCommand, AddMarkerCommand, UpdateMarkerCommand, InsertFrameCommand, OffsetCommand, SetFunctionInRegionCommand, UpdateFrameCommand
from core.clipboard_manager import ClipboardManager
from core.effects import EffectGenerator
from core.audio_manager import AudioManager
from core.serial_device_manager import SerialDeviceManager
from core.device_output_worker import DeviceOutputWorker
from core.color_calibration import color_calibration
from core.i18n import tr
from core.serial_protocol import (
    GLOBAL_BRIGHTNESS_DEFAULT,
    GLOBAL_BRIGHTNESS_MAX,
    GLOBAL_BRIGHTNESS_MIN,
    build_auth_frame,
    build_stream_frame,
    describe_auth_lic,
)

class AppLogic(QObject):
    # Signals to update the UI
    timeline_data_changed = Signal(pd.DataFrame)
    source_data_changed = Signal(pd.DataFrame)
    status_message_changed = Signal(str)
    undo_stack_changed = Signal(bool)
    redo_stack_changed = Signal(bool)
    # New signal for clipboard state
    clipboard_changed = Signal(bool, str)  # (has_data, source_type)
    # New signal for updating selection region after offset
    offset_applied = Signal(float, float)  # (new_start_ms, new_end_ms)
    # Audio signals
    source_audio_processed = Signal(object)  # AudioData
    edit_audio_processed = Signal(object)    # AudioData
    audio_processing_failed = Signal(str, str)  # timeline_type, error_message
    audio_progress = Signal(str, str, int)  # timeline_type, stage, percentage
    # Device output signals
    serial_connection_changed = Signal(bool, str)  # (connected, message)
    serial_frame_sent = Signal(int)  # frames_sent count
    serial_auth_status_changed = Signal(str)
    serial_auth_lic_info_changed = Signal(object)
    serial_connection_busy_changed = Signal(bool)
    _device_connect_requested = Signal(str, int, bytes)
    _device_disconnect_requested = Signal()
    _device_frame_requested = Signal(int, object)
    _device_tracking_reset_requested = Signal()

    def __init__(self):
        super().__init__()
        self.data_manager = DataManager()
        self.source_data_manager = DataManager()
        self.undo_manager = UndoManager()
        self.clipboard_manager = ClipboardManager()
        self.audio_manager = AudioManager()
        self.current_file_path = None
        self.current_source_file_path = None
        self.current_source_video_path = None
        self.current_edit_video_path = None
        self.source_audio_duration_ms = None
        self.edit_audio_duration_ms = None
        self.audio_channel_modes = {'source': 'mono', 'edit': 'mono'}

        # Device managers
        self.serial_device = SerialDeviceManager()
        self.serial_auth_lic = ""
        self.global_brightness_enabled = False
        self.global_brightness_percent = GLOBAL_BRIGHTNESS_DEFAULT

        # Device output worker thread
        self.device_thread = QThread()
        self.device_worker = DeviceOutputWorker(
            self.serial_device,
            self.data_manager,
            self.build_serial_packet
        )
        self.device_worker.moveToThread(self.device_thread)
        self._device_connect_requested.connect(self.device_worker.connect_to_device)
        self._device_disconnect_requested.connect(self.device_worker.disconnect_device)
        self._device_frame_requested.connect(self.device_worker.send_to_devices)
        self._device_tracking_reset_requested.connect(self.device_worker.reset_tracking)
        self.device_worker.auth_status_changed.connect(self.serial_auth_status_changed.emit)
        self.device_worker.operation_finished.connect(self._on_device_operation_finished)
        self.device_thread.start()

        # Connect audio manager signals
        self.audio_manager.audio_processed.connect(self._on_audio_processed)
        self.audio_manager.processing_failed.connect(self._on_audio_failed)
        self.audio_manager.audio_progress.connect(self._on_audio_progress)

        # Connect device manager signals
        self.serial_device.connection_changed.connect(self.serial_connection_changed.emit)
        self.serial_device.frame_sent.connect(self.serial_frame_sent.emit)

    @Slot()
    def _on_device_operation_finished(self):
        self.serial_connection_busy_changed.emit(False)

    def _execute_command(self, command, success_message_key=None, failure_message_key=None):
        try:
            self.undo_manager.execute(command)
            self.timeline_data_changed.emit(self.data_manager.get_full_data())
            if success_message_key:
                self.status_message_changed.emit(tr(success_message_key))
            else:
                self.status_message_changed.emit(tr("status.command_succeeded_generic"))
        except Exception as e:
            if failure_message_key:
                self.status_message_changed.emit(tr(failure_message_key, error=e))
            else:
                self.status_message_changed.emit(tr("status.command_failed_generic", error=e))
        finally:
            self.undo_stack_changed.emit(len(self.undo_manager.undo_stack) > 0)
            self.redo_stack_changed.emit(len(self.undo_manager.redo_stack) > 0)

    def _timeline_display_name(self, timeline_type: str) -> str:
        key = "timeline.source" if timeline_type == "source" else "timeline.edit"
        return tr(key)

    @Slot(str)
    def open_file(self, file_path):
        if self.data_manager.load_csv(file_path):
            self.current_file_path = file_path
            self.timeline_data_changed.emit(self.data_manager.get_full_data())
            self.status_message_changed.emit(tr("status.opened_file", path=file_path))
            self.undo_manager.undo_stack.clear()
            self.undo_manager.redo_stack.clear()
            self.undo_stack_changed.emit(False)
            self.redo_stack_changed.emit(False)
            return True
        else:
            self.status_message_changed.emit(tr("status.open_failed", path=file_path))
            return False

    @Slot(str)
    def open_source_file(self, file_path):
        if self.source_data_manager.load_csv(file_path):
            self.current_source_file_path = file_path
            self.source_data_changed.emit(self.source_data_manager.get_full_data())
            self.status_message_changed.emit(tr("status.opened_source_file", path=file_path))
            return True
        else:
            self.status_message_changed.emit(tr("status.open_source_failed", path=file_path))
            return False

    @Slot(str)
    def save_file(self, file_path=None):
        path_to_save = file_path or self.current_file_path
        if not path_to_save:
            # This should be handled by MainWindow triggering a "Save As" dialog
            self.status_message_changed.emit(tr("status.no_file_path"))
            return

        if self.data_manager.save_csv(path_to_save):
            self.current_file_path = path_to_save
            self.status_message_changed.emit(tr("status.file_saved", path=path_to_save))
        else:
            self.status_message_changed.emit(tr("status.file_save_failed", path=path_to_save))

    @Slot(float, float, str)
    def copy_selection(self, start_ms, end_ms, source='edit'):
        """Unified copy method that can copy from source or edit timeline"""
        if start_ms >= end_ms: 
            return
            
        try:
            if source == 'source':
                segment = self.source_data_manager.get_segment(start_ms, end_ms)
                manager = self.source_data_manager
            else:
                segment = self.data_manager.get_segment(start_ms, end_ms)
                manager = self.data_manager
                
            if segment.empty:
                self.status_message_changed.emit(
                    tr("status.no_data_to_copy", source=self._timeline_display_name(source))
                )
                return
                
            self.clipboard_manager.set_clipboard(segment, source)
            self.clipboard_changed.emit(True, source)
            self.status_message_changed.emit(
                tr("status.copied_frames", count=len(segment), source=self._timeline_display_name(source))
            )
            
            # Only add to undo stack for edit timeline copy
            if source == 'edit':
                command = CopyCommand(manager, self.clipboard_manager, start_ms, end_ms)
                self.undo_manager.execute(command)
                self.undo_stack_changed.emit(True)
                
        except Exception as e:
            self.status_message_changed.emit(tr("status.copy_failed", error=str(e)))

    @Slot(float, float)
    def cut_selection(self, start_ms, end_ms):
        if start_ms >= end_ms: return
        command = CutCommand(self.data_manager, self.clipboard_manager, start_ms, end_ms)
        self._execute_command(command)
        self.clipboard_changed.emit(self.clipboard_manager.has_data(), 'edit')

    @Slot(float)
    def paste_selection(self, at_ms):
        command = PasteCommand(self.data_manager, self.clipboard_manager, at_ms)
        self._execute_command(command)

    @Slot(float, float)
    def delete_selection(self, start_ms, end_ms):
        if start_ms >= end_ms: return
        command = DeleteCommand(self.data_manager, start_ms, end_ms)
        self._execute_command(command)

    @Slot(float, float, int)
    def set_function_in_region(self, start_ms, end_ms, function):
        command = SetFunctionInRegionCommand(
            self.data_manager,
            start_ms,
            end_ms,
            function,
        )
        try:
            self.undo_manager.execute(command)
            self.timeline_data_changed.emit(self.data_manager.get_full_data())
            function_name = tr(f"function.mode_{command.function}")
            self.status_message_changed.emit(
                tr(
                    "status.function_region_updated",
                    count=command.affected_count,
                    function=function_name,
                )
            )
        except Exception as exc:
            self.status_message_changed.emit(
                tr("status.function_region_failed", error=exc)
            )
        finally:
            self.undo_stack_changed.emit(len(self.undo_manager.undo_stack) > 0)
            self.redo_stack_changed.emit(len(self.undo_manager.redo_stack) > 0)

    @Slot(float, float, int)
    def adjust_brightness_in_region(self, start_ms, end_ms, percent):
        if int(percent) == 100:
            self.status_message_changed.emit(tr("status.brightness_region_unchanged"))
            return

        command = AdjustBrightnessInRegionCommand(
            self.data_manager,
            start_ms,
            end_ms,
            percent,
        )
        try:
            self.undo_manager.execute(command)
            self.timeline_data_changed.emit(self.data_manager.get_full_data())
            self.status_message_changed.emit(
                tr(
                    "status.brightness_region_updated",
                    count=command.affected_count,
                    percent=command.percent,
                )
            )
        except Exception as exc:
            self.status_message_changed.emit(
                tr("status.brightness_region_failed", error=exc)
            )
        finally:
            self.undo_stack_changed.emit(len(self.undo_manager.undo_stack) > 0)
            self.redo_stack_changed.emit(len(self.undo_manager.redo_stack) > 0)

    @Slot(float, float, dict)
    def set_color_in_region(self, start_ms, end_ms, color):
        command = SetColorInRegionCommand(
            self.data_manager,
            start_ms,
            end_ms,
            color,
        )
        try:
            self.undo_manager.execute(command)
            self.timeline_data_changed.emit(self.data_manager.get_full_data())
            self.status_message_changed.emit(
                tr(
                    "status.color_region_updated",
                    count=command.affected_count,
                    r=command.color['r'],
                    g=command.color['g'],
                    b=command.color['b'],
                )
            )
        except Exception as exc:
            self.status_message_changed.emit(
                tr("status.color_region_failed", error=exc)
            )
        finally:
            self.undo_stack_changed.emit(len(self.undo_manager.undo_stack) > 0)
            self.redo_stack_changed.emit(len(self.undo_manager.redo_stack) > 0)

    @Slot()
    def undo(self):
        try:
            self.undo_manager.undo()
            self.timeline_data_changed.emit(self.data_manager.get_full_data())
            self.status_message_changed.emit(tr("status.undo_success"))
        except Exception as e:
            self.status_message_changed.emit(tr("status.undo_failed", error=e))
        finally:
            self.undo_stack_changed.emit(len(self.undo_manager.undo_stack) > 0)
            self.redo_stack_changed.emit(len(self.undo_manager.redo_stack) > 0)

    @Slot()
    def redo(self):
        try:
            self.undo_manager.redo()
            self.timeline_data_changed.emit(self.data_manager.get_full_data())
            self.status_message_changed.emit(tr("status.redo_success"))
        except Exception as e:
            self.status_message_changed.emit(tr("status.redo_failed", error=e))
        finally:
            self.undo_stack_changed.emit(len(self.undo_manager.undo_stack) > 0)
            self.redo_stack_changed.emit(len(self.undo_manager.redo_stack) > 0)

    @Slot(float, str)
    def add_marker(self, at_ms, name):
        command = AddMarkerCommand(self.data_manager, at_ms, name)
        self._execute_command(command)

    @Slot(float, str)
    def update_marker(self, at_ms, name):
        command = UpdateMarkerCommand(self.data_manager, at_ms, name)
        self._execute_command(command)

    @Slot(float)
    def insert_blackout_frame(self, at_ms):
        command = InsertFrameCommand(self.data_manager, at_ms, 'blackout')
        self._execute_command(command)

    @Slot(float, dict, int, str)
    def insert_color_frame(self, at_ms, color, function, marker=""):
        command = InsertFrameCommand(self.data_manager, at_ms, 'color', color=color, function=function, marker=marker)
        self._execute_command(command)

    @Slot(float, dict, int, str)
    def update_frame(self, frame_time_ms, color, function, marker=None):
        """
        Per PRD 5.1: Update an existing frame's color and function values.
        Used by the 'E' shortcut to edit frames without delete/recreate.
        """
        command = UpdateFrameCommand(self.data_manager, frame_time_ms, color, function, marker)
        self._execute_command(command)

    @Slot(dict)
    def generate_breathing_effect(self, params):
        duration_ms = params.get('duration', 5000.0)
        interval_ms = params.get('interval', 100.0)
        color = params.get('color', {'r': 15, 'g': 15, 'b': 15})
        min_bright = params.get('min_bright', 0.1)
        max_bright = params.get('max_bright', 1.0)
        at_ms = params.get('at_ms', self.data_manager.get_timeline_stats()['end_time_ms'])  # Use playback head time or end of timeline
        
        effect_df = EffectGenerator.create_breathing_df(
            duration_ms, interval_ms, color, min_bright, max_bright, 
            self.data_manager.main_df.columns
        )
        command = InsertEffectCommand(
            self.data_manager, 
            at_ms, 
            effect_df, 
            "Breathing Effect"
        )
        self._execute_command(command)

    @Slot(dict)
    def generate_rainbow_effect(self, params):
        duration_ms = params.get('duration', 10000.0)
        interval_ms = params.get('interval', 100.0)
        speed = params.get('speed', 0.1)
        at_ms = params.get('at_ms', self.data_manager.get_timeline_stats()['end_time_ms'])  # Use playback head time or end of timeline

        effect_df = EffectGenerator.create_rainbow_df(
            duration_ms, interval_ms, speed,
            self.data_manager.main_df.columns
        )
        command = InsertEffectCommand(
            self.data_manager,
            at_ms,
            effect_df,
            "Rainbow Effect"
        )
        self._execute_command(command)

    @Slot(dict)
    def generate_gradient_effect(self, params):
        control_points = params.get('control_points', [])
        mode = params.get('mode', 0)  # 0=RGB, 1=HSV CW, 2=HSV CCW
        interval_ms = params.get('interval', 100.0)
        duration_ms = params.get('duration', 5000.0)
        at_ms = params.get('at_ms', self.data_manager.get_timeline_stats()['end_time_ms'])

        effect_df = EffectGenerator.create_gradient_df(
            duration_ms, interval_ms, control_points, mode,
            self.data_manager.main_df.columns
        )
        command = InsertEffectCommand(
            self.data_manager,
            at_ms,
            effect_df,
            "Gradient Effect"
        )
        self._execute_command(command)

    @Slot(dict)
    def generate_intermediate_frames(self, params):
        start_ms = params.get('start_ms', 0.0)
        end_ms = params.get('end_ms', 0.0)
        interval_ms = params.get('interval', 200.0)

        anchor_df = self.data_manager.get_segment(start_ms, end_ms)
        if len(anchor_df) < 2:
            self.status_message_changed.emit(tr("status.generate_intermediate_requires_two_frames"))
            return

        effect_df = EffectGenerator.create_intermediate_fill_df(
            anchor_df,
            interval_ms,
            self.data_manager.main_df.columns,
        )
        command = InsertEffectCommand(
            self.data_manager,
            float(anchor_df['frame_time_ms'].min()),
            effect_df,
            "Intermediate Frames",
        )
        self._execute_command(
            command,
            success_message_key="status.generate_intermediate_success",
            failure_message_key="status.generate_intermediate_failed",
        )

    @Slot(float)
    def new_edit(self, duration_sec):
        """Create a new edit project with the specified duration."""
        try:
            # Create a new data manager for the edit timeline
            self.data_manager = DataManager()
            self.current_file_path = None
            duration_ms = duration_sec * 1000
            
            # Get columns from source data manager or use default columns
            if not self.source_data_manager.main_df.empty:
                columns = list(self.source_data_manager.main_df.columns)
            else:
                # Default columns if no source data is available
                columns = ['frame_time_ms', 'frame_id', 'frame_type', 'marker']
                for i in range(10):
                    columns.extend([f'ch{i}_function', f'ch{i}_red', f'ch{i}_green', f'ch{i}_blue'])
            
            # Create start and end markers
            start_marker = {col: 0 for col in columns}
            start_marker.update({'frame_time_ms': 0, 'marker': 'Start'})
            
            end_marker = {col: 0 for col in columns}
            end_marker.update({'frame_time_ms': duration_ms, 'marker': 'End'})
            
            # Create a DataFrame with the start and end markers
            self.data_manager.main_df = pd.DataFrame([start_marker, end_marker])
            
            # Emit signal to update the UI
            self.timeline_data_changed.emit(self.data_manager.get_full_data())
            
            # Clear undo/redo stacks for the new project
            self.undo_manager.undo_stack.clear()
            self.undo_manager.redo_stack.clear()
            self.undo_stack_changed.emit(False)
            self.redo_stack_changed.emit(False)
            
            self.status_message_changed.emit(tr("status.new_edit_created", duration_sec=duration_sec))
        except Exception as e:
            self.status_message_changed.emit(tr("status.new_edit_failed", error=str(e)))

    @Slot(float, float, float)
    def offset_selection(self, start_ms, end_ms, offset_ms):
        """Offset a selection by the specified amount."""
        try:
            command = OffsetCommand(self.data_manager, start_ms, end_ms, offset_ms)
            self._execute_command(command)
            
            # 计算新的选区位置并发送信号
            new_start = start_ms + offset_ms
            new_end = end_ms + offset_ms
            self.offset_applied.emit(new_start, new_end)
            
            # 发送信号通知UI更新数据
            self.timeline_data_changed.emit(self.data_manager.get_full_data())
        except Exception as e:
            self.status_message_changed.emit(tr("status.offset_failed", error=str(e)))

    # --- Audio Methods ---
    @Slot(str, str)
    def load_video_audio(self, video_path: str, timeline_type: str):
        """Extract and process audio from a reference media file."""
        if timeline_type == 'source':
            self.current_source_video_path = video_path
            self.source_audio_duration_ms = None
        else:
            self.current_edit_video_path = video_path
            self.edit_audio_duration_ms = None

        self.audio_channel_modes[timeline_type] = 'mono'
        self.audio_manager.extract_audio(video_path, 'mono')
        self.status_message_changed.emit(
            tr("status.processing_audio_from_video", timeline=self._timeline_display_name(timeline_type))
        )

    @Slot(str, str, str)
    def change_audio_channel_mode(self, timeline_type: str, video_path: str, mode: str):
        """Re-process audio with different channel mode"""
        self.audio_channel_modes[timeline_type] = mode
        self.audio_manager.extract_audio(video_path, mode)
        self.status_message_changed.emit(tr("status.reprocessing_audio_mode", mode=mode))

    @Slot(str, object)
    def _on_audio_processed(self, video_path: str, audio_data):
        """Route processed audio to correct timeline"""
        if (video_path == self.current_source_video_path
                and audio_data.channel_mode == self.audio_channel_modes['source']):
            self.source_audio_processed.emit(audio_data)
            self.source_audio_duration_ms = audio_data.duration_ms
            duration_sec = audio_data.duration_ms / 1000.0
            self.status_message_changed.emit(
                tr("status.source_audio_loaded", sample_rate=audio_data.sample_rate, duration=duration_sec)
            )
        if (video_path == self.current_edit_video_path
                and audio_data.channel_mode == self.audio_channel_modes['edit']):
            self.edit_audio_processed.emit(audio_data)
            self.edit_audio_duration_ms = audio_data.duration_ms
            duration_sec = audio_data.duration_ms / 1000.0
            self.status_message_changed.emit(
                tr("status.edit_audio_loaded", sample_rate=audio_data.sample_rate, duration=duration_sec)
            )

    @Slot(str, str)
    def _on_audio_failed(self, video_path: str, error: str):
        """Handle audio processing errors"""
        matched = False
        for timeline_type, current_path in (
            ('source', self.current_source_video_path),
            ('edit', self.current_edit_video_path),
        ):
            if video_path == current_path:
                self.audio_processing_failed.emit(timeline_type, error)
                matched = True
        if matched:
            self.status_message_changed.emit(tr("status.audio_processing_failed", error=error))

    @Slot(str, str, int)
    def _on_audio_progress(self, video_path: str, stage: str, percentage: int):
        """Route audio processing progress to correct timeline"""
        matched = False
        for timeline_type, current_path in (
            ('source', self.current_source_video_path),
            ('edit', self.current_edit_video_path),
        ):
            if video_path == current_path:
                self.audio_progress.emit(timeline_type, stage, percentage)
                matched = True
        if matched:
            self.status_message_changed.emit(
                tr("status.audio_processing_progress", stage=stage, percentage=percentage)
            )

    # --- Device Output Methods ---

    def get_serial_ports(self):
        """Get list of available serial ports."""
        return self.serial_device.get_ports()

    def get_ble_devices(self):
        """Get list of discoverable LumaFlow BLE transmitters."""
        return self.serial_device.scan_ble_devices()

    def get_last_ble_scan_count(self):
        """Get the raw number of BLE advertisements from the last scan."""
        return self.serial_device.last_ble_scan_count

    def get_udp_stream_repeats(self):
        """Get UDP STREAM repeat count."""
        return self.serial_device.get_udp_stream_repeats()

    @Slot(str, int)
    def connect_serial(self, port, baud_rate):
        """Queue a serial, UDP, or BLE connection and AUTH operation."""
        try:
            auth_frame = self.build_auth_packet()
        except ValueError as exc:
            self.serial_auth_status_changed.emit("Config Error")
            self.serial_connection_changed.emit(False, f"Connection failed: {exc}")
            return

        self.serial_auth_status_changed.emit("Not Sent")
        self.serial_connection_busy_changed.emit(True)
        self._device_connect_requested.emit(port, baud_rate, auth_frame)

    @Slot()
    def disconnect_serial(self):
        """Queue a non-blocking device disconnect."""
        self.serial_connection_busy_changed.emit(True)
        self._device_disconnect_requested.emit()

    @Slot(int)
    def set_serial_offset(self, offset_ms):
        """Set serial device timing offset."""
        self.serial_device.set_offset(offset_ms)

    @Slot(int)
    def set_udp_stream_repeats(self, repeats):
        """Set UDP STREAM repeat count."""
        self.serial_device.set_udp_stream_repeats(repeats)

    @Slot(bool, int)
    def set_global_brightness(self, enabled, percent):
        """Configure non-destructive brightness modulation for device output."""
        percent = max(GLOBAL_BRIGHTNESS_MIN, min(GLOBAL_BRIGHTNESS_MAX, int(percent)))
        self.global_brightness_enabled = bool(enabled)
        self.global_brightness_percent = percent
        self._device_tracking_reset_requested.emit()

    @Slot(str)
    def set_serial_auth_lic(self, lic_text):
        """Set the AUTH LIC string used to build AUTH packets."""
        self.serial_auth_lic = lic_text.strip()
        self.serial_auth_lic_info_changed.emit(describe_auth_lic(self.serial_auth_lic))
        self.serial_auth_status_changed.emit("Not Sent")

    @Slot(float, float, float)
    def update_calibration(self, r, g, b):
        """Update color calibration and refresh timeline."""
        color_calibration.set_gains(r, g, b)
        # Force refresh timeline display by re-emitting data
        # This triggers RenderWorker which now uses the new LUTs
        self.timeline_data_changed.emit(self.data_manager.get_full_data())
        if not self.source_data_manager.main_df.empty:
            self.source_data_changed.emit(self.source_data_manager.get_full_data())
        self.status_message_changed.emit(tr("status.calibration_updated", r=r, g=g, b=b))

    def get_current_calibration(self):
        return color_calibration.get_gains()

    def build_serial_packet(self, frame):
        """Build a STREAM (0xD8) TLV frame from timeline data."""
        brightness_percent = (
            self.global_brightness_percent
            if self.global_brightness_enabled
            else GLOBAL_BRIGHTNESS_DEFAULT
        )
        return build_stream_frame(frame, brightness_percent)

    def build_auth_packet(self, host_time=None):
        """Build an AUTH (0xE0) TLV frame from the current LIC string."""
        auth_host_time = int(time.time()) if host_time is None else int(host_time)
        return build_auth_frame(self.serial_auth_lic, auth_host_time)

    def get_serial_auth_lic_info(self):
        """Get parsed information for the current AUTH LIC string."""
        return describe_auth_lic(self.serial_auth_lic)

    @Slot(int, str)
    def on_playback_position_changed(self, position_ms, timeline_type='edit'):
        """Called when video playback position changes. Sends frames to connected devices."""
        # Delegate to worker thread for non-blocking device output
        if timeline_type == 'source':
            self._device_frame_requested.emit(position_ms, self.source_data_manager)
        else:
            self._device_frame_requested.emit(position_ms, self.data_manager)

    def reset_device_tracking(self):
        """Reset frame tracking for new playback session."""
        self._device_tracking_reset_requested.emit()

    def shutdown(self):
        """Cleanup threads properly"""
        try:
            # Stop audio manager threads
            if hasattr(self, 'audio_manager'):
                self.audio_manager.shutdown()

            # Stop device output worker thread
            if hasattr(self, 'device_thread') and self.device_thread.isRunning():
                self.device_thread.quit()
                if not self.device_thread.wait(3000):
                    self.device_thread.terminate()
                    self.device_thread.wait()

            if hasattr(self, 'serial_device'):
                self.serial_device.disconnect(emit_signal=False)
        except RuntimeError:
            pass  # Qt objects already deleted
