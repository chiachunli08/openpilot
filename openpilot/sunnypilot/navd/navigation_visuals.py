from __future__ import annotations

from datetime import datetime, timedelta
import math


def normalize_maneuver(value: str) -> str:
  return " ".join((value or "").strip().lower().replace("_", " ").replace("-", " ").split())


def maneuver_side(maneuver_modifier: str) -> str | None:
  modifier = normalize_maneuver(maneuver_modifier)
  if modifier in ("left", "slight left", "sharp left"):
    return "left"
  if modifier in ("right", "slight right", "sharp right"):
    return "right"
  return None


def maneuver_symbol(maneuver_type: str, maneuver_modifier: str) -> str:
  maneuver_type = normalize_maneuver(maneuver_type)
  modifier = normalize_maneuver(maneuver_modifier)
  side = maneuver_side(modifier)
  if maneuver_type in ("arrive", "destination"):
    return "⚑"
  if "roundabout" in maneuver_type or "rotary" in maneuver_type:
    return "↶" if side == "left" else ("↷" if side == "right" else "↻")
  if modifier == "uturn":
    return "↩"
  if side == "left":
    return "↖" if maneuver_type in ("fork", "merge", "on ramp", "off ramp", "continue") else "←"
  if side == "right":
    return "↗" if maneuver_type in ("fork", "merge", "on ramp", "off ramp", "continue") else "→"
  return "↑"


def should_suggest_signal(maneuver_type: str, maneuver_modifier: str) -> str | None:
  maneuver_type = normalize_maneuver(maneuver_type)
  side = maneuver_side(maneuver_modifier)
  if side and maneuver_type in ("turn", "end of road", "lane change", "lanechange", "off ramp"):
    return side
  return None


def format_distance(meters: float) -> str:
  if not math.isfinite(meters):
    return "—"
  meters = max(0.0, meters)
  if meters >= 1000:
    return f"{meters / 1000:.1f} km"
  return f"{round(meters / 10) * 10:.0f} m"


def format_eta(seconds: float, now: float | None = None) -> str:
  if not math.isfinite(seconds) or seconds < 0:
    return "—"
  base = datetime.now().astimezone() if now is None else datetime.fromtimestamp(now).astimezone()
  return (base + timedelta(seconds=seconds)).strftime("%H:%M")
