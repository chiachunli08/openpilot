import unittest

import numpy as np

from openpilot.sunnypilot.modeld_v2.traffic_signal_yolo import CLASSES, CONFIDENCE_THRESHOLD, MODEL_INPUT, _decode


class TestTrafficSignalYoloDecode(unittest.TestCase):
  def make_output(self, signal: str, confidence: float, cx: float = 0.5, size: float = 0.08) -> np.ndarray:
    # Ultralytics detect export layout: [cx, cy, w, h, class...], shape (1, C, N).
    channels = 4 + len(CLASSES)
    out = np.zeros((1, channels, 4), dtype=np.float32)
    box = 0
    out[0, 0, box] = cx * MODEL_INPUT
    out[0, 1, box] = 0.25 * MODEL_INPUT
    out[0, 2, box] = size * MODEL_INPUT
    out[0, 3, box] = size * MODEL_INPUT
    out[0, 4 + CLASSES.index(signal), box] = confidence
    return out

  def test_detects_each_supported_class(self):
    for signal in CLASSES:
      with self.subTest(signal=signal):
        detected, confidence = _decode(self.make_output(signal, 0.91))
        self.assertEqual(detected, signal)
        self.assertAlmostEqual(confidence, 0.91, places=4)

  def test_accepts_transposed_export_layout(self):
    out = self.make_output("red", 0.88).transpose(0, 2, 1)
    signal, confidence = _decode(out)
    self.assertEqual(signal, "red")
    self.assertAlmostEqual(confidence, 0.88, places=4)

  def test_rejects_below_threshold(self):
    signal, confidence = _decode(self.make_output("green", CONFIDENCE_THRESHOLD - 0.01))
    self.assertIsNone(signal)
    self.assertEqual(confidence, 0.0)

  def test_prefers_relevant_center_signal(self):
    channels = 4 + len(CLASSES)
    out = np.zeros((1, channels, 2), dtype=np.float32)
    # Slightly higher confidence but tiny/far and at the extreme edge.
    out[0, :4, 0] = [0.02 * MODEL_INPUT, 0.2 * MODEL_INPUT, 0.01 * MODEL_INPUT, 0.01 * MODEL_INPUT]
    out[0, 4 + CLASSES.index("red"), 0] = 0.95
    # More relevant forward signal.
    out[0, :4, 1] = [0.5 * MODEL_INPUT, 0.2 * MODEL_INPUT, 0.08 * MODEL_INPUT, 0.08 * MODEL_INPUT]
    out[0, 4 + CLASSES.index("green"), 1] = 0.90
    signal, _ = _decode(out)
    self.assertEqual(signal, "green")

  def test_rejects_invalid_shapes_and_nan(self):
    self.assertEqual(_decode(np.zeros((3,), dtype=np.float32)), (None, 0.0))
    bad = self.make_output("yellow", 0.9)
    bad[0, 0, 0] = np.nan
    self.assertEqual(_decode(bad), (None, 0.0))


if __name__ == "__main__":
  unittest.main()
