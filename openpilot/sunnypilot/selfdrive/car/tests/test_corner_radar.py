import io
import json
import math
import unittest

from openpilot.sunnypilot.selfdrive.car.corner_radar import CornerRadarTracker, decode_frame
from tools.corner_radar.ev6_corner_radar import convert_stream


PUBLIC_SAMPLE = bytes.fromhex(
  "a3805e0511624c8069810a06a16050807b809e0a1c614c80977f4a0ccca6dc80" +
  "7f82f20cea555c807d7f4a0f69a84c806f7ed60f7381e080677faa110f684880"
)
INACTIVE_RECORD = b"\x80\x80\x00\x00\x00\x00\x00\x00"


def make_record(distance_m: float, encoded_angle_deg: float = 100.0) -> bytes:
  distance = round(distance_m * 256)
  angle = round(encoded_angle_deg * 256)
  return bytes((1, 0, 0, distance >> 8, distance & 0xFF, angle >> 8, angle & 0xFF, 0))


def make_frame(*records: bytes) -> bytes:
  return b"".join((*records, *(INACTIVE_RECORD for _ in range(8 - len(records)))))


class TestCornerRadar(unittest.TestCase):
  def test_public_sample_formula_and_unverified_fields(self):
    records = decode_frame(1_000_000_000, 9, 0x400, PUBLIC_SAMPLE)
    first = records[0]
    self.assertEqual(len(records), 8)
    self.assertTrue(math.isclose(first.distance_m, 5.06640625))
    self.assertTrue(math.isclose(first.encoded_angle_deg, 98.296875))
    self.assertTrue(math.isclose(first.corrected_angle_deg, 66.703125))
    self.assertTrue(first.candidate_active)
    self.assertFalse(first.status_validated)

  def test_wrong_length_overlap_is_retained_but_not_decoded(self):
    tracker = CornerRadarTracker()
    self.assertFalse(tracker.ingest(1_000_000_000, 1, 0x500, b"\0" * 8))
    self.assertEqual(tracker.rejected_length, 1)
    self.assertEqual(tracker.candidate_frames, 0)
    raw = tracker.pop_raw_frames()
    self.assertEqual(len(raw), 1)
    self.assertFalse(raw[0].accepted_length)

  def test_received_bus_is_discovered_from_valid_frame(self):
    tracker = CornerRadarTracker()
    self.assertTrue(tracker.ingest(1_000_000_000, 3, 0x300, make_frame(make_record(12.0))))
    self.assertEqual(tracker.observed_buses, {3})

  def test_stable_track_produces_separate_closing_speed_estimate(self):
    tracker = CornerRadarTracker()
    for index, distance in enumerate((10.0, 9.875, 9.75, 9.625)):
      tracker.ingest(1_000_000_000 + index * 50_000_000, 2, 0x300, make_frame(make_record(distance)))
    self.assertEqual(len(tracker.targets), 1)
    target = next(iter(tracker.targets.values()))
    self.assertTrue(math.isclose(target.estimated_radial_speed_mps, -2.5, abs_tol=0.001))
    output = tracker.json_records(1_150_000_000)[0]
    self.assertIsNone(output["relative_speed_mps"])
    self.assertEqual(output["relative_speed_source"], "unknown_not_decoded")
    self.assertEqual(output["estimated_radial_speed_source"], "range_difference_temporal_track")

  def test_slot_change_suppresses_speed_without_becoming_a_fixed_id(self):
    tracker = CornerRadarTracker()
    for index, distance in enumerate((10.0, 9.875, 9.75)):
      tracker.ingest(1_000_000_000 + index * 50_000_000, 2, 0x300, make_frame(make_record(distance)))
    tracker.ingest(1_150_000_000, 2, 0x300, make_frame(INACTIVE_RECORD, make_record(9.625)))
    self.assertEqual(len(tracker.targets), 1)
    target = next(iter(tracker.targets.values()))
    self.assertEqual(target.record.slot, 1)
    self.assertIsNone(target.estimated_radial_speed_mps)

  def test_jump_and_ambiguous_association_create_new_tracks(self):
    jump_tracker = CornerRadarTracker()
    jump_tracker.ingest(1_000_000_000, 4, 0x600, make_frame(make_record(10.0)))
    jump_tracker.ingest(1_050_000_000, 4, 0x600, make_frame(make_record(40.0)))
    self.assertEqual(len(jump_tracker.targets), 2)
    self.assertTrue(all(target.estimated_radial_speed_mps is None for target in jump_tracker.targets.values()))

    ambiguous_tracker = CornerRadarTracker()
    ambiguous_tracker.ingest(1_000_000_000, 4, 0x600, make_frame(make_record(10.0), make_record(10.2)))
    ambiguous_tracker.ingest(1_050_000_000, 4, 0x600, make_frame(make_record(10.1)))
    self.assertEqual(len(ambiguous_tracker.targets), 3)

  def test_timestamp_error_is_retained_and_does_not_update_track(self):
    tracker = CornerRadarTracker()
    frame = make_frame(make_record(10.0))
    tracker.ingest(1_000_000_000, 2, 0x300, frame)
    self.assertFalse(tracker.ingest(900_000_000, 2, 0x300, frame))
    self.assertEqual(tracker.timestamp_errors, 1)
    self.assertEqual(tracker.candidate_frames, 1)
    raw = tracker.pop_raw_frames()
    self.assertEqual(len(raw), 2)
    self.assertTrue(raw[0].timestamp_accepted)
    self.assertFalse(raw[1].timestamp_accepted)

  def test_stale_target_expires_and_tx_echo_is_ignored(self):
    tracker = CornerRadarTracker()
    frame = make_frame(make_record(10.0))
    tracker.ingest(1_000_000_000, 2, 0x300, frame)
    tracker.expire(1_350_000_001)
    self.assertFalse(tracker.targets)
    tracker.pop_raw_frames()
    self.assertFalse(tracker.ingest(1_400_000_000, 130, 0x300, frame))
    self.assertFalse(tracker.raw_frames)

  def test_jsonl_preserves_raw_and_source_distinctions(self):
    input_row = json.dumps({
      "timestamp_nanos": 1_000_000_000,
      "bus": 2,
      "address": "0x300",
      "data": make_frame(make_record(10.0)).hex(),
    })
    output = io.StringIO()
    convert_stream(io.StringIO(input_row), output)
    rows = [json.loads(row) for row in output.getvalue().splitlines()]
    self.assertEqual(rows[0]["record_type"], "raw_frame")
    self.assertEqual(rows[0]["data"], make_frame(make_record(10.0)).hex())
    decoded = next(row for row in rows if row["record_type"] == "decoded_record")
    self.assertIsNone(decoded["relative_speed_mps"])
    self.assertEqual(decoded["relative_speed_source"], "unknown_not_decoded")
    self.assertFalse(decoded["target_identity_validated"])
    self.assertEqual(rows[-1]["record_type"], "summary")


if __name__ == "__main__":
  unittest.main()
