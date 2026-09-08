import pyray as rl

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.lib.text_measure import measure_text_cached


class NavigationInstructionRenderer:
  def __init__(self):
    self._font = gui_app.font(FontWeight.MEDIUM)

  @staticmethod
  def _distance(meters: float) -> str:
    if meters >= 1000:
      return f"{meters / 1000:.1f} km"
    return f"{max(0, round(meters / 10) * 10):.0f} m"

  def render(self, rect: rl.Rectangle) -> None:
    if not ui_state.params.get_bool("NavigationEnabled") or not ui_state.sm.valid["navInstruction"]:
      return
    nav = ui_state.sm["navInstruction"]
    modifier = nav.maneuverModifier.lower()
    if "left" in modifier:
      arrow, signal = "←", tr("Use left turn signal when safe")
    elif "right" in modifier:
      arrow, signal = "→", tr("Use right turn signal when safe")
    else:
      arrow, signal = "↑", ""

    width, height = 760, 175
    card = rl.Rectangle(rect.x + (rect.width - width) / 2, rect.y + 35, width, height)
    rl.draw_rectangle_rounded(card, 0.18, 10, rl.Color(0, 0, 0, 205))
    rl.draw_rectangle_rounded_lines_ex(card, 0.18, 10, 3, rl.Color(255, 255, 255, 80))
    rl.draw_text_ex(self._font, arrow, rl.Vector2(card.x + 30, card.y + 28), 90, 0, rl.WHITE)
    title = nav.maneuverPrimaryText or tr("Continue on route")
    rl.draw_text_ex(self._font, title, rl.Vector2(card.x + 145, card.y + 25), 48, 0, rl.WHITE)
    detail = self._distance(nav.maneuverDistance)
    if signal:
      detail += f"  ·  {signal}"
    size = measure_text_cached(self._font, detail, 34)
    font_size = 34 if size.x < width - 175 else 28
    rl.draw_text_ex(self._font, detail, rl.Vector2(card.x + 145, card.y + 100), font_size, 0, rl.Color(210, 210, 210, 255))
