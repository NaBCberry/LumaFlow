from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QComboBox, QLabel, QSpinBox, QLineEdit, QCheckBox, QSlider
)
from PySide6.QtCore import Signal, Qt
from core.serial_device_manager import (
    UDP_DEFAULT_PORT,
    UDP_STREAM_REPEATS,
    UDP_STREAM_REPEATS_MAX,
    UDP_STREAM_REPEATS_MIN,
    normalize_udp_host,
)
from core.i18n import tr
from core.serial_protocol import (
    GLOBAL_BRIGHTNESS_DEFAULT,
    GLOBAL_BRIGHTNESS_MAX,
    GLOBAL_BRIGHTNESS_MIN,
)


class SerialDevicePanel(QGroupBox):
    """Panel for Serial RF Transmitter controls."""
    connect_requested = Signal(str, int)  # port, baud_rate
    disconnect_requested = Signal()
    offset_changed = Signal(int)
    refresh_requested = Signal()
    auth_lic_changed = Signal(str)
    udp_host_changed = Signal(str)
    udp_stream_repeats_changed = Signal(int)
    ble_scan_requested = Signal()
    ble_device_changed = Signal(str)
    global_brightness_changed = Signal(bool, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self._default_offset = 200

        # Port selection row
        port_row = QHBoxLayout()
        self.port_label = QLabel()
        port_row.addWidget(self.port_label)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(100)
        port_row.addWidget(self.port_combo)
        self.refresh_btn = QPushButton()
        port_row.addWidget(self.refresh_btn)
        port_row.addStretch()
        layout.addLayout(port_row)

        # Baud rate row
        baud_row = QHBoxLayout()
        self.baud_label = QLabel()
        baud_row.addWidget(self.baud_label)
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["115200", "230400", "512000", "460800", "921600"])
        self.baud_combo.setCurrentText("512000")
        baud_row.addWidget(self.baud_combo)
        baud_row.addStretch()
        layout.addLayout(baud_row)

        # Transport mode row
        transport_row = QHBoxLayout()
        self.transport_label = QLabel()
        transport_row.addWidget(self.transport_label)
        self.transport_combo = QComboBox()
        self.transport_combo.addItems(["Serial", "UDP", "BLE"])
        self.transport_combo.setCurrentText("Serial")
        transport_row.addWidget(self.transport_combo)
        transport_row.addStretch()
        layout.addLayout(transport_row)

        # UDP target row (hidden when serial mode)
        self.udp_row = QHBoxLayout()
        self.udp_ip_label = QLabel()
        self.udp_row.addWidget(self.udp_ip_label)
        self.udp_ip_edit = QLineEdit()
        self.udp_ip_edit.setPlaceholderText("192.168.19.123")
        self.udp_ip_edit.setMinimumWidth(132)
        self.udp_ip_edit.setClearButtonEnabled(True)
        self.udp_row.addWidget(self.udp_ip_edit)
        self.udp_port_label = QLabel()
        self.udp_row.addWidget(self.udp_port_label)
        self.udp_port_edit = QLineEdit(str(UDP_DEFAULT_PORT))
        self.udp_port_edit.setReadOnly(True)
        self.udp_port_edit.setAlignment(Qt.AlignCenter)
        self.udp_port_edit.setFixedWidth(72)
        self.udp_row.addWidget(self.udp_port_edit)
        self.udp_row.addStretch()
        layout.addLayout(self.udp_row)

        # UDP reliability row (hidden when not using UDP)
        self.udp_reliability_row = QHBoxLayout()
        self.udp_stream_repeats_label = QLabel()
        self.udp_reliability_row.addWidget(self.udp_stream_repeats_label)
        self.udp_stream_repeats_spin = QSpinBox()
        self.udp_stream_repeats_spin.setRange(UDP_STREAM_REPEATS_MIN, UDP_STREAM_REPEATS_MAX)
        self.udp_stream_repeats_spin.setValue(UDP_STREAM_REPEATS)
        self.udp_stream_repeats_spin.setFixedWidth(72)
        self.udp_stream_repeats_spin.setSuffix("x")
        self.udp_reliability_row.addWidget(self.udp_stream_repeats_spin)
        self.udp_reliability_row.addStretch()
        layout.addLayout(self.udp_reliability_row)

        # BLE target row (hidden when not using BLE)
        self.ble_row = QHBoxLayout()
        self.ble_device_label = QLabel()
        self.ble_row.addWidget(self.ble_device_label)
        self.ble_device_combo = QComboBox()
        self.ble_device_combo.setMinimumWidth(180)
        self.ble_row.addWidget(self.ble_device_combo)
        self.ble_scan_btn = QPushButton()
        self.ble_row.addWidget(self.ble_scan_btn)
        self.ble_row.addStretch()
        layout.addLayout(self.ble_row)

        # Connect button and status
        connect_row = QHBoxLayout()
        self.connect_btn = QPushButton()
        connect_row.addWidget(self.connect_btn)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        connect_row.addWidget(self.status_label)
        connect_row.addStretch()
        layout.addLayout(connect_row)

        # Offset control
        offset_row = QHBoxLayout()
        self.offset_label = QLabel()
        offset_row.addWidget(self.offset_label)
        self.offset_spin = QSpinBox()
        self.offset_spin.setRange(-1000, 1000)
        self.offset_spin.setValue(self._default_offset)
        self.offset_spin.setMinimumWidth(80)
        offset_row.addWidget(self.offset_spin)
        self.offset_minus_50_btn = QPushButton("-50")
        offset_row.addWidget(self.offset_minus_50_btn)
        self.offset_minus_10_btn = QPushButton("-10")
        offset_row.addWidget(self.offset_minus_10_btn)
        self.offset_plus_10_btn = QPushButton("+10")
        offset_row.addWidget(self.offset_plus_10_btn)
        self.offset_plus_50_btn = QPushButton("+50")
        offset_row.addWidget(self.offset_plus_50_btn)
        self.reset_offset_btn = QPushButton()
        offset_row.addWidget(self.reset_offset_btn)
        offset_row.addStretch()
        layout.addLayout(offset_row)

        # Non-destructive brightness modulation applied only to outgoing STREAM frames.
        brightness_row = QHBoxLayout()
        self.global_brightness_checkbox = QCheckBox()
        brightness_row.addWidget(self.global_brightness_checkbox)
        self.global_brightness_slider = QSlider(Qt.Horizontal)
        self.global_brightness_slider.setRange(GLOBAL_BRIGHTNESS_MIN, GLOBAL_BRIGHTNESS_MAX)
        self.global_brightness_slider.setValue(GLOBAL_BRIGHTNESS_DEFAULT)
        self.global_brightness_slider.setMinimumWidth(120)
        brightness_row.addWidget(self.global_brightness_slider, 1)
        self.global_brightness_spin = QSpinBox()
        self.global_brightness_spin.setRange(GLOBAL_BRIGHTNESS_MIN, GLOBAL_BRIGHTNESS_MAX)
        self.global_brightness_spin.setValue(GLOBAL_BRIGHTNESS_DEFAULT)
        self.global_brightness_spin.setSuffix("%")
        self.global_brightness_spin.setFixedWidth(72)
        brightness_row.addWidget(self.global_brightness_spin)
        layout.addLayout(brightness_row)

        auth_row = QHBoxLayout()
        self.auth_lic_label = QLabel()
        auth_row.addWidget(self.auth_lic_label)
        self.auth_lic_edit = QLineEdit()
        self.auth_lic_edit.setClearButtonEnabled(True)
        auth_row.addWidget(self.auth_lic_edit)
        layout.addLayout(auth_row)

        auth_status_row = QHBoxLayout()
        self.auth_status_title_label = QLabel()
        auth_status_row.addWidget(self.auth_status_title_label)
        self.auth_status_label = QLabel()
        auth_status_row.addWidget(self.auth_status_label)
        auth_status_row.addStretch()
        layout.addLayout(auth_status_row)

        self.lic_info_box = QGroupBox()
        lic_info_box = self.lic_info_box
        lic_info_layout = QVBoxLayout(lic_info_box)

        self.lic_device_label = QLabel()
        lic_info_layout.addWidget(self.lic_device_label)
        self.lic_expire_label = QLabel()
        lic_info_layout.addWidget(self.lic_expire_label)
        self.lic_validity_label = QLabel()
        lic_info_layout.addWidget(self.lic_validity_label)
        self.lic_signature_label = QLabel()
        lic_info_layout.addWidget(self.lic_signature_label)
        self.lic_parse_status_label = QLabel()
        self.lic_parse_status_label.setWordWrap(True)
        lic_info_layout.addWidget(self.lic_parse_status_label)
        layout.addWidget(lic_info_box)

        # Frames sent counter
        self.frames_label = QLabel()
        layout.addWidget(self.frames_label)

        # Connect signals
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        self.transport_combo.currentTextChanged.connect(self._on_transport_changed)
        self.offset_spin.valueChanged.connect(self.offset_changed.emit)
        self.offset_minus_50_btn.clicked.connect(lambda: self._adjust_offset(-50))
        self.offset_minus_10_btn.clicked.connect(lambda: self._adjust_offset(-10))
        self.offset_plus_10_btn.clicked.connect(lambda: self._adjust_offset(10))
        self.offset_plus_50_btn.clicked.connect(lambda: self._adjust_offset(50))
        self.reset_offset_btn.clicked.connect(lambda: self.offset_spin.setValue(self._default_offset))
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        self.ble_scan_btn.clicked.connect(self.ble_scan_requested.emit)
        self.ble_device_combo.currentIndexChanged.connect(self._on_ble_device_index_changed)
        self.auth_lic_edit.textChanged.connect(self.auth_lic_changed.emit)
        self.udp_ip_edit.textChanged.connect(self.udp_host_changed.emit)
        self.udp_ip_edit.editingFinished.connect(self._normalize_udp_ip_field)
        self.udp_stream_repeats_spin.valueChanged.connect(self.udp_stream_repeats_changed.emit)
        self.global_brightness_checkbox.toggled.connect(self._on_global_brightness_changed)
        self.global_brightness_slider.valueChanged.connect(self.global_brightness_spin.setValue)
        self.global_brightness_spin.valueChanged.connect(self.global_brightness_slider.setValue)
        self.global_brightness_spin.valueChanged.connect(self._on_global_brightness_changed)
        self._update_global_brightness_controls(False)
        self._on_transport_changed("Serial")
        self.apply_translations()

    def set_default_offset(self, value: int):
        self._default_offset = int(value)

    def _adjust_offset(self, delta: int):
        self.offset_spin.setValue(self.offset_spin.value() + int(delta))

    def _on_connect_clicked(self):
        if self.connect_btn.text() == tr("device_output.connect"):
            if self.transport_combo.currentText() == "UDP":
                target = self._normalize_udp_ip_field()
                if target is None:
                    self.status_label.setText(tr("device_output.invalid_udp_ip"))
                    return
                self.connect_requested.emit(target, -1)  # negative baud = UDP mode
            elif self.transport_combo.currentText() == "BLE":
                target = self.ble_device_combo.currentData()
                if not target:
                    self.status_label.setText(tr("device_output.no_ble_device"))
                    return
                self.connect_requested.emit(target, -2)  # -2 = BLE mode
            else:
                port = self.port_combo.currentData()
                baud = int(self.baud_combo.currentText())
                self.connect_requested.emit(port, baud)
        else:
            self.disconnect_requested.emit()

    def _on_transport_changed(self, mode):
        is_serial = (mode == "Serial")
        is_udp = (mode == "UDP")
        is_ble = (mode == "BLE")
        self.port_combo.setVisible(is_serial)
        self.port_label.setVisible(is_serial)
        self.refresh_btn.setVisible(is_serial)
        self.baud_combo.setVisible(is_serial)
        self.baud_label.setVisible(is_serial)
        self.udp_ip_edit.setVisible(is_udp)
        self.udp_ip_label.setVisible(is_udp)
        self.udp_port_edit.setVisible(is_udp)
        self.udp_port_label.setVisible(is_udp)
        self.udp_stream_repeats_label.setVisible(is_udp)
        self.udp_stream_repeats_spin.setVisible(is_udp)
        self.ble_device_combo.setVisible(is_ble)
        self.ble_device_label.setVisible(is_ble)
        self.ble_scan_btn.setVisible(is_ble)

    def _normalize_udp_ip_field(self):
        raw_host = self.udp_ip_edit.text().strip()
        try:
            host = normalize_udp_host(raw_host)
        except ValueError:
            return None
        if host != raw_host:
            self.udp_ip_edit.setText(host)
        return host

    def set_udp_host(self, value):
        self.udp_ip_edit.setText(str(value or "").strip())

    def get_udp_host(self):
        return self.udp_ip_edit.text().strip()

    def set_udp_stream_repeats(self, value):
        self.udp_stream_repeats_spin.setValue(int(value))

    def get_udp_stream_repeats(self):
        return self.udp_stream_repeats_spin.value()

    def _on_global_brightness_changed(self, _value=None):
        enabled = self.global_brightness_checkbox.isChecked()
        self._update_global_brightness_controls(enabled)
        self.global_brightness_changed.emit(enabled, self.global_brightness_spin.value())

    def _update_global_brightness_controls(self, enabled):
        self.global_brightness_slider.setEnabled(bool(enabled))
        self.global_brightness_spin.setEnabled(bool(enabled))

    def set_global_brightness(self, enabled, percent):
        self.global_brightness_checkbox.setChecked(bool(enabled))
        value = int(percent)
        self.global_brightness_slider.setValue(value)
        self.global_brightness_spin.setValue(value)
        self._update_global_brightness_controls(enabled)

    def get_global_brightness(self):
        return self.global_brightness_checkbox.isChecked(), self.global_brightness_spin.value()

    def set_ble_device(self, address):
        address = str(address or "").strip()
        if not address:
            return
        index = self.ble_device_combo.findData(address)
        if index < 0:
            self.ble_device_combo.addItem(address, address)
            index = self.ble_device_combo.findData(address)
        self.ble_device_combo.setCurrentIndex(index)

    def get_ble_device(self):
        return self.ble_device_combo.currentData() or ""

    def update_ble_devices(self, devices, raw_count=None):
        """Update the list of discovered BLE devices."""
        self.begin_ble_scan()
        for device in devices:
            self.add_ble_device(device)
        self.finish_ble_scan(raw_count=raw_count)

    def begin_ble_scan(self):
        """Prepare the BLE list for a fresh scan."""
        self.ble_device_combo.blockSignals(True)
        self.ble_device_combo.clear()
        self.ble_device_combo.blockSignals(False)
        self.ble_scan_btn.setEnabled(False)
        self.status_label.setText(tr("device_output.ble_scanning"))

    def add_ble_device(self, device):
        """Add one discovered BLE device to the list."""
        address = device.get("address", "")
        if not address or self.ble_device_combo.findData(address) >= 0:
            return

        name = device.get("name") or "LumaFlow BLE"
        rssi = device.get("rssi")
        display_text = f"{name} - {address}"
        if rssi is not None:
            display_text = f"{display_text} ({rssi} dBm)"

        was_empty = self.ble_device_combo.count() == 0
        self.ble_device_combo.addItem(display_text, address)
        if was_empty:
            self.ble_device_combo.setCurrentIndex(0)
            self._on_ble_device_index_changed(0)

        self.status_label.setText(
            tr("device_output.ble_scan_done", count=self.ble_device_combo.count())
        )

    def finish_ble_scan(self, raw_count=None, error=None):
        """Finish a BLE scan and surface the final state."""
        self.ble_scan_btn.setEnabled(True)
        if error:
            self.status_label.setText(tr("device_output.ble_scan_failed", error=error))
        elif self.ble_device_combo.count() > 0:
            self.status_label.setText(
                tr("device_output.ble_scan_done", count=self.ble_device_combo.count())
            )
        elif raw_count:
            self.status_label.setText(tr("device_output.no_lumaflow_ble_device", count=raw_count))
        else:
            self.status_label.setText(tr("device_output.no_ble_device"))

    def _on_ble_device_index_changed(self, _index):
        address = self.ble_device_combo.currentData()
        if address:
            self.ble_device_changed.emit(address)

    def update_ports(self, ports):
        """Update the list of available ports."""
        current = self.port_combo.currentData()
        self.port_combo.clear()
        for port_info in ports:
            device = port_info['device']
            description = port_info['description']
            # Display format: "COM6 - Device Name"
            display_text = f"{device} - {description}"
            self.port_combo.addItem(display_text, device)
        if current:
            index = self.port_combo.findData(current)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)

    def set_connected(self, connected, message=None):
        """Update UI to reflect connection state."""
        self.set_connection_busy(False)
        self.connect_btn.setText(tr("device_output.disconnect") if connected else tr("device_output.connect"))
        if message and (connected or message != "Disconnected"):
            self.status_label.setText(message)
        else:
            self.status_label.setText(tr("device_output.connected") if connected else tr("device_output.disconnected"))

    def set_connection_busy(self, busy):
        self.connect_btn.setEnabled(not busy)
        self.transport_combo.setEnabled(not busy)
        if busy:
            self.status_label.setText(tr("device_output.connecting"))

    def update_frames_sent(self, count):
        """Update the frames sent counter."""
        self.frames_label.setText(tr("device_output.frames_sent", count=count))

    def set_auth_lic(self, value):
        self.auth_lic_edit.setText(value)

    def set_auth_status(self, status):
        status_key = {
            "Not Sent": "device_output.auth_not_sent",
            "Sent": "device_output.auth_sent",
            "Config Error": "device_output.auth_config_error",
            "Send Failed": "device_output.auth_send_failed",
        }.get(status)
        self.auth_status_label.setText(tr(status_key) if status_key else status)

    def set_lic_info(self, info):
        self.lic_device_label.setText(tr("device_output.lic_device", value=info.get("device_mac", "--")))
        self.lic_expire_label.setText(tr("device_output.lic_expire_at", value=info.get("expire_at", "--")))
        self.lic_validity_label.setText(tr("device_output.lic_validity", value=info.get("validity", "--")))
        self.lic_signature_label.setText(tr("device_output.lic_signature", value=info.get("signature", "--")))
        self.lic_parse_status_label.setText(
            tr("device_output.lic_status", value=info.get("status", tr("device_output.lic_status_empty")))
        )

        validity_color = "#ff4d4f" if info.get("is_expired") else "#d9d9d9"
        if info.get("valid") and not info.get("is_expired"):
            validity_color = "#52c41a"
        if not info.get("valid") and not info.get("empty"):
            validity_color = "#ff4d4f"

        status_color = "#d9d9d9"
        if info.get("valid"):
            status_color = "#52c41a"
        elif not info.get("empty"):
            status_color = "#ff4d4f"

        self.lic_validity_label.setStyleSheet(f"color: {validity_color};")
        self.lic_parse_status_label.setStyleSheet(f"color: {status_color};")

    def apply_translations(self):
        self.setTitle(tr("device_output.group_title"))
        self.port_label.setText(tr("device_output.port"))
        self.refresh_btn.setText(tr("device_output.refresh"))
        self.baud_label.setText(tr("device_output.baud"))
        self.transport_label.setText(tr("device_output.transport"))
        self.udp_ip_label.setText(tr("device_output.udp_ip"))
        self.udp_port_label.setText(tr("device_output.udp_port"))
        self.udp_stream_repeats_label.setText(tr("device_output.udp_stream_repeats"))
        self.ble_device_label.setText(tr("device_output.ble_device"))
        self.ble_scan_btn.setText(tr("device_output.ble_scan"))
        self.offset_label.setText(tr("device_output.offset"))
        self.global_brightness_checkbox.setText(tr("device_output.global_brightness"))
        self.reset_offset_btn.setText(tr("device_output.reset"))
        self.auth_lic_label.setText(tr("device_output.auth_lic"))
        self.auth_status_title_label.setText(tr("device_output.auth_status"))
        self.lic_info_box.setTitle(tr("device_output.lic_info"))
        self.set_connected(False)
        self.set_auth_status("Not Sent")
        self.update_frames_sent(0)
        self.set_lic_info({
            "device_mac": "--",
            "expire_at": "--",
            "validity": "--",
            "signature": "--",
            "status": tr("device_output.lic_status_empty"),
            "is_expired": False,
            "valid": False,
            "empty": True,
        })


class DeviceOutputWidget(QWidget):
    """Main widget containing the serial output panel."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.serial_panel = SerialDevicePanel()

        layout.addWidget(self.serial_panel)
        layout.addStretch()
