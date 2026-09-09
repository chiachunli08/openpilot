from __future__ import annotations

from pathlib import Path
import time

import pyray as rl

from openpilot.common.hardware.hw import Paths
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.sunnypilot.navd.mapbox_mapd import display_map_supported
from openpilot.sunnypilot.navd.navigation_visuals import format_distance, format_eta, maneuver_symbol
from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.widgets import Widget

MAP_STATE_MAX_AGE = 2.5


class MapboxNavigationRenderer(Widget):
  """Interactive C3X-only map panel backed by mapbox_mapd PNG frames."""

  def __init__(self) -> None:
    super().__init__()
    self.supported = display_map_supported()
    self.expanded = False
    self._generation = -1
    self._texture = None
    self._font = gui_app.font(FontWeight.MEDIUM)
    self._font_bold = gui_app.font(FontWeight.BOLD)
    self.set_click_callback(self._toggle_expanded)

  def _toggle_expanded(self) -> None:
    self.expanded = not self.expanded

  @property
  def desired_size(self) -> tuple[int, int]:
    return (900, 760) if self.expanded else (510, 510)

  def _state_fresh(self) -> bool:
    service = "mapboxNavigationStateSP"
    return bool(ui_state.sm.valid[service] and ui_state.sm.alive[service] and
                0 <= time.monotonic() - ui_state.sm.recv_time[service] <= MAP_STATE_MAX_AGE)

  def _update_state(self) -> None:
    if not self.supported or not self._state_fresh():
      return
    state = ui_state.sm["mapboxNavigationStateSP"]
    if not state.displayImageValid or state.generation == self._generation:
      return
    path = Path(str(state.displayImagePath))
    expected_root = Path(Paths.mapbox_navigation_shm_root()).resolve()
    try:
      if path.resolve().parent != expected_root or not path.is_file():
        return
      texture = rl.load_texture(str(path))
      if not rl.is_texture_valid(texture):
        return
      if self._texture is not None and rl.is_texture_valid(self._texture):
        rl.unload_texture(self._texture)
      self._texture = texture
      self._generation = state.generation
    except OSError:
      return

  def _render(self, rect: rl.Rectangle) -> None:
    if not self.supported or not ui_state.params.get_bool("NavigationEnabled") or not ui_state.params.get_bool("MapboxMapDisplayEnabled"):
      return
    rl.draw_rectangle_rounded(rect, 0.07, 12, rl.Color(4, 8, 13, 235))
    rl.draw_rectangle_rounded_lines_ex(rect, 0.07, 12, 3, rl.Color(255, 255, 255, 75))

    state_fresh = self._state_fresh()
    state = ui_state.sm["mapboxNavigationStateSP"] if state_fresh else None
    if state is not None and state.displayImageValid and self._texture is not None and rl.is_texture_valid(self._texture):
      top_height = 132 if self.expanded else 105
      bottom_height = 66 if self.expanded else 48
      map_rect = rl.Rectangle(rect.x + 4, rect.y + top_height, rect.width - 8, rect.height - top_height - bottom_height)
      source = rl.Rectangle(0, 0, self._texture.width, self._texture.height)
      rl.draw_texture_pro(self._texture, source, map_rect, rl.Vector2(0, 0), 0, rl.WHITE)
    else:
      status = tr("Map loading") if state_fresh else tr("Map data unavailable")
      rl.draw_text_ex(self._font, status, rl.Vector2(rect.x + 28, rect.y + rect.height / 2 - 20), 34, 0,
                      rl.Color(220, 220, 220, 255))

    nav_valid = (ui_state.params.get_bool("NavigationTurnPromptEnabled") and
                 ui_state.sm.valid["navInstruction"] and ui_state.sm.alive["navInstruction"] and
                 ui_state.sm.valid["navigationStateSP"] and ui_state.sm.alive["navigationStateSP"] and
                 ui_state.sm["navigationStateSP"].instructionValid and
                 0 <= time.monotonic() - ui_state.sm.recv_time["navInstruction"] <= MAP_STATE_MAX_AGE and
                 0 <= time.monotonic() - ui_state.sm.recv_time["navigationStateSP"] <= MAP_STATE_MAX_AGE)
    if nav_valid:
      nav = ui_state.sm["navInstruction"]
      symbol = maneuver_symbol(nav.maneuverType, nav.maneuverModifier)
      primary = nav.maneuverPrimaryText or tr("Continue on route")
      rl.draw_text_ex(self._font_bold, symbol, rl.Vector2(rect.x + 20, rect.y + 13), 58 if self.expanded else 46, 0, rl.WHITE)
      rl.draw_text_ex(self._font_bold, primary, rl.Vector2(rect.x + 88, rect.y + 16), 36 if self.expanded else 27, 0, rl.WHITE)
      secondary = nav.maneuverSecondaryText or ""
      if secondary:
        rl.draw_text_ex(self._font, secondary, rl.Vector2(rect.x + 90, rect.y + (57 if self.expanded else 49)),
                        25 if self.expanded else 19, 0, rl.Color(210, 210, 210, 255))
      distance_y = 94 if self.expanded else 76
      rl.draw_text_ex(self._font, format_distance(nav.maneuverDistance), rl.Vector2(rect.x + 90, rect.y + distance_y),
                      27 if self.expanded else 21, 0, rl.Color(82, 195, 255, 255))
      summary = f"{format_distance(nav.distanceRemaining)}  ·  {tr('ETA')} {format_eta(nav.timeRemaining)}"
      rl.draw_text_ex(self._font, summary, rl.Vector2(rect.x + 22, rect.y + rect.height - (49 if self.expanded else 37)),
                      27 if self.expanded else 21, 0, rl.Color(225, 225, 225, 255))

    mode = tr("COLLAPSE") if self.expanded else tr("EXPAND")
    rl.draw_text_ex(self._font, mode, rl.Vector2(rect.x + rect.width - (145 if self.expanded else 110), rect.y + 20),
                    22 if self.expanded else 18, 0, rl.Color(190, 190, 190, 255))
    # Required attribution remains readable in both panel sizes.
    rl.draw_text_ex(self._font, "© Mapbox · © OpenStreetMap", rl.Vector2(rect.x + 18, rect.y + rect.height - 20),
                    13, 0, rl.Color(215, 215, 215, 230))

  def hide_event(self) -> None:
    if self._texture is not None and rl.is_texture_valid(self._texture):
      rl.unload_texture(self._texture)
    self._texture = None
    self._generation = -1
    super().hide_event()
