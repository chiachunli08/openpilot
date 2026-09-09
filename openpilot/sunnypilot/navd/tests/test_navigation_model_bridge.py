from types import SimpleNamespace as NS
import time

import numpy as np

from openpilot.cereal import log
from openpilot.sunnypilot.navd.navigation_model_bridge import NavigationModelBridge
from openpilot.sunnypilot.navd.navigation_model_compat import TACO2_NAV_FEATURE_CONTRACT


class FakeParams:
  def __init__(self, values=None):
    self.values = dict(values or {})

  def get_bool(self, key):
    return bool(self.values.get(key, False))

  def put_bool(self, key, value):
    self.values[key] = bool(value)


class FakePM:
  def __init__(self):
    self.sent = {}

  def send(self, service, message):
    self.sent[service] = message


class FakeSM:
  def __init__(self, *, features=True):
    now = time.monotonic()
    self.data = {
      "navInstruction": NS(maneuverType="turn", maneuverModifier="left", maneuverDistance=70.0),
      "navigationStateSP": NS(instructionValid=True, routeId="route", maneuverId="route:0"),
      "navigationModelStateSP": NS(featuresValid=features, routeId="route", features=[float(i) for i in range(64)]),
      "carState": NS(steeringPressed=False, leftBlinker=False, rightBlinker=False),
    }
    self.valid = {key: True for key in self.data}
    self.alive = {key: True for key in self.data}
    self.recv_time = {key: now for key in self.data}

  def __getitem__(self, key):
    return self.data[key]


def test_common_bridge_sends_turn_desire_without_model_fusion():
  params = FakeParams({"NavigationIntentEnabled": True})
  pm = FakePM()
  result = NavigationModelBridge(params, "stock").update(
    sm=FakeSM(), pm=pm, base_desire=log.Desire.none, v_ego=10.0, is_rhd=False,
    model_inputs={"desire": np.zeros(8, dtype=np.float32)})
  assert result.desire == log.Desire.turnLeft
  assert result.intent.pulse_sent
  assert not result.compatible and not result.fused
  assert pm.sent["navigationIntentStateSP"].navigationIntentStateSP.modelRunner == "stock"


def test_feature_fusion_requires_exact_input_and_matching_fresh_route():
  params = FakeParams({"NavigationIntentEnabled": True, "NavigationModelFusionEnabled": True})
  inputs = {"desire": np.zeros(8, dtype=np.float32), "nav_features": np.zeros((1, 64), dtype=np.float32)}
  result = NavigationModelBridge(params, "modeld_v2").update(
    sm=FakeSM(), pm=FakePM(), base_desire=log.Desire.none, v_ego=10.0, is_rhd=False, model_inputs=inputs,
    navigation_feature_contract=TACO2_NAV_FEATURE_CONTRACT)
  assert result.compatible and result.available and result.fused
  assert result.features.shape == (1, 64)
  assert params.values["NavigationModelFusionActive"]


def test_driver_input_has_priority_over_navigation():
  sm = FakeSM()
  sm.data["carState"].steeringPressed = True
  result = NavigationModelBridge(FakeParams({"NavigationIntentEnabled": True}), "stock").update(
    sm=sm, pm=FakePM(), base_desire=log.Desire.none, v_ego=10.0, is_rhd=False,
    model_inputs={"desire": np.zeros(8, dtype=np.float32)})
  assert result.desire == log.Desire.none
  assert result.intent.reason == "driverInput"


def test_feature_route_mismatch_deactivates_fusion_and_returns_no_stale_features():
  params = FakeParams({"NavigationIntentEnabled": True, "NavigationModelFusionEnabled": True})
  sm = FakeSM()
  sm.data["navigationModelStateSP"].routeId = "old-route"
  inputs = {"desire": np.zeros(8, dtype=np.float32), "nav_features": np.ones((1, 64), dtype=np.float32)}
  result = NavigationModelBridge(params, "modeld_v2").update(
    sm=sm, pm=FakePM(), base_desire=log.Desire.none, v_ego=10.0, is_rhd=False, model_inputs=inputs,
    navigation_feature_contract=TACO2_NAV_FEATURE_CONTRACT)
  assert result.compatible and not result.available and not result.fused
  assert result.features is None
  assert not params.values["NavigationModelFusionActive"]


def test_nonfinite_navigation_features_never_reach_driving_model():
  params = FakeParams({"NavigationModelFusionEnabled": True})
  sm = FakeSM()
  sm.data["navigationModelStateSP"].features[12] = float("nan")
  result = NavigationModelBridge(params, "modeld_v2").update(
    sm=sm, pm=FakePM(), base_desire=log.Desire.none, v_ego=10.0, is_rhd=False,
    model_inputs={"nav_features": np.zeros((1, 64), dtype=np.float32)},
    navigation_feature_contract=TACO2_NAV_FEATURE_CONTRACT)
  assert result.compatible and not result.available and not result.fused
  assert result.features is None
