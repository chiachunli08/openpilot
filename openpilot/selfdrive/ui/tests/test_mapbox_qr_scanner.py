import runpy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import numpy as np


class TestMapboxQrScanner(unittest.TestCase):
  def setUp(self):
    self.params, self.memory = Mock(), Mock()
    self.params.get_bool.return_value = False
    self.state = Mock(params=self.params, ignition=False)
    self.state.is_onroad.return_value = False
    self.device = Mock()
    self.stack = [object()]
    self.gui = Mock()
    self.gui.get_active_widget.side_effect = lambda: self.stack[-1]
    self.gui.pop_widget.side_effect = lambda: self.stack.pop().hide_event()
    self.decoder = Mock()
    self.decoder.read_barcodes.return_value = []

    class FakeCameraView:
      def __init__(inner, *args):
        inner.frame = None
        inner.release = Mock()
        self.state.add_offroad_transition_callback(inner._offroad_transition)

      def show_event(inner):
        pass

      def hide_event(inner):
        pass

      def close(inner):
        inner.release()

      def _handle_mouse_release(inner, _):
        pass

    self.modules = {
      "pyray": NS(Rectangle=NS),
      "openpilot.cereal.visionipc": NS(VisionStreamType=NS(VISION_STREAM_CABIN=1)),
      "openpilot.common.params": NS(Params=lambda path: self.memory),
      "openpilot.selfdrive.ui.onroad.cameraview": NS(CameraView=FakeCameraView),
      "openpilot.selfdrive.ui.ui_state": NS(ui_state=self.state, device=self.device),
      "openpilot.system.ui.lib.application": NS(gui_app=self.gui, FontWeight=NS(), TextAlignment=NS()),
      "openpilot.system.ui.lib.multilang": NS(tr=lambda text: text),
      "openpilot.system.ui.widgets.confirm_dialog": NS(alert_dialog=lambda text: text),
      "openpilot.system.ui.widgets.label": NS(gui_label=Mock()),
      "zxingcpp": self.decoder,
    }

  def open_scanner(self):
    path = Path(__file__).parents[1] / "sunnypilot/widgets/mapbox_qr_scanner.py"
    with patch.dict(sys.modules, self.modules):
      scanner = runpy.run_path(str(path))["MapboxQrScannerDialog"]()
      self.stack.append(scanner)
      scanner.show_event()
    self.addCleanup(scanner.close)
    return scanner

  @staticmethod
  def set_frame(scanner):
    scanner.frame = NS(data=memoryview(bytearray(range(12))), uv_offset=8, stride=4, width=2, height=2)

  def test_cancel_cleans_up_and_stale_callbacks_do_not_pop_other_screens(self):
    scanner = self.open_scanner()
    self.assertTrue(scanner._session.active)
    scanner._handle_mouse_release(None)
    self.memory.remove.assert_called_once_with("MapboxQrScanHeartbeat")
    self.params.put_bool.assert_called_with("IsDriverViewEnabled", False, block=True)
    self.state.remove_offroad_transition_callback.assert_called_once_with(scanner._offroad_transition)
    self.device.remove_interactive_timeout_callback.assert_called_once_with(scanner._cancel)
    self.state.is_onroad.return_value = True
    scanner._offroad_transition()
    scanner._cancel()
    scanner.close()
    self.assertEqual(len(self.stack), 1)
    self.gui.pop_widget.assert_called_once()
    scanner.release.assert_called_once()

  def test_success_restores_ir_and_saves_to_correct_field(self):
    for code, param, token in [("M0public", "MapboxPublicKey", "pk.public"), ("S0secret", "MapboxSecretKey", "sk.secret")]:
      with self.subTest(param=param):
        scanner = self.open_scanner()
        self.set_frame(scanner)
        self.decoder.read_barcodes.return_value = [NS(text=f"sunnypilot-mapbox:v1:{code}")]
        scanner._scan_frame()
        self.params.put.assert_called_with(param, token, block=True)
        self.assertFalse(scanner._session.active)
        self.assertTrue(scanner._closed)
        self.memory.remove.assert_called_with("MapboxQrScanHeartbeat")
        luminance = self.decoder.read_barcodes.call_args.args[0]
        np.testing.assert_array_equal(luminance, [[0, 1], [4, 5]])

  def test_missing_decoder_does_not_disable_ir(self):
    self.modules["zxingcpp"] = None
    scanner = self.open_scanner()
    self.assertIn("decoder missing", scanner._status)
    self.assertFalse(scanner._session.active)
    self.memory.put.assert_not_called()
    self.params.put_bool.assert_not_called()

  def test_unknown_qr_does_not_write_a_token(self):
    scanner = self.open_scanner()
    self.set_frame(scanner)
    self.decoder.read_barcodes.return_value = [NS(text="https://example.com")]
    scanner._scan_frame()
    self.params.put.assert_not_called()
    self.assertIn("not a sunnypilot", scanner._status)

  def test_no_result_and_frame_error_have_distinct_messages(self):
    scanner = self.open_scanner()
    self.set_frame(scanner)
    scanner._scan_frame()
    self.assertIn("No QR detected", scanner._status)
    self.decoder.read_barcodes.side_effect = RuntimeError("frame error")
    scanner._last_scan = 0
    scanner._scan_frame()
    self.assertIn("Unable to decode camera frame", scanner._status)

  def test_onroad_transition_cancels_before_reconnecting_camera(self):
    scanner = self.open_scanner()
    self.state.is_onroad.return_value = True
    scanner._offroad_transition()
    self.assertFalse(scanner._session.active)
    self.assertTrue(scanner._closed)


if __name__ == "__main__":
  unittest.main()
