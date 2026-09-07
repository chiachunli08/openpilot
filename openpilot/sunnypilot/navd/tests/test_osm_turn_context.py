import copy
from dataclasses import replace
import json
import math
from pathlib import Path
import unittest

from openpilot.sunnypilot.navd.tools.osm_turn_context import Observation, build_context


FIXTURE = Path(__file__).parent / "fixtures" / "osm_turn_snapshot.json"


class TestOsmTurnContext(unittest.TestCase):
  def setUp(self):
    self.snapshot = json.loads(FIXTURE.read_text())
    self.osm = self.snapshot["osm"]
    self.obs = Observation(**self.snapshot["observation"])

  def way(self, way_id):
    return next(e for e in self.osm["elements"] if e["type"] == "way" and e["id"] == way_id)

  def restriction(self, value="no_left_turn", to_id=20, extra=None):
    relation = {"type": "relation", "id": 100, "tags": {"type": "restriction", "restriction": value}, "members": [
      {"type": "way", "ref": 10, "role": "from"}, {"type": "node", "ref": 2, "role": "via"},
      {"type": "way", "ref": to_id, "role": "to"}]}
    relation["tags"].update(extra or {})
    self.osm["elements"].append(relation)
    return relation

  def test_left_shape_preserved_without_lane_target_or_model_tensor(self):
    before = copy.deepcopy(self.osm)
    result = build_context(self.osm, self.obs)
    self.assertEqual(result["status"], "unique_road_candidate")
    self.assertEqual(result["selected_candidate_id"], "20:1")
    candidate = result["candidates"][0]
    self.assertEqual(candidate["node_ids"], [2, 4, 5])
    self.assertEqual(candidate["lane_tags"], {"lanes": "2"})
    self.assertAlmostEqual(candidate["path_xy_m"][0][0], 11.119, places=3)
    self.assertGreater(candidate["path_xy_m"][1][1], 30)
    self.assertGreater(candidate["path_xy_m"][2][0], candidate["path_xy_m"][1][0])
    self.assertFalse(result["model_input_ready"])
    self.assertIsNone(result["target_lane"])
    self.assertEqual(self.osm, before)

  def test_right_signal_and_vehicle_coordinate_frame(self):
    result = build_context(self.osm, replace(self.obs, left_blinker=False, right_blinker=True))
    self.assertEqual(result["selected_candidate_id"], "30:1")
    self.assertLess(result["candidates"][0]["path_xy_m"][1][1], 0)

  def test_reverse_approach_rotates_geometry_and_intent(self):
    obs = replace(self.obs, previous_node_id=3, latitude=0.0001, bearing_deg=180, left_blinker=False, right_blinker=True)
    result = build_context(self.osm, obs)
    self.assertEqual(result["selected_candidate_id"], "20:1")
    self.assertLess(result["candidates"][0]["path_xy_m"][1][1], 0)
    self.way(10)["tags"]["oneway"] = "yes"
    self.assertEqual(build_context(self.osm, obs)["reason"], "invalid_approach_direction")

  def test_multiple_left_roads_are_ambiguous(self):
    self.osm["elements"].extend([
      {"type": "node", "id": 7, "lat": 0.0001, "lon": -0.0003},
      {"type": "way", "id": 40, "nodes": [2, 7], "tags": {"highway": "residential"}},
    ])
    result = build_context(self.osm, self.obs)
    self.assertEqual(result["status"], "ambiguous")
    self.assertEqual(len(result["candidates"]), 2)
    self.assertIsNone(result["selected_candidate_id"])

  def test_signal_cancellation_does_not_retain_a_previous_candidate(self):
    self.assertIsNotNone(build_context(self.osm, self.obs)["selected_candidate_id"])
    for left, right in ((False, False), (True, True)):
      result = build_context(self.osm, replace(self.obs, left_blinker=left, right_blinker=right))
      self.assertEqual(result["reason"], "hazards_or_no_turn_signal")
      self.assertFalse(result["candidates"])
      self.assertIsNone(result["selected_candidate_id"])

  def test_observation_integrity(self):
    invalid = [{"state_time_s": 98}, {"match_time_s": 98}, {"state_time_s": 101}, {"match_time_s": 101},
               {"accuracy_m": 6}, {"accuracy_m": -1}, {"now_s": math.nan}, {"latitude": math.inf}, {"bearing_deg": 360},
               {"localization_valid": False}, {"can_valid": False}, {"left_blinker": "false"}, {"latitude": 89}]
    for fields in invalid:
      with self.subTest(fields=fields):
        result = build_context(self.osm, replace(self.obs, **fields))
        self.assertEqual(result["status"], "withheld")
        self.assertFalse(result["candidates"])

  def test_wrong_approach_map_match_is_withheld(self):
    for fields in ({"bearing_deg": 90}, {"longitude": 0.0001}, {"latitude": 0.0001}, {"previous_node_id": 6}):
      with self.subTest(fields=fields):
        self.assertEqual(build_context(self.osm, replace(self.obs, **fields))["status"], "withheld")

  def test_oneway_and_access_exclude_roads(self):
    for tags in ({"oneway": "-1"}, {"access": "private"}, {"motor_vehicle": "no"}, {"motorcar": "destination"}):
      with self.subTest(tags=tags):
        self.way(20)["tags"] = {"highway": "residential", **tags}
        self.assertEqual(build_context(self.osm, self.obs)["reason"], "no_supported_turn_candidate")
    self.way(20)["tags"] = {"highway": "residential", "access": "no", "motorcar": "yes"}
    self.assertEqual(build_context(self.osm, self.obs)["selected_candidate_id"], "20:1")

  def test_reverse_osm_way_geometry(self):
    self.way(20)["nodes"].reverse()
    self.way(20)["tags"]["oneway"] = "-1"
    result = build_context(self.osm, self.obs)
    self.assertEqual(result["selected_candidate_id"], "20:-1")
    self.assertEqual(result["candidates"][0]["node_ids"], [2, 4, 5])

  def test_no_turn_restriction(self):
    self.restriction()
    self.assertEqual(build_context(self.osm, self.obs)["reason"], "no_supported_turn_candidate")

  def test_only_turn_restriction(self):
    self.restriction("only_right_turn", to_id=30)
    self.assertEqual(build_context(self.osm, self.obs)["reason"], "no_supported_turn_candidate")
    result = build_context(self.osm, replace(self.obs, left_blinker=False, right_blinker=True))
    self.assertEqual(result["selected_candidate_id"], "30:1")

  def test_vehicle_specific_restriction_and_exemption(self):
    restriction = self.restriction(extra={"restriction:motorcar": "no_left_turn"})
    self.assertEqual(build_context(self.osm, self.obs)["status"], "withheld")
    restriction["tags"]["except"] = "motorcar"
    self.assertEqual(build_context(self.osm, self.obs)["status"], "unique_road_candidate")

  def test_unsupported_restrictions_cannot_be_silently_ignored(self):
    restriction = self.restriction(extra={"restriction:conditional": "no_left_turn @ (Mo-Fr)"})
    self.assertEqual(build_context(self.osm, self.obs)["reason"], "conditional_restriction")
    del restriction["tags"]["restriction:conditional"]
    restriction["members"][1] = {"type": "way", "role": "via", "ref": 20}
    self.assertEqual(build_context(self.osm, self.obs)["reason"], "via_way_or_incomplete_restriction")
    restriction["members"][1] = {"type": "node", "role": "via", "ref": 2}
    restriction["members"][2]["ref"] = 10
    self.assertEqual(build_context(self.osm, self.obs)["reason"], "same_way_restriction")
    restriction["members"].pop(0)
    self.assertEqual(build_context(self.osm, self.obs)["reason"], "incomplete_restriction")

  def test_conditional_access_and_reversible_roads_withhold(self):
    for tags in ({"access:conditional": "no @ (Mo-Fr)"}, {"oneway": "reversible"}, {"oneway": "alternating"}, {"junction": "roundabout"}):
      with self.subTest(tags=tags):
        self.way(20)["tags"] = {"highway": "residential", **tags}
        self.assertEqual(build_context(self.osm, self.obs)["status"], "withheld")

  def test_incomplete_geometry_and_barriers_withhold(self):
    self.way(20)["nodes"].append(999)
    self.assertEqual(build_context(self.osm, self.obs)["reason"], "incomplete_way_geometry")
    self.way(20)["nodes"].pop()
    next(e for e in self.osm["elements"] if e["id"] == 4)["tags"] = {"barrier": "gate"}
    self.assertEqual(build_context(self.osm, self.obs)["reason"], "outgoing_barrier")

  def test_path_stops_at_next_road_junction(self):
    self.osm["elements"].append({"type": "way", "id": 40, "nodes": [4, 6], "tags": {"highway": "residential"}})
    self.assertEqual(build_context(self.osm, self.obs)["candidates"][0]["node_ids"], [2, 4])

  def test_distance_is_bounded_and_not_extrapolated(self):
    next(e for e in self.osm["elements"] if e["id"] == 5)["lon"] = -0.005
    result = build_context(self.osm, self.obs)
    points = result["candidates"][0]["path_xy_m"]
    self.assertAlmostEqual(sum(math.dist(a, b) for a, b in zip(points, points[1:], strict=False)), 80, places=2)

  def test_degenerate_duplicate_and_closed_ways_withhold(self):
    self.way(20)["nodes"].append(2)
    self.assertEqual(build_context(self.osm, self.obs)["reason"], "loop_way_requires_router")
    self.way(20)["nodes"].pop()
    self.osm["elements"].append(copy.deepcopy(self.way(20)))
    self.assertEqual(build_context(self.osm, self.obs)["reason"], "duplicate_way")
    self.osm["elements"].pop()
    for tags in ([], None, {"oneway": True}):
      self.way(20)["tags"] = tags
      self.assertEqual(build_context(self.osm, self.obs)["reason"], "invalid_tags")


if __name__ == "__main__":
  unittest.main()
