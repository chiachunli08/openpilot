import unittest
from types import SimpleNamespace

from openpilot.cereal import log
from openpilot.sunnypilot.navd.navigation_intent import NavigationIntentController, classify_maneuver, trigger_window
from openpilot.sunnypilot.navd.navigation_model_compat import (TACO2_DRIVING_MODEL_SHA256, TACO2_NAV_FEATURE_CONTRACT,
                                                               navigation_feature_key, navigation_features_fresh,
                                                               verified_navigation_contract)


class TestNavigationIntent(unittest.TestCase):
  def test_exact_maneuver_classification(self):
    self.assertEqual(classify_maneuver("turn", "sharp left").desire, log.Desire.turnLeft)
    self.assertEqual(classify_maneuver("off ramp", "slight right").desire, log.Desire.keepRight)
    self.assertEqual(classify_maneuver("lane change", "left").desire, log.Desire.laneChangeLeft)
    self.assertIsNone(classify_maneuver("arrive", "right"))
    self.assertIsNone(classify_maneuver("notification", "bear-left-ish"))
    self.assertEqual(classify_maneuver("turn", "uturn", is_rhd=True).desire, log.Desire.turnRight)

  def test_speed_scaled_window(self):
    low = trigger_window("turn", 3.0)
    high = trigger_window("turn", 30.0)
    self.assertGreater(high[1], low[1])
    self.assertLessEqual(high[1], 240.0)
    self.assertGreater(trigger_window("keep", 20.0)[1], trigger_window("turn", 20.0)[1])

  def test_pulse_dedup_and_conflict(self):
    nav = SimpleNamespace(maneuverType="turn", maneuverModifier="right", maneuverDistance=70.0)
    controller = NavigationIntentController()
    kwargs = dict(base_desire=log.Desire.none, enabled=True, nav_valid=True, nav=nav,
                  instruction_age_sec=0.5, v_ego=10.0, maneuver_id="route:2", route_id="route")
    first = controller.update(**kwargs)
    self.assertTrue(first.pulse_sent)
    self.assertEqual(first.desire, log.Desire.turnRight)
    self.assertEqual(controller.update(**kwargs).reason, "alreadySent")

    conflict = controller.update(**(kwargs | {"maneuver_id": "route:3", "driver_conflict": True}))
    self.assertFalse(conflict.pulse_sent)
    self.assertEqual(conflict.reason, "driverInput")

    matching_signal = controller.update(**(kwargs | {"maneuver_id": "route:4", "driver_direction": "right"}))
    self.assertTrue(matching_signal.pulse_sent)
    opposite_signal = controller.update(**(kwargs | {"maneuver_id": "route:5", "driver_direction": "left"}))
    self.assertFalse(opposite_signal.pulse_sent)
    self.assertEqual(opposite_signal.reason, "driverInput")

  def test_stale_and_wrong_type_do_not_pulse(self):
    nav = SimpleNamespace(maneuverType="turn", maneuverModifier="left", maneuverDistance=60.0)
    controller = NavigationIntentController()
    stale = controller.update(base_desire=log.Desire.none, enabled=True, nav_valid=True, nav=nav,
                              instruction_age_sec=3.0, v_ego=10.0, maneuver_id="a")
    self.assertEqual(stale.reason, "staleInstruction")
    nav.maneuverType = "arrive"
    unsupported = controller.update(base_desire=log.Desire.none, enabled=True, nav_valid=True, nav=nav,
                                    instruction_age_sec=0.1, v_ego=10.0, maneuver_id="b")
    self.assertEqual(unsupported.reason, "unsupportedManeuver")

  def test_model_contract_gate(self):
    shapes = {"img": [1, 12, 128, 256], "nav_features": [1, 64]}
    self.assertIsNone(navigation_feature_key(shapes))
    self.assertEqual(navigation_feature_key(shapes, TACO2_NAV_FEATURE_CONTRACT), "nav_features")
    self.assertIsNone(navigation_feature_key({"nav_features": [1, 63]}))
    self.assertIsNone(navigation_feature_key({"features_buffer": [1, 64]}))
    self.assertEqual(verified_navigation_contract(input_shapes=shapes,
                                                   model_sha256=TACO2_DRIVING_MODEL_SHA256),
                     TACO2_NAV_FEATURE_CONTRACT)
    self.assertEqual(verified_navigation_contract(input_shapes=shapes, declared_contract="made-up"), "")
    self.assertTrue(navigation_features_fresh(1_000_000_000, 2_000_000_000))
    self.assertFalse(navigation_features_fresh(1_000_000_000, 4_000_000_000))


if __name__ == "__main__":
  unittest.main()
