import unittest

from core.serial_protocol import (
    CMD_AUTH,
    CMD_STREAM,
    TLV_HEAD,
    TLV_TAIL,
    build_auth_frame,
    build_stream_frame,
    describe_auth_lic,
    parse_auth_lic,
)


SAMPLE_LIC = (
    "E8:3D:C1:94:FC:DA|1776522768|"
    "3044022030C3300FA64F2DFF0E05ABEE57DAE2DFCDB50FA72FFEBC7BD03BBB192775E534"
    "02202B27FDEE046394B99866332A9449BE2AC77E853AA6FFE0EFE731729F0F1AFCDD"
)


class SerialProtocolTests(unittest.TestCase):
    def test_stream_frame_uses_tlv_stream_command(self):
        frame = {}
        expected_payload = bytearray()
        for index in range(10):
            func = index % 4
            red = index
            green = 15 - index
            blue = (index * 2) % 16
            frame[f"ch{index}_function"] = func
            frame[f"ch{index}_red"] = red
            frame[f"ch{index}_green"] = green
            frame[f"ch{index}_blue"] = blue
            expected_payload.extend((((func << 4) | red), ((green << 4) | blue)))

        packet = build_stream_frame(frame)

        self.assertEqual(packet[:2], TLV_HEAD)
        self.assertEqual(packet[2], 21)
        self.assertEqual(packet[3], CMD_STREAM)
        self.assertEqual(packet[4:24], bytes(expected_payload))
        self.assertEqual(packet[-1], TLV_TAIL)
        self.assertEqual(packet[-2], (21 + CMD_STREAM + sum(expected_payload)) & 0xFF)

    def test_auth_frame_is_built_from_lic_text(self):
        host_time = 1776000000
        license_data = parse_auth_lic(SAMPLE_LIC)

        packet = build_auth_frame(SAMPLE_LIC, host_time)

        payload = packet[4:-2]
        self.assertEqual(packet[:2], TLV_HEAD)
        self.assertEqual(packet[3], CMD_AUTH)
        self.assertEqual(payload[:4], host_time.to_bytes(4, "little"))
        self.assertEqual(payload[4:8], license_data.expire_time.to_bytes(4, "little"))
        self.assertEqual(payload[8], len(license_data.signature))
        self.assertEqual(payload[9:], license_data.signature)
        self.assertEqual(packet[2], 1 + len(payload))
        self.assertEqual(packet[-1], TLV_TAIL)
        self.assertEqual(packet[-2], (packet[2] + CMD_AUTH + sum(payload)) & 0xFF)

    def test_auth_frame_rejects_expired_lic(self):
        with self.assertRaises(ValueError):
            build_auth_frame(SAMPLE_LIC, 1776522769)

    def test_describe_auth_lic_returns_remaining_info(self):
        info = describe_auth_lic(SAMPLE_LIC, now=1776000000)

        self.assertTrue(info["valid"])
        self.assertEqual(info["device_mac"], "E8:3D:C1:94:FC:DA")
        self.assertEqual(info["signature"], "70 bytes")
        self.assertTrue(str(info["validity"]).startswith("Remaining "))

    def test_describe_auth_lic_returns_invalid_status(self):
        info = describe_auth_lic("bad lic")

        self.assertFalse(info["valid"])
        self.assertFalse(info["empty"])
        self.assertIn("Invalid LIC", info["status"])


if __name__ == "__main__":
    unittest.main()
