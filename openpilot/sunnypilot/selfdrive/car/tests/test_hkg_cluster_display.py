from types import SimpleNamespace
import unittest

from opendbc.car.hyundai.values import CAR, HyundaiFlags
from openpilot.cereal import log
from openpilot.sunnypilot.selfdrive.car.hkg_cluster_display import (
  AssistDisplayStatus,
  CCNC_LCA_ICON_VALUE,
  ClusterFeature,
  ClusterInputs,
  Compatibility,
  DataAvailability,
  Direction,
  FirmwareEvidence,
  LaneChangePhase,
  LaneColor,
  TargetKind,
  TargetObservation,
  VerifiedClusterProfile,
  build_display_state,
  ccnc_lca_icon_values,
  feature_gates,
  is_ev6_hda2_cluster_candidate,
  lane_change_inputs_from_model,
  resolve_verified_profile,
  verified_features_for_car,
)


ALL_FEATURES = frozenset(ClusterFeature)


def car_params(car_fingerprint=CAR.KIA_EV6, flags=HyundaiFlags.CANFD | HyundaiFlags.CANFD_LKA_STEER_MSG,
               brand="hyundai", car_fw=()):
  return SimpleNamespace(carFingerprint=car_fingerprint, flags=flags, brand=brand, carFw=car_fw)


class TestHkgClusterCompatibility(unittest.TestCase):
  def test_only_ev6_hda2_is_a_candidate(self):
    self.assertTrue(is_ev6_hda2_cluster_candidate(car_params()))
    self.assertFalse(is_ev6_hda2_cluster_candidate(car_params(flags=HyundaiFlags.CANFD)))
    self.assertFalse(is_ev6_hda2_cluster_candidate(car_params(car_fingerprint="another Hyundai")))
    self.assertFalse(is_ev6_hda2_cluster_candidate(car_params(brand="toyota")))
    self.assertFalse(is_ev6_hda2_cluster_candidate(None))

  def test_candidate_is_not_a_verified_profile(self):
    CP = car_params()
    self.assertIsNone(resolve_verified_profile(CP))
    self.assertEqual(verified_features_for_car(CP), frozenset())
    self.assertTrue(all(gate.compatibility == Compatibility.UNCONFIRMED for gate in feature_gates(CP).values()))

  def test_profile_requires_exact_firmware_and_documented_evidence(self):
    firmware = SimpleNamespace(address=0x7C6, fwVersion=b"EV6-CLUSTER-A", bus=1)
    profile = VerifiedClusterProfile(
      profile_id="test-only",
      car_fingerprint=CAR.KIA_EV6,
      required_flags=int(HyundaiFlags.CANFD | HyundaiFlags.CANFD_LKA_STEER_MSG),
      status_bus=1,
      object_bus=1,
      features=frozenset({ClusterFeature.LANE_CHANGE_ARROWS}),
      required_firmware=(FirmwareEvidence(0x7C6, b"EV6-CLUSTER-A", 1),),
      evidence=("passive-capture", "synchronized-cluster-video"),
      status_frequency_hz=20.0,
      status_template=(("LKA_ICON", 0),),
      status_template_complete=True,
    )
    self.assertTrue(profile.matches(car_params(car_fw=(firmware,))))
    self.assertFalse(profile.matches(car_params(car_fw=(SimpleNamespace(address=0x7C6, fwVersion=b"OTHER", bus=1),))))

    no_firmware_rule = VerifiedClusterProfile(
      profile_id="unsafe-test-only",
      car_fingerprint=CAR.KIA_EV6,
      required_flags=int(HyundaiFlags.CANFD | HyundaiFlags.CANFD_LKA_STEER_MSG),
      status_bus=1,
      object_bus=1,
      features=frozenset({ClusterFeature.LANE_CHANGE_ARROWS}),
      required_firmware=(),
      evidence=("not-enough",),
    )
    self.assertFalse(no_firmware_rule.matches(car_params(car_fw=(firmware,))))

    no_complete_frame = VerifiedClusterProfile(
      profile_id="unsafe-missing-frame-template",
      car_fingerprint=CAR.KIA_EV6,
      required_flags=int(HyundaiFlags.CANFD | HyundaiFlags.CANFD_LKA_STEER_MSG),
      status_bus=1,
      object_bus=1,
      features=frozenset({ClusterFeature.LANE_CHANGE_ICONS}),
      required_firmware=(FirmwareEvidence(0x7C6, b"EV6-CLUSTER-A", 1),),
      evidence=("passive-capture",),
    )
    self.assertFalse(no_complete_frame.matches(car_params(car_fw=(firmware,))))

  def test_unclassified_model_and_radar_data_cannot_claim_object_type(self):
    gates = feature_gates(car_params())
    for feature in (ClusterFeature.VEHICLE_TARGET, ClusterFeature.PEDESTRIAN_TARGET,
                    ClusterFeature.BICYCLE_TARGET, ClusterFeature.MOTORCYCLE_TARGET,
                    ClusterFeature.CONE_TARGET):
      self.assertEqual(gates[feature].data, DataAvailability.MISSING)
      self.assertFalse(gates[feature].can_activate)


class TestHkgClusterSemanticState(unittest.TestCase):
  def test_master_switch_clears_everything(self):
    data = ClusterInputs(
      lane_change_phase=LaneChangePhase.STARTING,
      lane_change_direction=Direction.LEFT,
      model_valid=True,
      model_age_s=0.0,
      left_lane_probability=1.0,
      right_lane_probability=1.0,
      lateral_active=True,
      navigation_valid=True,
      navigation_age_s=0.0,
      targets=(TargetObservation(1, TargetKind.GENERIC, 10.0, 0.0, 0.0),),
    )
    state = build_display_state(False, ALL_FEATURES, data)
    self.assertFalse(state.left_arrow)
    self.assertFalse(state.navigation_icon)
    self.assertEqual(state.left_lane, LaneColor.HIDDEN)
    self.assertFalse(state.targets)
    self.assertFalse(state.active_features)

  def test_lane_change_arrow_only_during_real_execution(self):
    for phase in (LaneChangePhase.OFF, LaneChangePhase.PREPARING):
      state = build_display_state(True, frozenset({ClusterFeature.LANE_CHANGE_ARROWS}), ClusterInputs(
        lane_change_phase=phase,
        lane_change_direction=Direction.LEFT,
        model_valid=True,
        model_age_s=0.0,
        lateral_active=True,
      ))
      self.assertFalse(state.left_arrow)

    for phase in (LaneChangePhase.STARTING, LaneChangePhase.FINISHING):
      state = build_display_state(True, frozenset({ClusterFeature.LANE_CHANGE_ARROWS}), ClusterInputs(
        lane_change_phase=phase,
        lane_change_direction=Direction.RIGHT,
        model_valid=True,
        model_age_s=0.0,
        lateral_active=True,
      ))
      self.assertFalse(state.left_arrow)
      self.assertTrue(state.right_arrow)

  def test_lca_icons_follow_lateral_and_actual_lane_change_state(self):
    features = frozenset({ClusterFeature.LANE_CHANGE_ICONS})

    inactive = build_display_state(True, features, ClusterInputs(model_valid=True, model_age_s=0.0))
    self.assertEqual(inactive.left_lca_icon, AssistDisplayStatus.HIDDEN)
    self.assertEqual(inactive.right_lca_icon, AssistDisplayStatus.HIDDEN)

    standby = build_display_state(True, features, ClusterInputs(
      model_valid=True, model_age_s=0.0, lateral_active=True,
      lane_change_phase=LaneChangePhase.PREPARING, lane_change_direction=Direction.LEFT,
    ))
    self.assertEqual(standby.left_lca_icon, AssistDisplayStatus.STANDBY)
    self.assertEqual(standby.right_lca_icon, AssistDisplayStatus.STANDBY)

    active = build_display_state(True, features, ClusterInputs(
      model_valid=True, model_age_s=0.0, lateral_active=True,
      lane_change_phase=LaneChangePhase.STARTING, lane_change_direction=Direction.RIGHT,
    ))
    self.assertEqual(active.left_lca_icon, AssistDisplayStatus.STANDBY)
    self.assertEqual(active.right_lca_icon, AssistDisplayStatus.ACTIVE)
    self.assertEqual(ccnc_lca_icon_values(active), {"LCA_LEFT_ICON": 1, "LCA_RIGHT_ICON": 2})

  def test_lca_ready_requires_explicit_signal_and_no_blocker(self):
    features = frozenset({ClusterFeature.LANE_CHANGE_ICONS})
    ready = build_display_state(True, features, ClusterInputs(
      model_valid=True, model_age_s=0.0, lateral_active=True, lane_change_ready=True,
      lane_change_phase=LaneChangePhase.PREPARING, lane_change_direction=Direction.LEFT,
    ))
    self.assertEqual(ready.left_lca_icon, AssistDisplayStatus.READY)

    blocked = build_display_state(True, features, ClusterInputs(
      model_valid=True, model_age_s=0.0, lateral_active=True, lane_change_ready=True,
      lane_change_phase=LaneChangePhase.PREPARING, lane_change_direction=Direction.LEFT,
      left_lane_change_blocked=True,
    ))
    self.assertEqual(blocked.left_lca_icon, AssistDisplayStatus.STANDBY)

  def test_lca_icons_clear_on_stale_cancel_complete_or_pause(self):
    features = frozenset({ClusterFeature.LANE_CHANGE_ICONS})
    base = dict(model_valid=True, model_age_s=0.0, lateral_active=True,
                lane_change_phase=LaneChangePhase.STARTING, lane_change_direction=Direction.LEFT)
    self.assertEqual(build_display_state(True, features, ClusterInputs(**base)).left_lca_icon,
                     AssistDisplayStatus.ACTIVE)
    self.assertEqual(build_display_state(True, features, ClusterInputs(**(base | {"model_age_s": 0.6}))).left_lca_icon,
                     AssistDisplayStatus.HIDDEN)
    self.assertEqual(build_display_state(True, features, ClusterInputs(**(base | {"lateral_active": False}))).left_lca_icon,
                     AssistDisplayStatus.HIDDEN)
    for phase in (LaneChangePhase.OFF, LaneChangePhase.PREPARING):
      state = build_display_state(True, features, ClusterInputs(**(base | {"lane_change_phase": phase})))
      self.assertEqual(state.left_lca_icon, AssistDisplayStatus.STANDBY)

  def test_ccnc_icon_enum_mapping_does_not_invent_flashing_value(self):
    self.assertEqual(CCNC_LCA_ICON_VALUE[AssistDisplayStatus.HIDDEN], 0)
    self.assertEqual(CCNC_LCA_ICON_VALUE[AssistDisplayStatus.STANDBY], 1)
    self.assertEqual(CCNC_LCA_ICON_VALUE[AssistDisplayStatus.READY], 2)
    self.assertEqual(CCNC_LCA_ICON_VALUE[AssistDisplayStatus.ACTIVE], 2)
    self.assertNotIn(3, CCNC_LCA_ICON_VALUE.values())
    self.assertNotIn(4, CCNC_LCA_ICON_VALUE.values())

  def test_shared_modelv2_adapter_preserves_phase_direction_and_blocking(self):
    # stock modeld and modeld_v2 both publish this same modelV2.meta contract.
    model = SimpleNamespace(meta=SimpleNamespace(
      laneChangeState=log.LaneChangeState.preLaneChange,
      laneChangeDirection=log.LaneChangeDirection.right,
    ))
    data = lane_change_inputs_from_model(
      model, lateral_active=True, model_valid=True, model_age_s=0.1,
      right_blocked=True,
    )
    self.assertEqual(data.lane_change_phase, LaneChangePhase.PREPARING)
    self.assertEqual(data.lane_change_direction, Direction.RIGHT)
    self.assertTrue(data.lateral_active)
    self.assertTrue(data.right_lane_change_blocked)
    self.assertIsNone(data.lane_change_ready)

  def test_lane_color_uses_detection_assist_and_real_warning(self):
    features = frozenset({ClusterFeature.LANE_LINES})
    state = build_display_state(True, features, ClusterInputs(
      model_valid=True,
      model_age_s=0.1,
      left_lane_probability=0.9,
      right_lane_probability=0.9,
      lateral_active=True,
      right_lane_warning=True,
    ))
    self.assertEqual(state.left_lane, LaneColor.GREEN)
    self.assertEqual(state.right_lane, LaneColor.ORANGE)

    stale = build_display_state(True, features, ClusterInputs(
      model_valid=True,
      model_age_s=0.6,
      left_lane_probability=1.0,
      right_lane_probability=1.0,
    ))
    self.assertEqual(stale.left_lane, LaneColor.HIDDEN)
    self.assertEqual(stale.right_lane, LaneColor.HIDDEN)

  def test_navigation_requires_valid_fresh_data(self):
    features = frozenset({ClusterFeature.NAVIGATION_ICON})
    self.assertTrue(build_display_state(True, features, ClusterInputs(
      navigation_valid=True, navigation_age_s=2.5,
    )).navigation_icon)
    self.assertFalse(build_display_state(True, features, ClusterInputs(
      navigation_valid=True, navigation_age_s=2.6,
    )).navigation_icon)
    self.assertFalse(build_display_state(True, features, ClusterInputs(
      navigation_valid=False, navigation_age_s=0.0,
    )).navigation_icon)

  def test_targets_require_freshness_range_and_reliable_specific_class(self):
    features = frozenset({ClusterFeature.GENERIC_TARGET, ClusterFeature.VEHICLE_TARGET,
                          ClusterFeature.PEDESTRIAN_TARGET})
    data = ClusterInputs(targets=(
      TargetObservation(1, TargetKind.GENERIC, 15.0, -1.0, 0.1),
      TargetObservation(2, TargetKind.VEHICLE, 10.0, 1.0, 0.1, classification_reliable=False),
      TargetObservation(3, TargetKind.PEDESTRIAN, 20.0, 0.5, 0.1, classification_reliable=True),
      TargetObservation(4, TargetKind.GENERIC, 30.0, 0.0, 0.6),
      TargetObservation(5, TargetKind.GENERIC, 205.0, 0.0, 0.1),
    ))
    state = build_display_state(True, features, data)
    self.assertEqual([target.track_id for target in state.targets], [1, 3])
    self.assertNotIn(ClusterFeature.VEHICLE_TARGET, state.active_features)
    self.assertIn(ClusterFeature.PEDESTRIAN_TARGET, state.active_features)

  def test_no_verified_features_means_no_display_even_when_user_enabled(self):
    state = build_display_state(True, frozenset(), ClusterInputs(
      lane_change_phase=LaneChangePhase.STARTING,
      lane_change_direction=Direction.LEFT,
      navigation_valid=True,
      navigation_age_s=0.0,
    ))
    self.assertEqual(state, type(state)())


if __name__ == "__main__":
  unittest.main()
