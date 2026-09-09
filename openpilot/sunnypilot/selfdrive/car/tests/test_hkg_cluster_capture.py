import io
import json
import unittest

from opendbc.car.hyundai.hyundaicanfd import hkg_can_fd_checksum
from tools.hkg_cluster.ev6_cluster_capture import convert_stream


def make_frame(address: int, length: int, counter: int, marker: int = 0) -> bytes:
  data = bytearray(length)
  data[2] = counter
  data[3] = marker
  checksum = hkg_can_fd_checksum(address, None, data)
  data[:2] = checksum.to_bytes(2, "little")
  return bytes(data)


class TestHkgClusterCapture(unittest.TestCase):
  def test_passive_audit_preserves_raw_and_never_authorizes_transmission(self):
    frames = [
      {"timestamp_nanos": 1_000_000_000, "bus": 1, "address": "0x161", "data": make_frame(0x161, 32, 4).hex(), "event": "idle"},
      {"timestamp_nanos": 1_050_000_000, "bus": 1, "address": "0x161", "data": make_frame(0x161, 32, 5, 1).hex(), "event": "lane_change"},
      {"timestamp_nanos": 1_100_000_000, "bus": 129, "address": "0x161", "data": make_frame(0x161, 32, 6).hex(), "event": "tx_echo"},
      {"timestamp_nanos": 1_150_000_000, "bus": 1, "address": "0x162", "data": "00" * 8, "event": "bad_length"},
    ]
    output = io.StringIO()
    convert_stream(io.StringIO("\n".join(json.dumps(frame) for frame in frames)), output)
    rows = [json.loads(row) for row in output.getvalue().splitlines()]

    raw = rows[0]
    self.assertEqual(raw["record_type"], "passive_cluster_frame")
    self.assertTrue(raw["checksum_valid"])
    self.assertFalse(raw["compatibility_proof"])
    self.assertEqual(rows[1]["counter_delta"], 1)
    self.assertIn(3, rows[1]["changed_byte_indices"])
    self.assertEqual(rows[2]["rejection"], "transmit_echo_or_invalid_bus")
    self.assertEqual(rows[3]["rejection"], "wrong_payload_length:8")

    summary = rows[-1]
    self.assertEqual(summary["compatibility_state"], "unconfirmed")
    self.assertFalse(summary["active_transmission_authorized"])
    status_stream = next(stream for stream in summary["streams"] if stream["address"] == "0x161" and stream["source_bus"] == 1)
    self.assertEqual(status_stream["valid_checksums"], 2)
    self.assertEqual(status_stream["counter_gaps"], 0)
    self.assertAlmostEqual(status_stream["median_frequency_hz"], 20.0)


if __name__ == "__main__":
  unittest.main()
