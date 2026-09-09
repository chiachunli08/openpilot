from __future__ import annotations

from dataclasses import dataclass
import math

from openpilot.cereal import log, messaging


MAX_INSTRUCTION_AGE = 2.5

TURN_TYPES = {
  "turn", "end of road", "roundabout", "rotary", "roundabout turn",
  "exit roundabout", "exit rotary",
}
KEEP_TYPES = {"continue", "fork", "merge", "on ramp", "off ramp", "new name"}
LANE_CHANGE_TYPES = {"lane change", "lanechange"}
LEFT_MODIFIERS = {"left", "slight left", "sharp left"}
RIGHT_MODIFIERS = {"right", "slight right", "sharp right"}


def _normalize(value: str) -> str:
  return " ".join((value or "").strip().lower().replace("_", " ").replace("-", " ").split())


@dataclass(frozen=True)
class ManeuverIntent:
  desire: int
  category: str


@dataclass(frozen=True)
class NavigationIntentResult:
  desire: int
  pulse_sent: bool
  navigation_valid: bool
  maneuver_id: str
  maneuver_type: str
  maneuver_modifier: str
  reason: str
  trigger_distance: float
  instruction_age_sec: float


def classify_maneuver(maneuver_type: str, maneuver_modifier: str, is_rhd: bool = False) -> ManeuverIntent | None:
  """Map a Mapbox maneuver to an existing model desire using exact type/modifier groups.

  A ramp or fork is deliberately mapped to keepLeft/keepRight rather than a turn,
  and a turn-signal indication alone never enters this function.
  """
  maneuver_type = _normalize(maneuver_type)
  modifier = _normalize(maneuver_modifier)

  if modifier == "uturn":
    if maneuver_type not in TURN_TYPES:
      return None
    return ManeuverIntent(log.Desire.turnRight if is_rhd else log.Desire.turnLeft, "turn")

  if modifier in LEFT_MODIFIERS:
    side = "left"
  elif modifier in RIGHT_MODIFIERS:
    side = "right"
  else:
    return None

  if maneuver_type in LANE_CHANGE_TYPES:
    return ManeuverIntent(log.Desire.laneChangeLeft if side == "left" else log.Desire.laneChangeRight, "lane_change")
  if maneuver_type in KEEP_TYPES:
    return ManeuverIntent(log.Desire.keepLeft if side == "left" else log.Desire.keepRight, "keep")
  if maneuver_type in TURN_TYPES:
    return ManeuverIntent(log.Desire.turnLeft if side == "left" else log.Desire.turnRight, "turn")
  return None


def trigger_window(category: str, v_ego: float) -> tuple[float, float]:
  """Return a speed-scaled (minimum, maximum) trigger window in metres."""
  speed = max(0.0, float(v_ego))
  if category == "lane_change":
    return max(20.0, speed * 0.8), min(600.0, max(150.0, 100.0 + speed * 10.0))
  if category == "keep":
    return max(15.0, speed * 0.7), min(500.0, max(120.0, 80.0 + speed * 9.0))
  return max(5.0, speed * 0.45), min(240.0, max(55.0, 35.0 + speed * 5.0))


class NavigationIntentController:
  def __init__(self) -> None:
    self._last_maneuver_id = ""
    self._last_route_id = ""

  def reset(self) -> None:
    self._last_maneuver_id = ""
    self._last_route_id = ""

  def update(self, *, base_desire: int, enabled: bool, nav_valid: bool, nav,
             instruction_age_sec: float, v_ego: float, maneuver_id: str,
             route_id: str = "", driver_conflict: bool = False,
             driver_direction: str = "",
             is_rhd: bool = False) -> NavigationIntentResult:
    maneuver_type = str(getattr(nav, "maneuverType", "")) if nav is not None else ""
    modifier = str(getattr(nav, "maneuverModifier", "")) if nav is not None else ""
    distance = float(getattr(nav, "maneuverDistance", math.inf)) if nav is not None else math.inf
    age = max(0.0, float(instruction_age_sec))

    def result(desire: int, pulse: bool, valid: bool, reason: str, trigger_distance: float = 0.0) -> NavigationIntentResult:
      return NavigationIntentResult(int(desire), pulse, valid, maneuver_id, maneuver_type, modifier,
                                    reason, float(trigger_distance), age)

    if not enabled:
      return result(base_desire, False, False, "disabled")
    if not nav_valid or nav is None or age > MAX_INSTRUCTION_AGE:
      if not maneuver_id:
        self.reset()
      if age > MAX_INSTRUCTION_AGE:
        reason = "staleInstruction"
      else:
        reason = "navigationInvalid"
      return result(base_desire, False, False, reason)
    if not maneuver_id:
      return result(base_desire, False, True, "missingManeuverId")

    classified = classify_maneuver(maneuver_type, modifier, is_rhd)
    if classified is None:
      return result(base_desire, False, True, "unsupportedManeuver")
    minimum, maximum = trigger_window(classified.category, v_ego)

    if base_desire != log.Desire.none:
      return result(base_desire, False, True, "existingDesire", maximum)
    desired_side = ("left" if classified.desire in (log.Desire.turnLeft, log.Desire.keepLeft, log.Desire.laneChangeLeft)
                    else "right")
    # A matching manually operated signal is allowed to coexist with the
    # model hint. An opposite signal, hazards, or steering override wins.
    if driver_conflict or driver_direction not in ("", desired_side):
      return result(base_desire, False, True, "driverInput", maximum)
    if not math.isfinite(distance) or distance < 0.0:
      return result(base_desire, False, True, "invalidDistance", maximum)
    if maneuver_id == self._last_maneuver_id:
      return result(base_desire, False, True, "alreadySent", maximum)
    if distance > maximum:
      return result(base_desire, False, True, "awaitingTrigger", maximum)
    if distance < minimum:
      return result(base_desire, False, True, "tooClose", maximum)

    self._last_maneuver_id = maneuver_id
    self._last_route_id = route_id
    return result(classified.desire, True, True, "sent", maximum)


def publish_intent_state(pm, intent: NavigationIntentResult, runner: str, *, enabled: bool,
                         nav_features_compatible: bool = False,
                         nav_features_available: bool = False,
                         nav_features_fused: bool = False) -> None:
  msg = messaging.new_message("navigationIntentStateSP")
  state = msg.navigationIntentStateSP
  state.enabled = enabled
  state.navigationValid = intent.navigation_valid
  state.pulseSent = intent.pulse_sent
  state.desire = intent.desire
  state.maneuverId = intent.maneuver_id
  state.maneuverType = intent.maneuver_type
  state.maneuverModifier = intent.maneuver_modifier
  state.modelRunner = runner
  state.reason = intent.reason
  state.triggerDistance = intent.trigger_distance
  state.instructionAgeSec = intent.instruction_age_sec
  state.navFeaturesCompatible = nav_features_compatible
  state.navFeaturesAvailable = nav_features_available
  state.navFeaturesFused = nav_features_fused
  msg.valid = True
  pm.send("navigationIntentStateSP", msg)
