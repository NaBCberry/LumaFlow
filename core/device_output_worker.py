from PySide6.QtCore import QObject, Signal, Slot


class DeviceOutputWorker(QObject):
    """Worker thread for non-blocking device output."""

    auth_status_changed = Signal(str)
    operation_finished = Signal()

    def __init__(self, serial_device, data_manager, build_serial_packet_func):
        super().__init__()
        self.serial_device = serial_device
        self.data_manager = data_manager
        self.build_serial_packet = build_serial_packet_func

    @Slot(str, int, bytes)
    def connect_to_device(self, target, baud_rate, auth_frame):
        """Connect and authenticate without blocking the Qt UI thread."""
        try:
            if baud_rate == -1:
                result = self.serial_device.connect(target, transport="udp")
            elif baud_rate == -2:
                result = self.serial_device.connect(target, transport="ble")
            else:
                result = self.serial_device.connect(
                    target,
                    baud_rate,
                    transport="serial",
                )

            if not result:
                self.auth_status_changed.emit("Not Sent")
                return

            if not self.serial_device.send_data(auth_frame, count_frame=False):
                self.auth_status_changed.emit("Send Failed")
                if self.serial_device.is_connected():
                    self.serial_device.disconnect(
                        message="Connection failed: AUTH send failed",
                        emit_signal=True,
                    )
                return

            self.auth_status_changed.emit("Sent")
            if baud_rate == -1:
                endpoint = self.serial_device.get_udp_endpoint_label()
                self.serial_device.mark_connected(f"Connected to {endpoint} via UDP")
            elif baud_rate == -2:
                endpoint = self.serial_device.get_ble_endpoint_label()
                self.serial_device.mark_connected(f"Connected to {endpoint} via BLE")
            else:
                self.serial_device.mark_connected(
                    f"Connected to {target} @ {baud_rate}bps"
                )
        except Exception as exc:
            self.auth_status_changed.emit("Send Failed")
            self.serial_device.disconnect(
                message=f"Connection failed: {exc}",
                emit_signal=True,
            )
        finally:
            self.operation_finished.emit()

    @Slot()
    def disconnect_device(self):
        """Disconnect without blocking the Qt UI thread."""
        try:
            self.serial_device.disconnect()
            self.auth_status_changed.emit("Not Sent")
        finally:
            self.operation_finished.emit()

    @Slot()
    def reset_tracking(self):
        self.serial_device.reset_frame_tracking()

    @Slot(int, object)
    def send_to_devices(self, position_ms, data_manager=None):
        """Send frame data to devices (runs in worker thread)."""
        # Use provided data manager or fallback to the default one
        dm = data_manager if data_manager is not None else self.data_manager

        # Serial device
        if self.serial_device.is_connected():
            offset_time = position_ms + self.serial_device.offset_ms
            frame_index = dm.get_frame_index_at_ms(offset_time)
            if frame_index is not None and frame_index != self.serial_device.last_sent_frame_index:
                frame = dm.get_frame_at_ms(offset_time)
                if frame is not None:
                    packet = self.build_serial_packet(frame)
                    if self.serial_device.send_data(packet):
                        self.serial_device.last_sent_frame_index = frame_index
