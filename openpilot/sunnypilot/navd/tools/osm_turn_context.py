#!/usr/bin/env python3
"""Build OFFLINE road context from an OSM extract and a matched junction.

This is not a routing engine, lane assignment, model tensor, or vehicle process.
The caller must supply a complete junction extract and a replay map match. Way
centerlines must never be used as steering targets or placed in recurrent model
features. No messaging, Params, network, model runner, or CAN imports belong here.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path


ROAD_TYPES = frozenset(("motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
                        "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link", "living_street", "service"))
ACCESS_KEYS = ("motorcar", "motor_vehicle", "vehicle", "access")
MAX_SAMPLE_AGE_S = 1.0
MAX_ACCURACY_M = 5.0
MAX_JUNCTION_DISTANCE_M = 60.0
MAX_CONTEXT_LENGTH_M = 80.0


class UnsupportedContext(ValueError):
  pass


@dataclass(frozen=True)
class Observation:
  # These three IDs are an external replay map match, not inferred from blinkers.
  from_way_id: int
  previous_node_id: int
  junction_node_id: int
  latitude: float
  longitude: float
  bearing_deg: float  # clockwise from geographic north
  accuracy_m: float
  now_s: float
  state_time_s: float
  match_time_s: float  # same clock as now_s, from the matched localization sample
  left_blinker: bool
  right_blinker: bool
  localization_valid: bool
  can_valid: bool


def _xy(latitude, longitude, obs):
  east = math.radians(longitude - obs.longitude) * 6371000 * math.cos(math.radians(obs.latitude))
  north = math.radians(latitude - obs.latitude) * 6371000
  heading = math.radians(obs.bearing_deg)
  return (east * math.sin(heading) + north * math.cos(heading),
          -east * math.cos(heading) + north * math.sin(heading))  # forward, LEFT; metres


def _directions(tags):
  if any(":conditional" in key for key in tags):
    raise UnsupportedContext("conditional_way_tags")
  for key in ACCESS_KEYS:
    if key in tags:
      if tags[key] not in ("yes", "designated", "permissive"):
        return ()  # unknown, private and destination access are not assumed
      break
  if any(key in tags for key in ("barrier", "construction", "proposed")) or tags.get("area") == "yes":
    return ()
  if tags.get("highway") not in ROAD_TYPES:
    return ()
  if tags.get("junction") in ("roundabout", "circular"):
    raise UnsupportedContext("roundabout_requires_router")
  implied = "yes" if tags.get("highway") == "motorway" else "no"
  oneway = next((tags[key] for key in ("oneway:motorcar", "oneway:motor_vehicle", "oneway:vehicle", "oneway") if key in tags), implied)
  if oneway in ("yes", "1", "true"):
    return (1,)
  if oneway == "-1":
    return (-1,)
  if oneway in ("no", "0", "false"):
    return (-1, 1)
  raise UnsupportedContext("unsupported_oneway")


def _restrictions(relations, obs):
  forbidden, only = set(), None
  for relation in relations:
    tags, members = relation.get("tags", {}), relation.get("members", [])
    if tags.get("type") != "restriction":
      continue
    from_ids = [m["ref"] for m in members if m.get("role") == "from" and m.get("type") == "way"]
    via = [m for m in members if m.get("role") == "via"]
    if obs.from_way_id not in from_ids:
      # A malformed restriction at our junction cannot silently disappear.
      if not from_ids and any(m.get("type") == "node" and m.get("ref") == obs.junction_node_id for m in via):
        raise UnsupportedContext("incomplete_restriction")
      continue
    if set(ACCESS_KEYS).intersection(mode.strip() for mode in tags.get("except", "").split(";")):
      continue
    keys = ("restriction:motorcar", "restriction:motor_vehicle", "restriction:vehicle", "restriction")
    if any(key.startswith(keys) and ":conditional" in key for key in tags):
      raise UnsupportedContext("conditional_restriction")
    restriction = next((tags[key] for key in keys if key in tags), None)
    if restriction is None:
      if any(key.startswith("restriction:") for key in tags):
        continue  # a restriction only for another vehicle class
      raise UnsupportedContext("missing_restriction_type")
    if len(via) != 1 or via[0].get("type") != "node":
      raise UnsupportedContext("via_way_or_incomplete_restriction")
    if via[0].get("ref") != obs.junction_node_id:
      continue
    to_ids = [m["ref"] for m in members if m.get("role") == "to" and m.get("type") == "way"]
    if len(from_ids) != 1 or len(to_ids) != 1:
      raise UnsupportedContext("complex_restriction")
    # Same-way restrictions distinguish U-turns from continuing on that way.
    # Way-ID filtering alone cannot represent this case.
    if to_ids[0] == obs.from_way_id:
      raise UnsupportedContext("same_way_restriction")
    if restriction in ("no_left_turn", "no_right_turn", "no_straight_on", "no_u_turn", "no_entry", "no_exit"):
      forbidden.add(to_ids[0])
    elif restriction in ("only_left_turn", "only_right_turn", "only_straight_on"):
      only = set(to_ids) if only is None else only.intersection(to_ids)
    else:
      raise UnsupportedContext("unknown_restriction")
  return forbidden, only


def _result(status, reason, candidates=(), selected=None):
  return {"schema_version": 1, "mode": "offline_road_context", "status": status, "reason": reason,
          "model_input_ready": False, "target_lane": None, "coordinate_frame": "x_forward_y_left_metres",
          "candidates": list(candidates), "selected_candidate_id": selected}


def build_context(osm, obs):
  """Return a coarse road candidate, withholding any uncertain selection.

The completeness of the extract and correctness of the caller's map match are
prerequisites, not facts proved by this function. A unique candidate is still
only a hypothesis: a turn signal can indicate a lane change or an earlier turn.
"""
  bools = (obs.left_blinker, obs.right_blinker, obs.localization_valid, obs.can_valid)
  numbers = (obs.latitude, obs.longitude, obs.bearing_deg, obs.accuracy_m, obs.now_s, obs.state_time_s, obs.match_time_s)
  if any(type(value) is not bool for value in bools) or any(type(value) not in (int, float) or not math.isfinite(value) for value in numbers):
    return _result("withheld", "invalid_observation")
  if not (-85 <= obs.latitude <= 85 and -180 <= obs.longitude <= 180 and 0 <= obs.bearing_deg < 360):
    return _result("withheld", "invalid_position_or_bearing")
  if not obs.can_valid or not obs.localization_valid or not 0 <= obs.accuracy_m <= MAX_ACCURACY_M:
    return _result("withheld", "invalid_localization_or_can")
  if any(not 0 <= obs.now_s - stamp <= MAX_SAMPLE_AGE_S for stamp in (obs.state_time_s, obs.match_time_s)):
    return _result("withheld", "stale_or_future_observation")
  if obs.left_blinker == obs.right_blinker:
    return _result("withheld", "hazards_or_no_turn_signal")
  try:
    return _build_context(osm, obs)
  except (KeyError, TypeError, ValueError, IndexError) as exc:
    return _result("withheld", str(exc) if isinstance(exc, UnsupportedContext) else "invalid_or_incomplete_extract")


def _build_context(osm, obs):
  nodes, ways, relations = {}, {}, []
  if not isinstance(osm["elements"], list):
    raise UnsupportedContext("invalid_extract_schema")
  for element in osm["elements"]:
    if not isinstance(element, dict) or type(element["id"]) is not int:
      raise UnsupportedContext("invalid_element_schema")
    tags = element.get("tags", {})
    if not isinstance(tags, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in tags.items()):
      raise UnsupportedContext("invalid_tags")
    kind = element["type"]
    if kind == "node":
      latitude, longitude = element["lat"], element["lon"]
      if not (-85 <= latitude <= 85 and -180 <= longitude <= 180):
        raise UnsupportedContext("invalid_map_coordinate")
      if element["id"] in nodes:
        raise UnsupportedContext("duplicate_node")
      nodes[element["id"]] = element
    elif kind == "way":
      if not isinstance(element["nodes"], list) or any(type(node_id) is not int for node_id in element["nodes"]):
        raise UnsupportedContext("invalid_way_nodes")
      if element["id"] in ways:
        raise UnsupportedContext("duplicate_way")
      ways[element["id"]] = element
    elif kind == "relation":
      if not isinstance(element["members"], list) or any(not isinstance(member, dict) or type(member.get("ref")) is not int
                                                       for member in element["members"]):
        raise UnsupportedContext("invalid_relation_members")
      relations.append(element)

  previous, junction = nodes[obs.previous_node_id], nodes[obs.junction_node_id]
  incoming = ways[obs.from_way_id]
  junction_index = incoming["nodes"].index(obs.junction_node_id)
  previous_index = incoming["nodes"].index(obs.previous_node_id)
  approach_direction = junction_index - previous_index
  if approach_direction not in _directions(incoming.get("tags", {})):
    raise UnsupportedContext("invalid_approach_direction")
  if any(node.get("tags", {}).get("barrier") for node in (previous, junction)):
    raise UnsupportedContext("junction_barrier")
  start = _xy(previous["lat"], previous["lon"], obs)
  end = _xy(junction["lat"], junction["lon"], obs)
  dx, dy = end[0] - start[0], end[1] - start[1]
  length = math.hypot(dx, dy)
  if length < 1 or dx / length < math.cos(math.radians(30)):
    raise UnsupportedContext("approach_heading_mismatch")
  fraction = -(start[0] * dx + start[1] * dy) / length ** 2
  offset = abs(start[0] * dy - start[1] * dx) / length
  if not 0 <= fraction <= 1 or offset > obs.accuracy_m + 3 or not 2 <= math.hypot(*end) <= MAX_JUNCTION_DISTANCE_M:
    raise UnsupportedContext("approach_position_mismatch")

  forbidden, only = _restrictions(relations, obs)
  candidates = []
  incident = [way for way in ways.values() if obs.junction_node_id in way["nodes"]]
  for way in sorted(incident, key=lambda item: item["id"]):
    tags, ids = way.get("tags", {}), way["nodes"]
    if len(ids) != len(set(ids)):
      raise UnsupportedContext("loop_way_requires_router")
    directions = _directions(tags)
    if not directions or way["id"] in forbidden or (only is not None and way["id"] not in only):
      continue
    # Missing geometry must not turn multiple possibilities into a unique one.
    if any(node_id not in nodes for node_id in ids):
      raise UnsupportedContext("incomplete_way_geometry")
    index = ids.index(obs.junction_node_id)
    for direction in directions:
      positions = list(range(index, len(ids) if direction == 1 else -1, direction))
      if len(positions) < 2 or ids[positions[1]] == obs.previous_node_id:
        continue
      points = [end]
      path_nodes, distance = [obs.junction_node_id], 0.0
      for pos in positions[1:]:
        node = nodes[ids[pos]]
        if node.get("tags", {}).get("barrier"):
          raise UnsupportedContext("outgoing_barrier")
        point = _xy(node["lat"], node["lon"], obs)
        segment_length = math.dist(points[-1], point)
        if segment_length < 0.1:
          raise UnsupportedContext("degenerate_way_geometry")
        if distance + segment_length > MAX_CONTEXT_LENGTH_M:
          scale = (MAX_CONTEXT_LENGTH_M - distance) / segment_length
          points.append(tuple(a + scale * (b - a) for a, b in zip(points[-1], point, strict=True)))
          break
        points.append(point)
        path_nodes.append(ids[pos])
        distance += segment_length
        # Do not invent a continuation beyond the next mapped road junction.
        if any(other["id"] != way["id"] and ids[pos] in other["nodes"] and other.get("tags", {}).get("highway") in ROAD_TYPES
               for other in ways.values()):
          break
      outgoing = (points[1][0] - end[0], points[1][1] - end[1])
      angle = math.degrees(math.atan2(outgoing[1], outgoing[0]) - math.atan2(dy, dx))
      angle = (angle + 180) % 360 - 180  # positive = left of incoming road
      if not 20 <= abs(angle) < 150:
        continue  # straight, near-straight forks and U-turns are not inferred
      turn = "left" if angle > 0 else "right"
      if (turn == "left") != obs.left_blinker:
        continue
      candidates.append({"id": f'{way["id"]}:{direction}', "way_id": way["id"], "direction": turn,
                         "road_name": tags.get("name", ""), "turn_angle_deg": round(angle, 2),
                         "path_xy_m": [[round(x, 3), round(y, 3)] for x, y in points], "node_ids": path_nodes,
                         "lane_tags": {key: value for key, value in tags.items() if "lanes" in key},
                         "geometry_kind": "osm_way_centerline"})
  if not candidates:
    return _result("withheld", "no_supported_turn_candidate")
  if len(candidates) > 1:
    return _result("ambiguous", "multiple_roads_match_turn_signal", candidates)
  return _result("unique_road_candidate", "road_hypothesis_only", candidates, candidates[0]["id"])


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("snapshot", type=Path, help="JSON with osm.elements and observation; see the synthetic fixture")
  args = parser.parse_args()
  raw = args.snapshot.read_bytes()
  snapshot = json.loads(raw)
  result = build_context(snapshot["osm"], Observation(**snapshot["observation"]))
  result["snapshot_sha256"] = hashlib.sha256(raw).hexdigest()
  print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
  main()
