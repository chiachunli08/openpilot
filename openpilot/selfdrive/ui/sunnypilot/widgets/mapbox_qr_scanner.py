import time

import numpy as np
import pyray as rl

from openpilot.cereal.visionipc import VisionStreamType
from openpilot.common.params import Params
from openpilot.common.hardware.hw import Paths
from openpilot.selfdrive.ui.onroad.cameraview import CameraView
from openpilot.selfdrive.ui.ui_state import device, ui_state
from openpilot.sunnypilot.navd.mapbox_qr_scan import MapboxQrScanSession
from openpilot.sunnypilot.navd.qr_decoder import load_decoder
from openpilot.sunnypilot.navd.mapbox_token_codec import decode_mapbox_qr_payload
from openpilot.system.ui.lib.application import FontWeight, TextAlignment, gui_app
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.widgets.confirm_dialog import alert_dialog
from openpilot.system.ui.widgets.label import gui_label


class MapboxQrScannerDialog(CameraView):
  """Scan a scoped Mapbox token QR code using the cabin camera while offroad."""

  SCAN_INTERVAL = 0.35

  def __init__(self):
    self._closed = False
    self._session = None
    super().__init__("camerad", VisionStreamType.VISION_STREAM_CABIN)
    self._last_scan = 0.0
    self._status = tr("Hold the QR code inside the frame")
    try:
      self._decoder = load_decoder(Paths.qr_decoder_root())
    except (ImportError, OSError):
      self._decoder = None
      self._status = tr("QR decoder missing. Download or repair it in the OSM menu.")

    self._session = MapboxQrScanSession(ui_state.params, Params("/dev/shm/params"))
    device.add_interactive_timeout_callback(self._cancel)

  def show_event(self):
    super().show_event()
    if ui_state.is_onroad():
      self._cancel()
    elif self._decoder is not None:
      self._session.start(ui_state.ignition)

  def hide_event(self):
    super().hide_event()
    self.close()

  def close(self):
    if self._closed:
      return
    self._closed = True
    try:
      if self._session is not None:
        self._session.stop()
    finally:
      ui_state.remove_offroad_transition_callback(self._offroad_transition)
      device.remove_interactive_timeout_callback(self._cancel)
      super().close()

  def _cancel(self):
    if not self._closed and gui_app.get_active_widget() is self:
      gui_app.pop_widget()

  def _offroad_transition(self):
    if not self._closed and ui_state.is_onroad():
      self._cancel()

  def _handle_mouse_release(self, _):
    super()._handle_mouse_release(_)
    self._cancel()

  def _scan_frame(self) -> None:
    if self.frame is None or self._closed or self._decoder is None:
      return

    now = time.monotonic()
    if now - self._last_scan < self.SCAN_INTERVAL:
      return
    self._last_scan = now

    try:
      # The cabin stream is NV12. QR decoding only needs its full-resolution Y plane.
      luminance = np.frombuffer(self.frame.data, dtype=np.uint8, count=self.frame.uv_offset)
      luminance = luminance.reshape((-1, self.frame.stride))[:self.frame.height, :self.frame.width]
      results = self._decoder.read_barcodes(luminance, formats=self._decoder.BarcodeFormat.QRCode,
                                           try_rotate=True, try_downscale=True, try_invert=True)
    except (BufferError, TypeError, ValueError, RuntimeError):
      self._status = tr("Unable to decode camera frame. Close and retry.")
      return

    self._status = tr("No QR detected. Adjust distance and screen brightness.")
    for result in results:
      try:
        param, token = decode_mapbox_qr_payload(result.text)
      except ValueError:
        self._status = tr("This is not a sunnypilot Mapbox QR code")
        continue

      try:
        ui_state.params.put(param, token, block=True)
      except (OSError, RuntimeError):
        self._status = tr("Unable to save token. Close and retry.")
        return
      token_type = tr("Public") if param == "MapboxPublicKey" else tr("Secret")
      self._cancel()
      gui_app.push_widget(alert_dialog(tr("Mapbox %s token saved") % token_type))
      return

  def _render(self, rect: rl.Rectangle) -> int:
    if self._closed:
      return -1
    if ui_state.is_onroad() or (self._session.active and not self._session.update(ui_state.is_onroad(), ui_state.ignition)):
      self._cancel()
      return -1
    if self._decoder is not None:
      super()._render(rect)
      if self.frame is None:
        self._status = tr("Camera starting. Tap anywhere to cancel.")
      self._scan_frame()
      if self._closed:
        return -1
    else:
      rl.draw_rectangle_rec(rect, rl.BLACK)

    guide_size = min(rect.width * 0.58, rect.height * 0.64)
    guide = rl.Rectangle(rect.x + (rect.width - guide_size) / 2,
                         rect.y + (rect.height - guide_size) / 2,
                         guide_size, guide_size)
    rl.draw_rectangle_rounded_lines_ex(guide, 0.06, 12, 9, rl.Color(71, 201, 255, 255))
    gui_label(rl.Rectangle(rect.x + 40, rect.y + 35, rect.width - 80, 90),
              tr("Scan Mapbox Token QR"), font_size=58, font_weight=FontWeight.BOLD,
              alignment=TextAlignment.CENTER)
    footer = rl.Rectangle(rect.x, rect.y + rect.height - 160, rect.width, 160)
    rl.draw_rectangle_rec(footer, rl.Color(0, 0, 0, 210))
    gui_label(rl.Rectangle(rect.x + 40, footer.y, rect.width - 80, 80),
              self._status, font_size=36, alignment=TextAlignment.CENTER)
    gui_label(rl.Rectangle(rect.x + 40, footer.y + 80, rect.width - 80, 65),
              tr("IR pauses during scanning. Tap anywhere to cancel.") if self._session.active else tr("Tap anywhere to cancel."),
              font_size=32, alignment=TextAlignment.CENTER)
    return -1
