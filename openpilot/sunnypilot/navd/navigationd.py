#!/usr/bin/env python3
"""Mapbox route guidance with persistent route caching.

Routing needs a network connection. Guidance does not: the active route is kept
in Params and restored after process restarts or temporary connectivity loss.
"""
import json
import math
import time

import requests

from openpilot.cereal import log, messaging
from openpilot.common.params import Params
from openpilot.common.realtime import Ratekeeper
from openpilot.common.swaglog import cloudlog
from openpilot.sunnypilot.navd.helpers import Coordinate, distance_along_geometry, minimum_distance, parse_banner_instructions

REROUTE_DISTANCE = 35.0
MANEUVER_TRANSITION_THRESHOLD = 12.0
ROUTE_REQUEST_TIMEOUT = 12


def _destination(params: Params) -> Coordinate | None:
  raw = params.get("NavDestination")
  if not raw:
    return None
  try:
    value = raw if isinstance(raw, dict) else json.loads(raw)
    return Coordinate(float(value["latitude"]), float(value["longitude"]))
  except (KeyError, TypeError, ValueError, json.JSONDecodeError):
    return None


def _coord_dict(c: Coordinate) -> dict[str, float]:
  return {"latitude": c.latitude, "longitude": c.longitude}


class NavigationEngine:
  def __init__(self, sm=None, pm=None, params=None):
    self.params = params or Params()
    self.sm = sm or messaging.SubMaster(["gpsLocationExternal"])
    self.pm = pm or messaging.PubMaster(["navInstruction", "navRoute"])
    self.position: Coordinate | None = None
    self.bearing: float | None = None
    self.destination: Coordinate | None = None
    self.steps: list[dict] = []
    self.geometry: list[list[Coordinate]] = []
    self.step_idx = 0
    self.last_route_attempt = 0.0
    self._restore_route()

  def _restore_route(self) -> None:
    raw = self.params.get("NavigationRouteCache")
    cached_destination = self.params.get("NavigationRouteDestination")
    if not raw or not cached_destination:
      return
    try:
      self.steps = raw if isinstance(raw, list) else json.loads(raw)
      d = cached_destination if isinstance(cached_destination, dict) else json.loads(cached_destination)
      self.destination = Coordinate(float(d["latitude"]), float(d["longitude"]))
      self.geometry = [[Coordinate.from_mapbox_tuple(c) for c in step["geometry"]["coordinates"]] for step in self.steps]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
      self.steps, self.geometry, self.destination = [], [], None

  def _update_position(self) -> None:
    self.sm.update(0)
    gps = self.sm["gpsLocationExternal"]
    if self.sm.valid["gpsLocationExternal"] and gps.hasFix:
      self.position = Coordinate(gps.latitude, gps.longitude)
      self.bearing = gps.bearingDeg

  def _token(self) -> str:
    return self.params.get("MapboxPublicKey") or self.params.get("MapboxSecretKey") or ""

  def _request_route(self, destination: Coordinate) -> bool:
    if self.position is None or not self._token():
      return False
    query = {
      "access_token": self._token(), "geometries": "geojson", "overview": "full", "steps": "true",
      "banner_instructions": "true", "alternatives": "false", "language": self.params.get("LanguageSetting") or "en",
    }
    if self.bearing is not None and math.isfinite(self.bearing):
      query["bearings"] = f"{self.bearing % 360:.0f},90;"
    url = ("https://api.mapbox.com/directions/v5/mapbox/driving-traffic/"
           f"{self.position.longitude},{self.position.latitude};{destination.longitude},{destination.latitude}")
    try:
      response = requests.get(url, params=query, timeout=ROUTE_REQUEST_TIMEOUT)
      response.raise_for_status()
      routes = response.json().get("routes", [])
      if not routes:
        return False
      steps = routes[0]["legs"][0]["steps"]
      geometry = [[Coordinate.from_mapbox_tuple(c) for c in step["geometry"]["coordinates"]] for step in steps]
      self.steps, self.geometry, self.destination, self.step_idx = steps, geometry, destination, 0
      self.params.put("NavigationRouteCache", steps)
      self.params.put("NavigationRouteDestination", _coord_dict(destination))
      return True
    except (requests.RequestException, KeyError, TypeError, ValueError, json.JSONDecodeError):
      cloudlog.exception("Mapbox route request failed; retaining cached route")
      return False

  def _off_route(self) -> bool:
    if self.position is None or not self.geometry or self.step_idx >= len(self.geometry):
      return True
    path = self.geometry[self.step_idx]
    distances = [minimum_distance(path[i], path[i + 1], self.position) for i in range(len(path) - 1)]
    return not distances or min(distances) > REROUTE_DISTANCE

  def _update_route(self) -> None:
    destination = _destination(self.params)
    if destination is None:
      self.steps, self.geometry, self.destination = [], [], None
      return
    changed = self.destination is None or destination.distance_to(self.destination) > 1.0
    if changed or self._off_route():
      now = time.monotonic()
      if now - self.last_route_attempt >= 10.0:
        self.last_route_attempt = now
        self._request_route(destination)

  def _publish(self) -> None:
    instruction = messaging.new_message("navInstruction")
    route = messaging.new_message("navRoute")
    if self.position is None or not self.steps or self.step_idx >= len(self.steps):
      instruction.valid = False
      self.pm.send("navInstruction", instruction)
      self.pm.send("navRoute", route)
      return

    step = self.steps[self.step_idx]
    path = self.geometry[self.step_idx]
    distance = max(0.0, step["distance"] - distance_along_geometry(path, self.position))
    parsed = parse_banner_instructions(step.get("bannerInstructions", []), distance) or {}
    nav = instruction.navInstruction
    self.params.put("NavigationManeuverId", f"{self.destination.latitude:.6f}:{self.destination.longitude:.6f}:{self.step_idx}")
    nav.maneuverDistance = distance
    for key in ("maneuverPrimaryText", "maneuverSecondaryText", "maneuverType", "maneuverModifier", "showFull"):
      if key in parsed:
        setattr(nav, key, parsed[key])
    remaining_steps = self.steps[self.step_idx:]
    nav.distanceRemaining = distance + sum(s["distance"] for s in remaining_steps[1:])
    nav.timeRemaining = (step["duration"] * distance / max(step["distance"], 1.0)) + sum(s["duration"] for s in remaining_steps[1:])
    instruction.valid = True
    self.pm.send("navInstruction", instruction)

    route.navRoute.coordinates = [_coord_dict(c) for segment in self.geometry[self.step_idx:] for c in segment]
    route.valid = True
    self.pm.send("navRoute", route)

    if distance <= MANEUVER_TRANSITION_THRESHOLD:
      if self.step_idx + 1 < len(self.steps):
        self.step_idx += 1
      elif self.destination.distance_to(self.position) < REROUTE_DISTANCE:
        self.params.remove("NavDestination")

  def update(self) -> None:
    self._update_position()
    self._update_route()
    self._publish()


def main() -> None:
  engine = NavigationEngine()
  rk = Ratekeeper(1.0)
  while True:
    engine.update()
    rk.keep_time()


if __name__ == "__main__":
  main()
