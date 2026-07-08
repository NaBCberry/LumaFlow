import asyncio
import serial
import serial.tools.list_ports
import socket
import threading
import time
from concurrent.futures import TimeoutError as FutureTimeoutError
from ipaddress import AddressValueError, IPv4Address
from PySide6.QtCore import QObject, Signal

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    BleakClient = None
    BleakScanner = None

UDP_DEFAULT_PORT = 32712
TLV_HEAD = bytes((0xEB, 0x90))
TLV_TAIL = 0xED
TLV_CMD_OFFSET = 3
CMD_STREAM = 0xD8
CMD_AUTH = 0xE0
UDP_STREAM_REPEATS = 2
UDP_STREAM_REPEATS_MIN = 1
UDP_STREAM_REPEATS_MAX = 4
UDP_AUTH_REPEATS = 3
UDP_REPEAT_DELAY_SEC = 0.002
BLE_SERVICE_UUID = "7e570001-3e74-4b1e-b6f4-1a91f7080001"
BLE_CHARACTERISTIC_UUID = "7e570002-3e74-4b1e-b6f4-1a91f7080002"
BLE_NAME_PREFIX = "LumaFlow"
BLE_SCAN_TIMEOUT_SEC = 8.0
BLE_CONNECT_TIMEOUT_SEC = 10.0
BLE_WRITE_TIMEOUT_SEC = 1.0
BLE_DISCONNECT_TIMEOUT_SEC = 2.0
BLE_FALLBACK_WRITE_CHUNK = 20


def normalize_udp_host(value):
    """Return a canonical IPv4 host. Accepts pasted 'host:port' for convenience."""
    text = str(value or "").strip()
    if not text:
        raise ValueError("UDP target IP is empty")

    if "://" in text:
        text = text.rsplit("://", 1)[1]

    if ":" in text:
        host, port_text = text.rsplit(":", 1)
        if not host or not port_text:
            raise ValueError("UDP target must be an IPv4 address")
        try:
            pasted_port = int(port_text.strip(), 10)
        except ValueError as exc:
            raise ValueError("UDP port must be numeric") from exc
        if pasted_port != UDP_DEFAULT_PORT:
            raise ValueError(f"UDP port is fixed at {UDP_DEFAULT_PORT}")
        text = host

    try:
        return str(IPv4Address(text.strip()))
    except AddressValueError as exc:
        raise ValueError("UDP target must be an IPv4 address") from exc


def scan_lumaflow_ble_devices(timeout=BLE_SCAN_TIMEOUT_SEC, device_callback=None):
    """Scan for LumaFlow BLE devices using Web-style name-prefix matching."""
    if BleakScanner is None:
        raise RuntimeError("BLE support requires bleak. Run: pip install bleak")
    return asyncio.run(_scan_lumaflow_ble_devices_async(float(timeout), device_callback))


async def _scan_lumaflow_ble_devices_async(timeout, device_callback=None):
    entries_by_address = {}
    devices_by_address = {}

    def consider_device(device, advertisement):
        address = getattr(device, "address", "") or ""
        if not address:
            return

        entries_by_address[address] = (device, advertisement)
        matched = _build_lumaflow_ble_device(device, advertisement)
        if not matched or address in devices_by_address:
            return

        devices_by_address[address] = matched
        if device_callback:
            device_callback(matched)

    try:
        scanner = BleakScanner(detection_callback=consider_device)
        await scanner.start()
        try:
            await asyncio.sleep(timeout)
        finally:
            await scanner.stop()
    except TypeError:
        discovered = await BleakScanner.discover(timeout=timeout)
        for device in discovered:
            consider_device(device, None)

    devices = list(devices_by_address.values())
    devices.sort(key=lambda item: (item["name"], item["address"]))
    return {
        "devices": devices,
        "raw_count": len(entries_by_address),
    }


def _build_lumaflow_ble_device(device, advertisement):
    address = getattr(device, "address", "") or ""
    name = (
        getattr(device, "name", None)
        or getattr(advertisement, "local_name", None)
        or ""
    )
    service_uuids = _collect_ble_service_uuids(device, advertisement)

    # Matches the Web frontend behavior: namePrefix is the primary filter.
    # Service UUID is a compatibility bonus for devices that advertise it.
    if not name.startswith(BLE_NAME_PREFIX) and BLE_SERVICE_UUID not in service_uuids:
        return None

    return {
        "address": address,
        "name": name or "LumaFlow BLE",
        "rssi": getattr(advertisement, "rssi", None),
    }


def _collect_ble_service_uuids(device, advertisement):
    uuids = []
    if advertisement is not None:
        uuids.extend(getattr(advertisement, "service_uuids", None) or [])
    metadata = getattr(device, "metadata", None) or {}
    uuids.extend(metadata.get("uuids") or [])
    return {str(uuid).lower() for uuid in uuids}


class SerialDeviceManager(QObject):
    """
    Manager for RF transmitter output transports.
    Handles serial, UDP, and BLE lifecycle plus raw byte transmission.
    """
    connection_changed = Signal(bool, str)  # (connected, message)
    frame_sent = Signal(int)  # frames_sent count

    def __init__(self):
        super().__init__()
        self.serial_port = None
        self.udp_socket = None
        self.target_host = None
        self.target_port = None
        self.ble_client = None
        self.ble_loop = None
        self.ble_thread = None
        self.ble_address = None
        self.ble_name = None
        self.last_ble_scan_count = 0
        self.transport = 'serial'  # 'serial', 'udp', or 'ble'
        self.frames_sent = 0
        self.last_sent_frame_index = -1  # For deduplication
        self.offset_ms = 0
        self.udp_stream_repeats = UDP_STREAM_REPEATS

    def get_ports(self):
        """Get list of available serial ports with descriptions."""
        ports_info = []
        for port in serial.tools.list_ports.comports():
            port_info = {
                'device': port.device,
                'description': port.description or 'Unknown Device',
                'manufacturer': port.manufacturer or ''
            }
            ports_info.append(port_info)
        return ports_info

    def scan_ble_devices(self, timeout=BLE_SCAN_TIMEOUT_SEC):
        """Scan for LumaFlow BLE transmitters."""
        if BleakScanner is None:
            self.connection_changed.emit(
                False,
                "BLE support requires bleak. Run: pip install bleak"
            )
            return []

        try:
            result = scan_lumaflow_ble_devices(timeout)
            self.last_ble_scan_count = result["raw_count"]
            return result["devices"]
        except Exception as e:
            self.connection_changed.emit(False, f"BLE scan failed: {e}")
            return []

    def connect(self, target, baud_rate=512000, transport='serial'):
        """Connect to a serial port, UDP endpoint, or BLE device."""
        self.disconnect(emit_signal=False)
        if transport == 'udp':
            return self._connect_udp(target)
        if transport == 'ble':
            return self._connect_ble(target)
        return self._connect_serial(target, baud_rate)

    def _connect_serial(self, port, baud_rate):
        """Connect to the specified serial port."""
        try:
            self.serial_port = serial.Serial(port, baudrate=baud_rate, timeout=1)
            self.transport = 'serial'
            self.frames_sent = 0
            self.last_sent_frame_index = -1
            self.frame_sent.emit(0)
            return True
        except serial.SerialException as e:
            self.serial_port = None
            self.connection_changed.emit(False, f"Connection failed: {e}")
            return False

    def _connect_udp(self, host):
        """Create a UDP sender for the cube's fixed LAN port."""
        try:
            normalized_host = normalize_udp_host(host)
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.transport = 'udp'
            self.target_host = normalized_host
            self.target_port = UDP_DEFAULT_PORT
            self.frames_sent = 0
            self.last_sent_frame_index = -1
            self.frame_sent.emit(0)
            return True
        except Exception as e:
            self.udp_socket = None
            self.connection_changed.emit(False, f"UDP connect failed: {e}")
            return False

    def _connect_ble(self, address):
        """Connect to a LumaFlow BLE transmitter."""
        if BleakClient is None:
            self.connection_changed.emit(
                False,
                "BLE support requires bleak. Run: pip install bleak"
            )
            return False

        address = str(address or "").strip()
        if not address:
            self.connection_changed.emit(False, "BLE connect failed: no device selected")
            return False

        try:
            self._start_ble_loop()
            client = self._run_ble_coro(
                self._open_ble_client(address),
                BLE_CONNECT_TIMEOUT_SEC + 2.0,
            )
            self.ble_client = client
            self.ble_address = address
            self.ble_name = self._get_ble_client_name(client) or "LumaFlow BLE"
            self.transport = 'ble'
            self.frames_sent = 0
            self.last_sent_frame_index = -1
            self.frame_sent.emit(0)
            return True
        except Exception as e:
            self._disconnect_ble_client()
            self.connection_changed.emit(False, f"BLE connect failed: {e}")
            return False

    async def _open_ble_client(self, address):
        client = BleakClient(address, timeout=BLE_CONNECT_TIMEOUT_SEC)
        await client.connect()
        if not client.is_connected:
            raise RuntimeError("device did not report a connected state")
        return client

    def _get_ble_client_name(self, client):
        details = getattr(client, "details", None)
        for attr in ("name", "local_name"):
            value = getattr(details, attr, None)
            if value:
                return value
        return None

    def _start_ble_loop(self):
        if self.ble_loop and self.ble_loop.is_running():
            return

        ready = threading.Event()
        loop = asyncio.new_event_loop()

        def run_loop():
            asyncio.set_event_loop(loop)
            ready.set()
            loop.run_forever()
            loop.close()

        self.ble_loop = loop
        self.ble_thread = threading.Thread(
            target=run_loop,
            name="LumaFlowBLELoop",
            daemon=True,
        )
        self.ble_thread.start()
        if not ready.wait(timeout=2.0):
            raise RuntimeError("BLE event loop did not start")

    def _stop_ble_loop(self):
        loop = self.ble_loop
        thread = self.ble_thread
        if loop and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self.ble_loop = None
        self.ble_thread = None

    def _run_ble_coro(self, coro, timeout):
        if not self.ble_loop or not self.ble_loop.is_running():
            raise RuntimeError("BLE event loop is not running")
        future = asyncio.run_coroutine_threadsafe(coro, self.ble_loop)
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError:
            future.cancel()
            raise TimeoutError("BLE operation timed out")

    def _disconnect_ble_client(self):
        client = self.ble_client
        if client and self.ble_loop and self.ble_loop.is_running():
            try:
                self._run_ble_coro(client.disconnect(), BLE_DISCONNECT_TIMEOUT_SEC)
            except Exception:
                pass
        self.ble_client = None
        self.ble_address = None
        self.ble_name = None
        self._stop_ble_loop()

    def get_udp_endpoint_label(self):
        if self.target_host and self.target_port:
            return f"{self.target_host}:{self.target_port}"
        return f":{UDP_DEFAULT_PORT}"

    def get_ble_endpoint_label(self):
        if self.ble_name and self.ble_address:
            return f"{self.ble_name} ({self.ble_address})"
        return self.ble_address or "BLE"

    def mark_connected(self, message):
        """Emit a successful connection state after higher-level init succeeds."""
        self.connection_changed.emit(True, message)

    def disconnect(self, message="Disconnected", emit_signal=True):
        """Disconnect from serial port or UDP socket."""
        if self.transport == 'udp' and self.udp_socket:
            try:
                self.udp_socket.close()
            except Exception:
                pass
            self.udp_socket = None
            self.target_host = None
            self.target_port = None
        elif self.transport == 'ble' and self.ble_client:
            self._disconnect_ble_client()
        elif self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.serial_port = None
        self.transport = 'serial'
        self.frames_sent = 0
        self.last_sent_frame_index = -1
        self.frame_sent.emit(0)
        if emit_signal:
            self.connection_changed.emit(False, message)

    def is_connected(self):
        """Check if connected to a serial port or UDP endpoint."""
        if self.transport == 'udp':
            return self.udp_socket is not None
        if self.transport == 'ble':
            return self.ble_client is not None and bool(self.ble_client.is_connected)
        return self.serial_port is not None and self.serial_port.is_open

    def send_data(self, data_bytes, count_frame=True):
        """Send raw bytes to serial port or UDP endpoint."""
        if not self.is_connected():
            return False
        try:
            if self.transport == 'udp':
                self._send_udp_data(data_bytes)
            elif self.transport == 'ble':
                self._send_ble_data(data_bytes)
            else:
                self.serial_port.write(data_bytes)
            if count_frame:
                self.frames_sent += 1
                self.frame_sent.emit(self.frames_sent)
            return True
        except Exception as e:
            print(f"Send error: {e}")
            self.disconnect(message=f"Disconnected: {e}")
            return False

    def _send_udp_data(self, data_bytes):
        data = bytes(data_bytes)
        repeat_count = self._get_udp_repeat_count(data)

        for index in range(repeat_count):
            self.udp_socket.sendto(data, (self.target_host, self.target_port))
            if index + 1 < repeat_count and UDP_REPEAT_DELAY_SEC > 0:
                time.sleep(UDP_REPEAT_DELAY_SEC)

    def _get_udp_repeat_count(self, data):
        cmd = self._get_tlv_command(data)
        if cmd == CMD_AUTH:
            return UDP_AUTH_REPEATS
        if cmd == CMD_STREAM:
            return self.udp_stream_repeats
        return 1

    def _get_tlv_command(self, data):
        if (
            len(data) >= 6
            and data[0:2] == TLV_HEAD
            and data[-1] == TLV_TAIL
        ):
            return data[TLV_CMD_OFFSET]
        return None

    def _send_ble_data(self, data_bytes):
        if not self.ble_client:
            raise RuntimeError("BLE client is not connected")

        data = bytes(data_bytes)
        chunk_size = self._get_ble_write_chunk_size()
        for offset in range(0, len(data), chunk_size):
            chunk = data[offset:offset + chunk_size]
            self._run_ble_coro(
                self.ble_client.write_gatt_char(
                    BLE_CHARACTERISTIC_UUID,
                    chunk,
                    response=False,
                ),
                BLE_WRITE_TIMEOUT_SEC,
            )

    def _get_ble_write_chunk_size(self):
        if not self.ble_client:
            return BLE_FALLBACK_WRITE_CHUNK
        mtu_size = int(getattr(self.ble_client, "mtu_size", 0) or 0)
        if mtu_size > 3:
            return max(1, mtu_size - 3)
        return BLE_FALLBACK_WRITE_CHUNK

    def set_offset(self, offset_ms):
        """Set the timing offset in milliseconds."""
        self.offset_ms = offset_ms

    def get_offset(self):
        """Get the current timing offset."""
        return self.offset_ms

    def set_udp_stream_repeats(self, repeats):
        """Set UDP STREAM repeat count for reliability tuning."""
        try:
            value = int(repeats)
        except (TypeError, ValueError):
            value = UDP_STREAM_REPEATS
        self.udp_stream_repeats = max(UDP_STREAM_REPEATS_MIN, min(UDP_STREAM_REPEATS_MAX, value))

    def get_udp_stream_repeats(self):
        """Get UDP STREAM repeat count."""
        return self.udp_stream_repeats

    def reset_frame_tracking(self):
        """Reset frame tracking for new playback session."""
        self.last_sent_frame_index = -1
        self.frames_sent = 0
        self.frame_sent.emit(0)

    def get_frames_sent(self):
        """Get the number of frames sent."""
        return self.frames_sent
