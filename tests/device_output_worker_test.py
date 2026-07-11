import unittest

from core.device_output_worker import DeviceOutputWorker


class FakeDeviceManager:
    def __init__(self):
        self.connected = False
        self.connect_args = None
        self.sent = []
        self.marked_message = None
        self.disconnect_message = None

    def connect(self, target, baud_rate=512000, transport="serial"):
        self.connect_args = (target, baud_rate, transport)
        self.connected = True
        return True

    def send_data(self, data, count_frame=True):
        self.sent.append((data, count_frame))
        return True

    def is_connected(self):
        return self.connected

    def mark_connected(self, message):
        self.marked_message = message

    def disconnect(self, message="Disconnected", emit_signal=True):
        self.connected = False
        self.disconnect_message = (message, emit_signal)

    def get_udp_endpoint_label(self):
        return "192.168.1.2:32712"

    def get_ble_endpoint_label(self):
        return "LumaFlow-Cube (AA:BB)"

    def reset_frame_tracking(self):
        pass


class DeviceOutputWorkerTests(unittest.TestCase):
    def test_serial_connect_sends_auth_before_marking_connected(self):
        device = FakeDeviceManager()
        worker = DeviceOutputWorker(device, None, lambda frame: frame)
        statuses = []
        finished = []
        worker.auth_status_changed.connect(statuses.append)
        worker.operation_finished.connect(lambda: finished.append(True))

        worker.connect_to_device("COM7", 512000, b"auth")

        self.assertEqual(("COM7", 512000, "serial"), device.connect_args)
        self.assertEqual([(b"auth", False)], device.sent)
        self.assertEqual(["Sent"], statuses)
        self.assertIn("COM7", device.marked_message)
        self.assertEqual([True], finished)

    def test_ble_connect_uses_ble_transport(self):
        device = FakeDeviceManager()
        worker = DeviceOutputWorker(device, None, lambda frame: frame)

        worker.connect_to_device("AA:BB", -2, b"auth")

        self.assertEqual(("AA:BB", 512000, "ble"), device.connect_args)
        self.assertIn("via BLE", device.marked_message)


if __name__ == "__main__":
    unittest.main()
