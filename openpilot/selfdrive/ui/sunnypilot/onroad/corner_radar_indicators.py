"""Independent radar target panels beside the speedometer; no control output."""
import time

import pyray as rl

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.selfdrive.ui.sunnypilot.onroad.corner_radar_layout import (
  GROUP_POSITIONS, marker_position, panel_bounds, select_display_targets,
)
from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.lib.text_measure import measure_text_cached


class CornerRadarIndicators:
  def __init__(self):
    self._font = gui_app.font(FontWeight.SEMI_BOLD)

  def update(self) -> None:
    # Select at render time so a frozen message cannot leave stale dots.
    pass

  def render(self, rect: rl.Rectangle) -> None:
    sm = ui_state.sm
    service = "cornerRadarStateSP"
    if (not ui_state.hkg_corner_radar or not sm.valid[service] or not sm.alive[service] or
        sm.recv_frame[service] <= ui_state.started_frame):
      return
    targets = select_display_targets(sm[service].targets, time.monotonic() - sm.recv_time[service])
    if not targets:
      return

    yellow = rl.Color(255, 193, 7, 235)
    for side in (-1, 1):
      side_targets = [t for t in targets if GROUP_POSITIONS[t.sensor_group][0] == side]
      bounds = panel_bounds(rect.x, rect.width, side)
      if not side_targets or bounds is None:
        continue
      x, width = bounds
      # Follow the speed renderer's absolute y=180 anchor on both UI sizes.
      rl.draw_rectangle_rounded(rl.Rectangle(x, 62, width, 242), 0.15, 6, rl.Color(0, 0, 0, 100))
      for label, y in (("RADAR*", 67), (f"~{min(t.distance_m for t in side_targets):.1f} m", 277)):
        size = min(22.0, width / 4)
        measured = measure_text_cached(self._font, label, size)
        rl.draw_text_ex(self._font, label, rl.Vector2(x + (width - measured.x) / 2, y), size, 0, yellow)

    columns = dict.fromkeys(GROUP_POSITIONS, 0)
    for target in targets:
      position = marker_position(target, columns[target.sensor_group], rect.x, rect.width)
      columns[target.sensor_group] += 1
      if position is None:
        continue
      x, y = position
      radius = max(5.0, 10.0 - target.distance_m / 24)
      rl.draw_circle_v(rl.Vector2(x, y), radius + 2, rl.Color(0, 0, 0, 200))
      rl.draw_circle_v(rl.Vector2(x, y), radius, yellow)
