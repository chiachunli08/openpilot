"""Unclassified radar markers. Group mounting is experimental; columns are not lateral coordinates."""
import math
from dataclasses import dataclass

MAX_DISPLAY_AGE_SEC = 0.35
MAX_DISPLAY_DISTANCE_M = 120.0
MAX_TARGETS_PER_GROUP = 3
GROUP_POSITIONS = {0: (-1, 0), 1: (1, 0), 2: (-1, 1), 3: (1, 1)}


@dataclass(frozen=True)
class DisplayCornerTarget:
  sensor_group: int
  source_bus: int
  track_id: int
  distance_m: float


def select_display_targets(targets, message_age: float = 0.0) -> list[DisplayCornerTarget]:
  if not math.isfinite(message_age) or not 0 <= message_age <= MAX_DISPLAY_AGE_SEC:
    return []
  groups: dict[int, list[DisplayCornerTarget]] = {group: [] for group in GROUP_POSITIONS}
  for target in targets:
    group, bus = int(target.sensorGroup), int(target.sourceBus)
    distance, age = float(target.distance), float(target.ageSec) + message_age
    if (group not in groups or not 0 <= bus < 128 or not target.candidateActive or
        not math.isfinite(distance) or not 0 < distance <= MAX_DISPLAY_DISTANCE_M or
        not math.isfinite(age) or not 0 <= age <= MAX_DISPLAY_AGE_SEC):
      continue
    groups[group].append(DisplayCornerTarget(group, bus, int(target.trackId), distance))
  return [target for group in groups.values()
          for target in sorted(group, key=lambda t: (t.distance_m, t.source_bus, t.track_id))[:MAX_TARGETS_PER_GROUP]]


def panel_bounds(x: float, width: float, side: int) -> tuple[float, float] | None:
  # Reserve speed and standard blind-spot widgets (+/-230 plus 20 clearance),
  # and mici edge blind-spot icons (148 including clearance).
  panel_width = min(150.0, width / 2 - 250 - 148)
  if panel_width < 72:
    return None
  center = x + width / 2
  return (center - 250 - panel_width if side < 0 else center + 250, panel_width)


def marker_position(target: DisplayCornerTarget, column: int, x: float, width: float) -> tuple[float, float] | None:
  side, rear = GROUP_POSITIONS[target.sensor_group]
  bounds = panel_bounds(x, width, side)
  if bounds is None:
    return None
  left, panel_width = bounds
  offset = 18 + 65 * min(target.distance_m / MAX_DISPLAY_DISTANCE_M, 1.0)
  return left + panel_width * (column + 0.5) / MAX_TARGETS_PER_GROUP, 180 + (offset if rear else -offset)
