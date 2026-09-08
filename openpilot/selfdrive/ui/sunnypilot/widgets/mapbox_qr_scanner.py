import time

import numpy as np
import pyray as rl

from openpilot.cereal.visionipc import VisionStreamType
from openpilot.selfdrive.ui.onroad.cameraview import CameraView
from openpilot.selfdrive.ui.ui_state import device, ui_state
from openpilot.sunnypilot.navd.mapbox_token_codec import decode_mapbox_qr_payload
from openpilot.system.ui.lib.application import FontWeight, TextAlignment, gui_app
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.widgets.confirm_dialog import alert_dialog
from openpilot.system.ui.widgets.label import gui_label


class MapboxQrScannerDialog(CameraView):
  """Scan a scoped Mapbox token QR code using the cabin camera while offroad."""

  SCAN_INTERVAL = 0.35

  def __init__(self):
    super().__init__("camerad", VisionStreamType.VISION_STREAM_CABIN)
    self._last_scan = 0.0
    self._finished = False
    self._status = tr("Hold the QR code inside the frame")
    device.add_interactive_timeout_callback(gui_app.pop_widget)
    ui_state.params.put_bool("IsDriverViewEnabled", True, block=True)

  def hide_event(self):
    super().hide_event()
    ui_state.params.put_bool("IsDriverViewEnabled", False, block=True)
    self.close()

  def _offroad_transition(self):
    super()._offroad_transition()
    if ui_state.is_onroad():
      gui_app.pop_widget()

  def _handle_mouse_release(self, _):
    super()._handle_mouse_release(_)
    gui_app.pop_widget()

  def _scan_frame(self) -> None:
    if self.frame is None or self._finished:
      return

    now = time.monotonic()
    if now - self._last_scan < self.SCAN_INTERVAL:
      return
    self._last_scan = now

    try:
      import zxingcpp

      # The cabin stream is NV12. QR decoding only needs its full-resolution Y plane.
      luminance = np.array(self.frame.data[:self.frame.uv_offset], dtype=np.uint8)
      luminance = luminance.reshape((-1, self.frame.stride))[:self.frame.height, :self.frame.width]
      results = zxingcpp.read_barcodes(luminance, formats=zxingcpp.BarcodeFormat.QRCode,
                                      try_rotate=True, try_downscale=True, try_invert=True)
      for result in results:
        try:
          param, token = decode_mapbox_qr_payload(result.text)
        except ValueError:
          self._status = tr("This is not a sunnypilot Mapbox QR code")
          continue

        ui_state.params.put(param, token)
        self._finished = True
        token_type = tr("Public") if param == "MapboxPublicKey" else tr("Secret")
        gui_app.pop_widget()
        gui_app.push_widget(alert_dialog(tr("Mapbox %s token saved") % token_type))
        return
    except (BufferError, ImportError, TypeError, ValueError):
      self._status = tr("QR scanner unavailable")

  def _render(self, rect: rl.Rectangle) -> int:
    super()._render(rect)
    self._scan_frame()

    guide_size = min(rect.width * 0.58, rect.height * 0.64)
    guide = rl.Rectangle(rect.x + (rect.width - guide_size) / 2,
                         rect.y + (rect.height - guide_size) / 2,
                         guide_size, guide_size)
    rl.draw_rectangle_rounded_lines_ex(guide, 0.06, 12, 9, rl.Color(71, 201, 255, 255))
    gui_label(rl.Rectangle(rect.x + 40, rect.y + 35, rect.width - 80, 90),
              tr("Scan Mapbox Token QR"), font_size=58, font_weight=FontWeight.BOLD,
              alignment=TextAlignment.CENTER)
    gui_label(rl.Rectangle(rect.x + 40, rect.y + rect.height - 120, rect.width - 80, 80),
              self._status, font_size=36, alignment=TextAlignment.CENTER)
    return -1
