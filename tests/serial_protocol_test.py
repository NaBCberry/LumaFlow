import unittest

from core.serial_protocol import build_stream_payload


def make_frame(red=15, green=10, blue=1, function=2):
    frame = {}
    for index in range(10):
        frame[f"ch{index}_function"] = function
        frame[f"ch{index}_red"] = red
        frame[f"ch{index}_green"] = green
        frame[f"ch{index}_blue"] = blue
    return frame


class StreamBrightnessTests(unittest.TestCase):
    def test_default_brightness_preserves_payload(self):
        payload = build_stream_payload(make_frame())
        self.assertEqual(bytes((0x2F, 0xA1)) * 10, payload)

    def test_brightness_scales_rgb_but_not_function(self):
        payload = build_stream_payload(make_frame(), brightness_percent=50)
        self.assertEqual(bytes((0x28, 0x51)) * 10, payload)

    def test_zero_brightness_preserves_function(self):
        payload = build_stream_payload(make_frame(), brightness_percent=0)
        self.assertEqual(bytes((0x20, 0x00)) * 10, payload)

    def test_invalid_brightness_is_rejected(self):
        with self.assertRaises(ValueError):
            build_stream_payload(make_frame(), brightness_percent=101)


if __name__ == "__main__":
    unittest.main()
