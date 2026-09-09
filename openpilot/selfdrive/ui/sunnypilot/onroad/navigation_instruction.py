from __future__ import annotations

import time

import pyray as rl

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.sunnypilot.navd.mapbox_mapd import display_map_supported
from openpilot.sunnypilot.navd.navigation_visuals import (format_distance, format_eta, maneuver_symbol,
                                                          should_suggest_signal)
from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.lib.text_measure import measure_text_cached

INSTRUCTION_MAX_AGE = 2.5


class NavigationInstructionRenderer:
  def __init__(self):
    self._font = gui_app.font(FontWeight.MEDIUM)
    self._font_bold = gui_app.font(FontWeight.BOLD)
    self._map_display_supported = display_map_supported()

  @staticmethod
  def _fresh() -> bool:
    service = "navInstruction"
    state_service = "navigationStateSP"
    return bool(ui_state.sm.valid[service] and ui_state.sm.alive[service] and
                0 <= time.monotonic() - ui_state.sm.recv_time[service] <= INSTRUCTION_MAX_AGE and
                ui_state.sm.valid[state_service] and ui_state.sm.alive[state_service] and
                0 <= time.monotonic() - ui_state.sm.recv_time[state_service] <= INSTRUCTION_MAX_AGE and
                ui_state.sm[state_service].instructionValid)

  def render(self, rect: rl.Rectangle) -> None:
    if (not ui_state.params.get_bool("NavigationEnabled") or
        not ui_state.params.get_bool("NavigationTurnPromptEnabled") or
        (self._map_display_supported and ui_state.params.get_bool("MapboxMapDisplayEnabled")) or not self._fresh()):
      return
    nav = ui_state.sm["navInstruction"]
    arrow = maneuver_symbol(nav.maneuverType, nav.maneuverModifier)
    signal_side = should_suggest_signal(nav.maneuverType, nav.maneuverModifier)

    width, height = max(600, min(880, int(rect.width - 500))), 224
    card = rl.Rectangle(rect.x + (rect.width - width) / 2, rect.y + 30, width, height)
    rl.draw_rectangle_rounded(card, 0.16, 10, rl.Color(0, 0, 0, 215))
    rl.draw_rectangle_rounded_lines_ex(card, 0.16, 10, 3, rl.Color(255, 255, 255, 85))
    rl.draw_text_ex(self._font_bold, arrow, rl.Vector2(card.x + 28, card.y + 36), 92, 0, rl.WHITE)

    title = nav.maneuverPrimaryText or tr("Continue on route")
    title_size = 46
    while title_size > 30 and measure_text_cached(self._font_bold, title, title_size).x > width - 190:
      title_size -= 2
    rl.draw_text_ex(self._font_bold, title, rl.Vector2(card.x + 155, card.y + 24), title_size, 0, rl.WHITE)

    secondary = nav.maneuverSecondaryText or ""
    if secondary:
      secondary_size = 29
      while secondary_size > 22 and measure_text_cached(self._font, secondary, secondary_size).x > width - 190:
        secondary_size -= 1
      rl.draw_text_ex(self._font, secondary, rl.Vector2(card.x + 157, card.y + 77), secondary_size, 0,
                      rl.Color(210, 210, 210, 255))

    detail = format_distance(nav.maneuverDistance)
    if signal_side == "left":
      detail += f"  ·  {tr('Use left turn signal when safe')}"
    elif signal_side == "right":
      detail += f"  ·  {tr('Use right turn signal when safe')}"
    detail_size = 31
    while detail_size > 22 and measure_text_cached(self._font, detail, detail_size).x > width - 190:
      detail_size -= 1
    rl.draw_text_ex(self._font, detail, rl.Vector2(card.x + 157, card.y + 120), detail_size, 0,
                    rl.Color(82, 195, 255, 255))

    remaining = f"{tr('Remaining')} {format_distance(nav.distanceRemaining)}  ·  {tr('ETA')} {format_eta(nav.timeRemaining)}"
    rl.draw_text_ex(self._font, remaining, rl.Vector2(card.x + 157, card.y + 168), 26, 0,
                    rl.Color(225, 225, 225, 255))
