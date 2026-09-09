from __future__ import annotations

from dataclasses import dataclass
import time

import numpy as np

from openpilot.sunnypilot.navd.navigation_intent import NavigationIntentController, NavigationIntentResult, publish_intent_state
from openpilot.sunnypilot.navd.navigation_model_compat import NAV_FEATURE_LEN, navigation_feature_key


@dataclass(frozen=True)
class NavigationBridgeResult:
  desire: int
  intent: NavigationIntentResult
  feature_key: str | None
  features: np.ndarray | None
  compatible: bool
  available: bool
  fused: bool


class NavigationModelBridge:
  """One navigation/desire implementation shared by stock modeld and modeld_v2."""

  def __init__(self, params, runner: str) -> None:
    self.params = params
    self.runner = runner
    self.intent_controller = NavigationIntentController()
    self._last_compatible: bool | None = None
    self._last_fused: bool | None = None

  def _put_state_param(self, key: str, value: bool, previous: bool | None) -> bool:
    if previous is None or previous != value:
      self.params.put_bool(key, value)
    return value

  @staticmethod
  def _valid(sm, service: str, max_age: float = 2.5) -> bool:
    return bool(sm.valid[service] and sm.alive[service] and
                0 <= time.monotonic() - sm.recv_time[service] <= max_age)

  def update(self, *, sm, pm, base_desire: int, v_ego: float, is_rhd: bool,
             model_inputs: dict[str, np.ndarray], navigation_feature_contract: str = "") -> NavigationBridgeResult:
    nav_fresh = self._valid(sm, "navInstruction")
    state_fresh = self._valid(sm, "navigationStateSP")
    navigation_state = sm["navigationStateSP"] if state_fresh else None
    nav_valid = bool(nav_fresh and navigation_state is not None and navigation_state.instructionValid)
    nav = sm["navInstruction"] if nav_fresh else None
    route_id = str(navigation_state.routeId) if navigation_state is not None else ""
    maneuver_id = str(navigation_state.maneuverId) if navigation_state is not None else ""
    instruction_age = max(0.0, time.monotonic() - sm.recv_time["navInstruction"]) if nav_fresh else float("inf")
    car_state = sm["carState"]
    driver_conflict = bool(car_state.steeringPressed)
    if car_state.leftBlinker and car_state.rightBlinker:
      driver_direction = "both"
    elif car_state.leftBlinker:
      driver_direction = "left"
    elif car_state.rightBlinker:
      driver_direction = "right"
    else:
      driver_direction = ""
    enabled = self.params.get_bool("NavigationIntentEnabled")
    intent = self.intent_controller.update(base_desire=base_desire, enabled=enabled, nav_valid=nav_valid, nav=nav,
                                           instruction_age_sec=instruction_age, v_ego=v_ego, maneuver_id=maneuver_id,
                                           route_id=route_id, driver_conflict=driver_conflict,
                                           driver_direction=driver_direction, is_rhd=is_rhd)

    input_shapes = {key: value.shape for key, value in model_inputs.items()}
    feature_key = navigation_feature_key(input_shapes, navigation_feature_contract)
    compatible = feature_key is not None
    self._last_compatible = self._put_state_param("NavigationModelFusionCompatible", compatible, self._last_compatible)

    model_state_fresh = self._valid(sm, "navigationModelStateSP")
    model_state = sm["navigationModelStateSP"] if model_state_fresh else None
    feature_values = (np.asarray(model_state.features, dtype=np.float32)
                      if model_state is not None and len(model_state.features) == NAV_FEATURE_LEN else None)
    available = bool(model_state is not None and model_state.featuresValid and
                     feature_values is not None and np.all(np.isfinite(feature_values)) and
                     route_id and model_state.routeId == route_id)
    fusion_requested = self.params.get_bool("NavigationModelFusionEnabled")
    fused = bool(fusion_requested and compatible and available)
    features = None
    if fused and feature_key is not None and feature_values is not None:
      features = feature_values.reshape(model_inputs[feature_key].shape)
    self._last_fused = self._put_state_param("NavigationModelFusionActive", fused, self._last_fused)

    publish_intent_state(pm, intent, self.runner, enabled=enabled,
                         nav_features_compatible=compatible, nav_features_available=available,
                         nav_features_fused=fused)
    return NavigationBridgeResult(intent.desire, intent, feature_key, features, compatible, available, fused)
