#!/usr/bin/env python3
"""Mapbox route guidance with persistent, destination-bound route caching.

Directions requests need a network connection. Once downloaded, route geometry
and instructions remain usable while offline. Position-dependent guidance is
only published while the external GPS message is alive and has a fix.
"""
from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import math
import time

import requests

from openpilot.cereal import log, messaging
from openpilot.common.params import Params
from openpilot.common.realtime import Ratekeeper
from openpilot.common.swaglog import cloudlog
from openpilot.sunnypilot.navd.helpers import Coordinate, distance_along_geometry, minimum_distance, parse_banner_instructions
from openpilot.sunnypilot.navd.mapbox_token_codec import decode_mapbox_token

REROUTE_DISTANCE = 35.0
MANEUVER_TRANSITION_THRESHOLD = 12.0
ROUTE_REQUEST_TIMEOUT = 12
ROUTE_RETRY_INTERVAL = 10.0


def _wall_time() -> float:
  # Wall time is intentional here: this timestamp survives a device restart
  # and is only used to report cache age, never for safety/control timing.
  return datetime.now(UTC).timestamp()


def _destination(params: Params) -> Coordinate | None:
  raw = params.get("NavDestination")
  if not raw:
    return None
  try:
    value = raw if isinstance(raw, dict) else json.loads(raw)
    latitude, longitude = float(value["latitude"]), float(value["longitude"])
    if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
      return None
    return Coordinate(latitude, longitude)
  except (KeyError, TypeError, ValueError, json.JSONDecodeError):
    return None


def _coord_dict(c: Coordinate) -> dict[str, float]:
  return {"latitude": c.latitude, "longitude": c.longitude}


def _build_geometry(steps: list[dict]) -> list[list[Coordinate]]:
  geometry: list[list[Coordinate]] = []
  for step in steps:
    coordinates = step["geometry"]["coordinates"]
    segment = [Coordinate.from_mapbox_tuple(c) for c in coordinates]
    if not segment:
      raise ValueError("route step has no geometry")
    geometry.append(segment)
  return geometry


def _route_id(steps: list[dict], destination: Coordinate) -> str:
  identity = {
    "destination": [round(destination.latitude, 6), round(destination.longitude, 6)],
    "steps": [{
      "distance": round(float(step.get("distance", 0.0)), 1),
      "type": step.get("maneuver", {}).get("type", ""),
      "modifier": step.get("maneuver", {}).get("modifier", ""),
      "end": step.get("geometry", {}).get("coordinates", [[0.0, 0.0]])[-1],
    } for step in steps],
  }
  return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]


class NavigationEngine:
  def __init__(self, sm=None, pm=None, params=None):
    self.params = params or Params()
    self.sm = sm or messaging.SubMaster(["gpsLocationExternal", "deviceState"])
    self.pm = pm or messaging.PubMaster(["navInstruction", "navRoute", "navigationStateSP"])
    self.position: Coordinate | None = None
    self.bearing: float | None = None
    self.destination: Coordinate | None = None
    self.steps: list[dict] = []
    self.geometry: list[list[Coordinate]] = []
    self.step_idx = 0
    self.route_id = ""
    self.last_route_attempt = -ROUTE_RETRY_INTERVAL
    self.route_loaded_mono = 0.0
    self.route_loaded_wall = 0.0
    self.last_instruction_mono = 0.0
    self.using_cached_route = False
    self.recalculating = False
    self.route_error = False
    self.arrived = False
    self.location_valid = False
    self.network_available = False
    self._restore_route()

  def _clear_cached_route(self) -> None:
    for key in ("NavigationRouteCache", "NavigationRouteDestination", "NavigationRouteMetadata", "NavigationManeuverId"):
      self.params.remove(key)

  def _clear_route(self, *, clear_cache: bool) -> None:
    self.steps, self.geometry = [], []
    self.destination = None
    self.step_idx = 0
    self.route_id = ""
    self.route_loaded_mono = 0.0
    self.route_loaded_wall = 0.0
    self.last_instruction_mono = 0.0
    self.using_cached_route = False
    self.recalculating = False
    self.route_error = False
    self.arrived = False
    self.last_route_attempt = -ROUTE_RETRY_INTERVAL
    if clear_cache:
      self._clear_cached_route()

  def _restore_route(self) -> None:
    active_destination = _destination(self.params)
    raw = self.params.get("NavigationRouteCache")
    cached_destination = self.params.get("NavigationRouteDestination")
    if active_destination is None:
      # A canceled or completed destination must never resurrect after restart.
      if raw or cached_destination:
        self._clear_cached_route()
      return
    if not raw or not cached_destination:
      self.destination = active_destination
      return
    try:
      steps = raw if isinstance(raw, list) else json.loads(raw)
      d = cached_destination if isinstance(cached_destination, dict) else json.loads(cached_destination)
      cached = Coordinate(float(d["latitude"]), float(d["longitude"]))
      if cached.distance_to(active_destination) > 1.0:
        self._clear_cached_route()
        self.destination = active_destination
        return
      metadata = self.params.get("NavigationRouteMetadata") or {}
      if isinstance(metadata, str):
        metadata = json.loads(metadata)
      geometry = _build_geometry(steps)
      self.steps, self.geometry, self.destination = steps, geometry, active_destination
      self.route_id = str(metadata.get("routeId") or _route_id(steps, active_destination))
      self.route_loaded_wall = float(metadata.get("savedAt", _wall_time()))
      self.route_loaded_mono = time.monotonic()
      self.using_cached_route = True
    except (KeyError, TypeError, ValueError, IndexError, json.JSONDecodeError):
      self._clear_cached_route()
      self.destination = active_destination

  def _update_position(self) -> None:
    self.sm.update(0)
    now = time.monotonic()
    recv_time = getattr(self.sm, "recv_time", {})
    gps = self.sm["gpsLocationExternal"]
    gps_alive = self.sm.alive.get("gpsLocationExternal", False)
    gps_fresh = 0 <= now - recv_time.get("gpsLocationExternal", now) <= 2.5
    self.location_valid = bool(self.sm.valid["gpsLocationExternal"] and gps_alive and gps_fresh and gps.hasFix and
                               math.isfinite(gps.latitude) and math.isfinite(gps.longitude))
    if self.location_valid:
      self.position = Coordinate(gps.latitude, gps.longitude)
      self.bearing = gps.bearingDeg if math.isfinite(gps.bearingDeg) else None
    else:
      self.position = None
      self.bearing = None

    device_seen = self.sm.seen.get("deviceState", False)
    device_fresh = 0 <= now - recv_time.get("deviceState", now) <= 2.5
    self.network_available = bool(device_seen and self.sm.alive.get("deviceState", False) and device_fresh and
                                  self.sm.valid["deviceState"] and
                                  self.sm["deviceState"].networkType != log.DeviceState.NetworkType.none)

  def _token(self) -> str:
    token = self.params.get("MapboxPublicKey") or self.params.get("MapboxSecretKey") or ""
    if not token:
      return token
    try:
      return decode_mapbox_token(token)
    except ValueError:
      return ""

  def _save_route(self) -> None:
    assert self.destination is not None
    self.params.put("NavigationRouteCache", self.steps)
    self.params.put("NavigationRouteDestination", _coord_dict(self.destination))
    self.params.put("NavigationRouteMetadata", {
      "routeId": self.route_id,
      "savedAt": self.route_loaded_wall,
    })

  def _request_route(self, destination: Coordinate) -> bool:
    token = self._token()
    if self.position is None:
      return False
    if not token or not self.network_available:
      self.route_error = True
      return False
    query = {
      "access_token": token, "geometries": "geojson", "overview": "full", "steps": "true",
      "banner_instructions": "true", "alternatives": "false", "language": self.params.get("LanguageSetting") or "en",
    }
    if self.bearing is not None:
      query["bearings"] = f"{self.bearing % 360:.0f},90;"
    url = ("https://api.mapbox.com/directions/v5/mapbox/driving-traffic/"
           f"{self.position.longitude},{self.position.latitude};{destination.longitude},{destination.latitude}")
    self.destination = destination
    self.recalculating = True
    # Clear the previous turn card before a potentially blocking Directions
    # request and publish a truthful intermediate state. The following normal
    # publish replaces it with the new route or an explicit error/stale state.
    instruction = messaging.new_message("navInstruction")
    instruction.valid = False
    self.pm.send("navInstruction", instruction)
    self.params.remove("NavigationManeuverId")
    self._publish_state("", False)
    try:
      response = requests.get(url, params=query, timeout=ROUTE_REQUEST_TIMEOUT)
      response.raise_for_status()
      routes = response.json().get("routes", [])
      if not routes:
        raise ValueError("empty route response")
      steps = routes[0]["legs"][0]["steps"]
      geometry = _build_geometry(steps)
      if not steps:
        raise ValueError("route has no steps")
      self.steps, self.geometry, self.destination, self.step_idx = steps, geometry, destination, 0
      self.route_id = _route_id(steps, destination)
      self.route_loaded_mono = time.monotonic()
      self.route_loaded_wall = _wall_time()
      self.using_cached_route = False
      self.route_error = False
      self.arrived = False
      self._save_route()
      return True
    except (requests.RequestException, KeyError, TypeError, ValueError, IndexError, json.JSONDecodeError):
      # Exception strings from requests can contain the complete URL, including
      # access_token. Never put that data in logs.
      cloudlog.warning("Mapbox route request failed; a matching cached route will be retained")
      self.route_error = True
      return False
    finally:
      self.recalculating = False

  def _off_route(self) -> bool:
    if self.position is None:
      return False
    if not self.geometry or self.step_idx >= len(self.geometry):
      return True
    path = self.geometry[self.step_idx]
    distances = [minimum_distance(path[i], path[i + 1], self.position) for i in range(len(path) - 1)]
    if not distances and path:
      distances = [path[0].distance_to(self.position)]
    return not distances or min(distances) > REROUTE_DISTANCE

  def _select_step_for_position(self) -> None:
    """Advance a restored route to the closest remaining segment."""
    if self.position is None or not self.geometry:
      return
    closest_idx, closest_distance = self.step_idx, math.inf
    for index in range(self.step_idx, len(self.geometry)):
      path = self.geometry[index]
      distances = [minimum_distance(path[i], path[i + 1], self.position) for i in range(len(path) - 1)]
      if not distances and path:
        distances = [path[0].distance_to(self.position)]
      if distances and min(distances) < closest_distance:
        closest_idx, closest_distance = index, min(distances)
    if closest_distance <= REROUTE_DISTANCE:
      self.step_idx = closest_idx

  def _update_route(self) -> None:
    destination = _destination(self.params)
    if destination is None:
      self.arrived = False
      if self.steps or self.destination is not None:
        self._clear_route(clear_cache=True)
      return

    changed = self.destination is None or destination.distance_to(self.destination) > 1.0
    if changed:
      # Never show instructions from the previous destination while requesting
      # the new one. Keep only the Params destination itself.
      self._clear_route(clear_cache=True)
      self.destination = destination

    self._select_step_for_position()
    needs_route = not self.steps or self._off_route()
    if not needs_route:
      self.route_error = False
    if needs_route and self.position is not None:
      now = time.monotonic()
      if now - self.last_route_attempt >= ROUTE_RETRY_INTERVAL:
        self.last_route_attempt = now
        self._request_route(destination)

  @staticmethod
  def _instruction_fields(step: dict, distance: float) -> dict:
    try:
      parsed = parse_banner_instructions(step.get("bannerInstructions", []), distance) or {}
    except (KeyError, TypeError, ValueError, IndexError):
      parsed = {}
    maneuver = step.get("maneuver", {}) or {}
    primary = parsed.get("maneuverPrimaryText") or maneuver.get("instruction") or step.get("name") or "Continue"
    secondary = parsed.get("maneuverSecondaryText") or ""
    road_name = str(step.get("name") or "")
    if not secondary and road_name and road_name.strip() != str(primary).strip():
      secondary = road_name
    return {
      **parsed,
      "maneuverPrimaryText": str(primary),
      "maneuverSecondaryText": str(secondary),
      "maneuverType": str(parsed.get("maneuverType") or maneuver.get("type") or "continue"),
      "maneuverModifier": str(parsed.get("maneuverModifier") or maneuver.get("modifier") or "straight"),
      "showFull": bool(parsed.get("showFull", True)),
    }

  def _publish_state(self, maneuver_id: str, instruction_valid: bool) -> None:
    msg = messaging.new_message("navigationStateSP")
    state = msg.navigationStateSP
    state.routeId = self.route_id
    state.maneuverId = maneuver_id
    state.routeLoaded = bool(self.steps)
    state.locationValid = self.location_valid
    state.instructionValid = instruction_valid
    state.networkAvailable = self.network_available
    state.usingCachedRoute = self.using_cached_route
    state.recalculating = self.recalculating
    now = time.monotonic()
    state.routeAgeSec = max(0.0, _wall_time() - self.route_loaded_wall) if self.route_loaded_wall else 0.0
    state.instructionAgeSec = max(0.0, now - self.last_instruction_mono) if self.last_instruction_mono else 0.0

    if self.arrived:
      state.status = "arrived"
    elif self.destination is None:
      state.status = "noDestination"
    elif not self.location_valid:
      state.status = "waitingForLocation"
    elif self.recalculating:
      state.status = "recalculating"
    elif self.route_error and self.steps:
      state.status = "stale"
    elif self.route_error and not self.steps:
      state.status = "routeError"
    elif not self.steps:
      state.status = "waitingForRoute"
    elif self.using_cached_route:
      state.status = "cachedRoute"
    else:
      state.status = "routeLoaded"
    msg.valid = True
    self.pm.send("navigationStateSP", msg)

  def _publish(self) -> None:
    instruction = messaging.new_message("navInstruction")
    route = messaging.new_message("navRoute")
    maneuver_id = ""
    instruction_valid = False

    if self.steps and self.step_idx < len(self.steps):
      route.navRoute.coordinates = [_coord_dict(c) for segment in self.geometry[self.step_idx:] for c in segment]
      route.valid = True
    else:
      route.valid = False
    guidance_stale = bool(self.route_error and self._off_route())
    if (self.location_valid and self.position is not None and self.steps and
        self.step_idx < len(self.steps) and not guidance_stale):
      step = self.steps[self.step_idx]
      path = self.geometry[self.step_idx]
      along = distance_along_geometry(path, self.position) if path else 0.0
      distance = max(0.0, float(step.get("distance", 0.0)) - along)
      fields = self._instruction_fields(step, distance)
      nav = instruction.navInstruction
      maneuver_id = f"{self.route_id}:{self.step_idx}"
      self.params.put("NavigationManeuverId", maneuver_id)
      nav.maneuverDistance = distance
      for key in ("maneuverPrimaryText", "maneuverSecondaryText", "maneuverType", "maneuverModifier", "showFull", "lanes"):
        if key in fields:
          setattr(nav, key, fields[key])
      remaining_steps = self.steps[self.step_idx:]
      current_distance = max(float(step.get("distance", 0.0)), 1.0)
      nav.distanceRemaining = distance + sum(float(s.get("distance", 0.0)) for s in remaining_steps[1:])
      nav.timeRemaining = (float(step.get("duration", 0.0)) * distance / current_distance) + \
                          sum(float(s.get("duration", 0.0)) for s in remaining_steps[1:])
      nav.timeRemainingTypical = nav.timeRemaining
      instruction.valid = True
      instruction_valid = True
      self.last_instruction_mono = time.monotonic()

      if distance <= MANEUVER_TRANSITION_THRESHOLD:
        if self.step_idx + 1 < len(self.steps):
          self.step_idx += 1
        elif self.destination is not None and self.destination.distance_to(self.position) < REROUTE_DISTANCE:
          self.params.remove("NavDestination")
          self.params.remove("NavigationManeuverId")
          self._clear_route(clear_cache=True)
          self.arrived = True
          route.valid = False
          instruction.valid = False
          instruction_valid = False
          maneuver_id = ""
    else:
      instruction.valid = False
      self.params.remove("NavigationManeuverId")
    self.pm.send("navRoute", route)
    self.pm.send("navInstruction", instruction)
    self._publish_state(maneuver_id, instruction_valid)

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
