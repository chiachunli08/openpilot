"""Display-only traffic-signal indicator fed by the optional YOLO visual detector."""

import json
from pathlib import Path
import time

import pyray as rl

from openpilot.sunnypilot.modeld_v2.traffic_signal_settings import is_enabled
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.multilang import multilang
from openpilot.system.ui.lib.text_measure import measure_text_cached

STATE_PATH = Path("/dev/shm/sunnypilot_traffic_signal_yolo.json")
STATE_TTL_S = 1.5

LABELS = {
  "green": ("GREEN", "綠燈"),
  "left-green": ("LEFT", "左轉"),
  "left-red": ("LEFT", "左轉"),
  "left-yellow": ("LEFT", "左轉"),
  "red": ("RED", "紅燈"),
  "yellow": ("YELLOW", "黃燈"),
}


class TrafficSignalIndicator:
  def __init__(self):
    self._state = None
    self._last_read = 0.0
    self._font = gui_app.font(FontWeight.BOLD)

  def update(self) -> None:
    now = time.monotonic()
    if now - self._last_read < 0.15:
      return
    self._last_read = now
    self._state = None
    if not is_enabled():
      return
    try:
      state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
      age = now - float(state.get("monotonic", 0.0))
      if 0.0 <= age <= STATE_TTL_S and state.get("active"):
        self._state = state
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
      self._state = None

  @staticmethod
  def _signal_color(signal: str) -> rl.Color:
    if signal in ("green", "left-green"):
      return rl.Color(0, 230, 80, 255)
    if signal in ("yellow", "left-yellow"):
      return rl.Color(255, 195, 0, 255)
    return rl.Color(255, 55, 55, 255)

  @staticmethod
  def _draw_left_arrow(center: rl.Vector2, color: rl.Color) -> None:
    rl.draw_line_ex(rl.Vector2(center.x + 20, center.y), rl.Vector2(center.x - 20, center.y), 7, color)
    rl.draw_line_ex(rl.Vector2(center.x - 20, center.y), rl.Vector2(center.x - 4, center.y - 15), 7, color)
    rl.draw_line_ex(rl.Vector2(center.x - 20, center.y), rl.Vector2(center.x - 4, center.y + 15), 7, color)

  def render(self, rect: rl.Rectangle) -> None:
    self.update()
    if self._state is None:
      return

    signal = str(self._state.get("signal", ""))
    confidence = float(self._state.get("confidence", 0.0))
    if signal not in LABELS:
      return

    # Positioned directly below the Experimental Mode button in the upper-right HUD area.
    box_w, box_h = 150, 190
    x = rect.x + rect.width - 30 - box_w
    y = rect.y + 30 + 192 + 24
    box = rl.Rectangle(x, y, box_w, box_h)
    rl.draw_rectangle_rounded(box, 0.24, 12, rl.Color(0, 0, 0, 205))
    rl.draw_rectangle_rounded_lines_ex(box, 0.24, 12, 3, rl.Color(255, 255, 255, 65))

    color = self._signal_color(signal)
    center = rl.Vector2(x + box_w / 2, y + 72)
    rl.draw_circle_v(center, 38, rl.Color(25, 25, 25, 255))
    rl.draw_circle_v(center, 29, color)
    if signal.startswith("left-"):
      self._draw_left_arrow(center, rl.Color(15, 15, 15, 235))

    label = LABELS[signal][1] if multilang.language == "zh-CHT" else LABELS[signal][0]
    label_size = measure_text_cached(self._font, label, 30)
    rl.draw_text_ex(self._font, label, rl.Vector2(x + (box_w - label_size.x) / 2, y + 120), 30, 0, rl.WHITE)

    conf_text = f"{round(confidence * 100)}%"
    conf_size = measure_text_cached(self._font, conf_text, 24)
    rl.draw_text_ex(self._font, conf_text, rl.Vector2(x + (box_w - conf_size.x) / 2, y + 156), 24, 0, rl.Color(210, 210, 210, 220))
