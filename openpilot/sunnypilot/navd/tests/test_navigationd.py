from types import SimpleNamespace as NS
import time
from unittest.mock import patch

import requests

from openpilot.cereal import log
from openpilot.sunnypilot.navd.navigationd import NavigationEngine


def route_steps():
  return [{
    "distance": 100.0,
    "duration": 20.0,
    "name": "Test Road",
    "maneuver": {"type": "turn", "modifier": "left", "instruction": "Turn left"},
    "geometry": {"coordinates": [[121.0, 25.0], [121.001, 25.0]]},
    "bannerInstructions": [],
  }]


class FakeParams:
  def __init__(self, values=None):
    self.values = dict(values or {})

  def get(self, key, **_kwargs):
    return self.values.get(key)

  def put(self, key, value, **_kwargs):
    self.values[key] = value

  def remove(self, key):
    self.values.pop(key, None)


class FakeSM:
  def __init__(self, *, valid_gps=True, network=True, longitude=121.0, stale_gps=False):
    self.data = {
      "gpsLocationExternal": NS(hasFix=valid_gps, latitude=25.0, longitude=longitude, bearingDeg=90.0),
      "deviceState": NS(networkType=(log.DeviceState.NetworkType.wifi if network else log.DeviceState.NetworkType.none)),
    }
    self.valid = {"gpsLocationExternal": valid_gps, "deviceState": True}
    self.alive = {"gpsLocationExternal": valid_gps, "deviceState": True}
    self.seen = {"gpsLocationExternal": True, "deviceState": True}
    now = time.monotonic()
    self.recv_time = {"gpsLocationExternal": now - (3.0 if stale_gps else 0.0), "deviceState": now}

  def __getitem__(self, key):
    return self.data[key]

  def update(self, _timeout):
    pass


class FakePM:
  def __init__(self):
    self.sent = {}

  def send(self, service, message):
    self.sent[service] = message


def cached_params(with_destination=True):
  values = {
    "NavigationRouteCache": route_steps(),
    "NavigationRouteDestination": {"latitude": 25.0, "longitude": 121.001},
    "NavigationRouteMetadata": {"routeId": "cached-route", "savedAt": 1.0},
  }
  if with_destination:
    values["NavDestination"] = {"latitude": 25.0, "longitude": 121.001}
  return FakeParams(values)


def test_canceled_destination_never_restores_cached_route():
  params = cached_params(with_destination=False)
  engine = NavigationEngine(sm=FakeSM(), pm=FakePM(), params=params)
  assert not engine.steps
  assert "NavigationRouteCache" not in params.values


def test_cached_route_survives_invalid_gps_but_instruction_is_cleared():
  pm = FakePM()
  engine = NavigationEngine(sm=FakeSM(valid_gps=False), pm=pm, params=cached_params())
  engine.update()
  assert pm.sent["navRoute"].valid
  assert not pm.sent["navInstruction"].valid
  assert pm.sent["navigationStateSP"].navigationStateSP.status == "waitingForLocation"


def test_stale_gps_never_keeps_guidance_alive():
  pm = FakePM()
  engine = NavigationEngine(sm=FakeSM(stale_gps=True), pm=pm, params=cached_params())
  engine.update()
  assert pm.sent["navRoute"].valid
  assert not pm.sent["navInstruction"].valid
  assert pm.sent["navigationStateSP"].navigationStateSP.status == "waitingForLocation"


def test_cached_route_guidance_continues_on_route_while_offline():
  pm = FakePM()
  engine = NavigationEngine(sm=FakeSM(network=False), pm=pm, params=cached_params())
  engine.update()
  assert pm.sent["navRoute"].valid
  assert pm.sent["navInstruction"].valid
  state = pm.sent["navigationStateSP"].navigationStateSP
  assert state.status == "cachedRoute"
  assert not state.networkAvailable


def test_off_route_failed_recalculation_clears_instruction_but_keeps_route_context():
  pm = FakePM()
  engine = NavigationEngine(sm=FakeSM(network=False, longitude=122.0), pm=pm, params=cached_params())
  engine.update()
  assert pm.sent["navRoute"].valid
  assert not pm.sent["navInstruction"].valid
  assert pm.sent["navigationStateSP"].navigationStateSP.status == "stale"


def test_arrival_clears_route_instruction_and_destination_immediately():
  pm = FakePM()
  params = cached_params()
  engine = NavigationEngine(sm=FakeSM(longitude=121.001), pm=pm, params=params)
  engine.update()
  assert not pm.sent["navRoute"].valid
  assert not pm.sent["navInstruction"].valid
  assert pm.sent["navigationStateSP"].navigationStateSP.status == "arrived"
  assert "NavDestination" not in params.values
  assert "NavigationRouteCache" not in params.values


def test_mapbox_step_fallback_supplies_visible_instruction():
  fields = NavigationEngine._instruction_fields(route_steps()[0], 75.0)
  assert fields["maneuverPrimaryText"] == "Turn left"
  assert fields["maneuverSecondaryText"] == "Test Road"
  assert fields["maneuverType"] == "turn"
  assert fields["maneuverModifier"] == "left"


def test_malformed_banner_falls_back_to_step_without_crashing():
  step = route_steps()[0]
  step["bannerInstructions"] = [{"unexpected": True}]
  fields = NavigationEngine._instruction_fields(step, 75.0)
  assert fields["maneuverPrimaryText"] == "Turn left"
  assert fields["maneuverType"] == "turn"


def test_request_failure_never_logs_token_bearing_exception():
  params = FakeParams({"MapboxPublicKey": "pk.secret-value", "LanguageSetting": "en"})
  engine = NavigationEngine(sm=FakeSM(), pm=FakePM(), params=params)
  engine.position = NS(longitude=121.0, latitude=25.0)
  engine.network_available = True
  destination = NS(longitude=121.1, latitude=25.1)
  with patch("openpilot.sunnypilot.navd.navigationd.requests.get",
             side_effect=requests.RequestException("https://example/?access_token=pk.secret-value")), \
       patch("openpilot.sunnypilot.navd.navigationd.cloudlog.warning") as warning:
    assert not engine._request_route(destination)
  assert "pk.secret-value" not in str(warning.call_args)
