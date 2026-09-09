"""Experimental display for passively received HKG corner-radar candidates."""
from __future__ import annotations

import math
from dataclasses import dataclass

import pyray as rl

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.lib.text_measure import measure_text_cached

MAX_DISPLAY_AGE_SEC = 0.35
MAX_DISPLAY_DISTANCE_M = 120.0
GROUP_POSITIONS = {
  0: (-1, 0),  # experimental PR mapping: left/front
  1: (1, 0),   # experimental PR mapping: right/front
  2: (-1, 1),  # experimental PR mapping: left/rear
  3: (1, 1),   # experimental PR mapping: right/rear
}


@dataclass(frozen=True)
class DisplayCornerTarget:
  sensor_group: int
  source_bus: int
  distance_m: float
  corrected_angle_deg: float
  estimated_radial_speed_mps: float | None


def select_display_targets(targets) -> dict[int, DisplayCornerTarget]:
  """Keep the nearest fresh candidate in each unverified sensor group."""
  selected: dict[int, DisplayCornerTarget] = {}
  for target in targets:
    group = int(target.sensorGroup)
    source_bus = int(target.sourceBus)
    distance = float(target.distance)
    angle = float(target.correctedAngle)
    age = float(target.ageSec)
    if (group not in GROUP_POSITIONS or not bool(target.candidateActive) or
        not math.isfinite(distance) or not 0.0 < distance <= MAX_DISPLAY_DISTANCE_M or
        not math.isfinite(angle) or not 0.0 <= age <= MAX_DISPLAY_AGE_SEC):
      continue

    speed = None
    if bool(target.estimatedRadialSpeedValid):
      candidate_speed = float(target.estimatedRadialSpeed)
      speed = candidate_speed if math.isfinite(candidate_speed) else None

    display = DisplayCornerTarget(group, source_bus, distance, angle, speed)
    if group not in selected or distance < selected[group].distance_m:
      selected[group] = display
  return selected


class CornerRadarIndicators:
  def __init__(self):
    self._font = gui_app.font(FontWeight.SEMI_BOLD)
    self._targets: dict[int, DisplayCornerTarget] = {}

  def update(self) -> None:
    sm = ui_state.sm
    service = "cornerRadarStateSP"
    if (not ui_state.hkg_corner_radar or not sm.valid[service] or not sm.alive[service] or
        sm.recv_frame[service] <= ui_state.started_frame):
      self._targets = {}
      return
    self._targets = select_display_targets(sm[service].targets)

  @staticmethod
  def _triangle(center_x: float, center_y: float, size: float, side: int, color: rl.Color) -> None:
    half = size / 2.0
    if side < 0:
      tip = rl.Vector2(center_x + half, center_y)
      upper = rl.Vector2(center_x - half, center_y - half)
      lower = rl.Vector2(center_x - half, center_y + half)
      rl.draw_triangle(tip, lower, upper, color)
    else:
      tip = rl.Vector2(center_x - half, center_y)
      upper = rl.Vector2(center_x + half, center_y - half)
      lower = rl.Vector2(center_x + half, center_y + half)
      rl.draw_triangle(tip, upper, lower, color)

  def render(self, rect: rl.Rectangle) -> None:
    if not ui_state.hkg_corner_radar:
      return

    center_x = rect.x + rect.width / 2.0
    for group, target in self._targets.items():
      side, row = GROUP_POSITIONS[group]
      x = center_x + side * 315
      y = rect.y + 205 + row * 145
      size = max(28.0, min(58.0, 58.0 - target.distance_m * 0.6))
      alpha = int(max(120.0, min(245.0, 255.0 - target.distance_m * 2.0)))
      self._triangle(x + 3, y + 3, size, side, rl.Color(0, 0, 0, min(alpha, 180)))
      self._triangle(x, y, size, side, rl.Color(255, 193, 7, alpha))

      labels = [f"B{target.source_bus} G{group}  {target.distance_m:.1f} m  {target.corrected_angle_deg:.0f}°"]
      if target.estimated_radial_speed_mps is not None:
        labels.append(f"~vr {target.estimated_radial_speed_mps:+.1f} m/s")
      font_size = 24
      for line, label in enumerate(labels):
        measured = measure_text_cached(self._font, label, font_size)
        text_x = x - measured.x / 2.0
        text_y = y + size / 2.0 + 7 + line * 27
        rl.draw_text_ex(self._font, label, rl.Vector2(text_x + 2, text_y + 2), font_size, 0,
                        rl.Color(0, 0, 0, min(alpha, 190)))
        rl.draw_text_ex(self._font, label, rl.Vector2(text_x, text_y), font_size, 0,
                        rl.Color(255, 214, 64, alpha))
