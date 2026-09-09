import unittest
from unittest.mock import Mock

from openpilot.sunnypilot.navd.mapbox_qr_scan import MapboxQrScanSession


class TestMapboxQrScanSession(unittest.TestCase):
  def setUp(self):
    self.now = 10_000_000_000
    self.params = Mock()
    self.params.get_bool.return_value = False
    self.memory = Mock()
    self.session = MapboxQrScanSession(self.params, self.memory, lambda: self.now)

  def test_live_scan_renews_only_twice_a_second(self):
    self.session.start(False)
    self.memory.put.assert_called_once_with("MapboxQrScanHeartbeat", str(self.now), block=True)
    self.params.put_bool.assert_called_once_with("IsDriverViewEnabled", True, block=True)
    self.now += 400_000_000
    self.assertTrue(self.session.update(False, False))
    self.assertEqual(self.memory.put.call_count, 1)
    self.now += 100_000_000
    self.assertTrue(self.session.update(False, False))
    self.assertEqual(self.memory.put.call_count, 2)

  def test_cancel_restores_camera_and_removes_heartbeat_once(self):
    self.session.start(False)
    self.session.stop()
    self.session.stop()
    self.memory.remove.assert_called_once_with("MapboxQrScanHeartbeat")
    self.params.put_bool.assert_called_with("IsDriverViewEnabled", False, block=True)
    self.assertFalse(self.session.update(False, False))

  def test_driving_and_ignition_rising_stop_the_scan(self):
    for onroad, ignition in [(True, False), (False, True)]:
      with self.subTest(onroad=onroad, ignition=ignition):
        self.session.start(False)
        self.assertFalse(self.session.update(onroad, ignition))
        self.assertFalse(self.session.active)
        self.memory.remove.assert_called_with("MapboxQrScanHeartbeat")

  def test_initial_ignition_is_allowed_while_offroad(self):
    self.session.start(True)
    self.assertTrue(self.session.update(False, True))

  def test_scan_timeout_releases_ir(self):
    self.session.start(False)
    self.now += 90_000_000_000
    self.assertFalse(self.session.update(False, False))
    self.memory.remove.assert_called_once_with("MapboxQrScanHeartbeat")

  def test_failed_camera_start_releases_request(self):
    self.params.put_bool.side_effect = [OSError("unavailable"), None]
    with self.assertRaises(OSError):
      self.session.start(False)
    self.assertFalse(self.session.active)
    self.memory.remove.assert_called_once_with("MapboxQrScanHeartbeat")

  def test_previous_camera_request_is_restored(self):
    self.params.get_bool.return_value = True
    self.session.start(False)
    self.session.stop()
    self.params.put_bool.assert_called_with("IsDriverViewEnabled", True, block=True)


if __name__ == "__main__":
  unittest.main()
