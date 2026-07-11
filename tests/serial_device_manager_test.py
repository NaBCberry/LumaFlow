import unittest
from unittest.mock import patch

from core.serial_device_manager import (
    CMD_AUTH,
    SERIAL_AUTH_REPEATS,
    SerialDeviceManager,
)
from core.serial_protocol import build_tlv_frame


class FakeSerialPort:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.dtr = True
        self.rts = True
        self.port = None
        self.is_open = False
        self.writes = []
        self.flush_count = 0

    def open(self):
        self.is_open = True

    def close(self):
        self.is_open = False

    def reset_input_buffer(self):
        pass

    def reset_output_buffer(self):
        pass

    def write(self, data):
        self.writes.append(bytes(data))
        return len(data)

    def flush(self):
        self.flush_count += 1


class SerialDeviceManagerTests(unittest.TestCase):
    @patch("core.serial_device_manager.time.sleep")
    @patch("core.serial_device_manager.serial.Serial")
    def test_serial_open_disables_control_lines(self, serial_factory, _sleep):
        fake_port = FakeSerialPort()
        serial_factory.return_value = fake_port
        manager = SerialDeviceManager()

        self.assertTrue(manager._connect_serial("COM7", 512000))

        serial_kwargs = serial_factory.call_args.kwargs
        self.assertIsNone(serial_kwargs["port"])
        self.assertFalse(serial_kwargs["rtscts"])
        self.assertFalse(serial_kwargs["dsrdtr"])
        self.assertFalse(fake_port.dtr)
        self.assertFalse(fake_port.rts)
        self.assertEqual("COM7", fake_port.port)

    @patch("core.serial_device_manager.time.sleep")
    def test_serial_auth_is_repeated_but_stream_is_not(self, _sleep):
        manager = SerialDeviceManager()
        fake_port = FakeSerialPort()
        fake_port.open()
        manager.serial_port = fake_port

        auth_frame = build_tlv_frame(CMD_AUTH, b"auth")
        manager._send_serial_data(auth_frame)
        manager._send_serial_data(build_tlv_frame(0xD8, b"stream"))

        self.assertEqual(SERIAL_AUTH_REPEATS + 1, len(fake_port.writes))
        self.assertEqual(SERIAL_AUTH_REPEATS + 1, fake_port.flush_count)


if __name__ == "__main__":
    unittest.main()
