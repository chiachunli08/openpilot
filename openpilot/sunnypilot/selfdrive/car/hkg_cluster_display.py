"""Safety gates for optional Hyundai/Kia stock-cluster extensions.

This module deliberately separates semantic display intent from CAN packing.
No CCNC message may be sent unless an exact, vehicle-verified profile resolves.
The common DBC alone is not compatibility evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from opendbc.car.hyundai.values import CAR, HyundaiFlags


CCNC_STATUS_ADDRESS = 0x161
CCNC_OBJECTS_ADDRESS = 0x162
LFAHDA_CLUSTER_ADDRESS = 0x1E0
EXPECTED_PAYLOAD_BYTES = {
  CCNC_STATUS_ADDRESS: 32,
  CCNC_OBJECTS_ADDRESS: 32,
  LFAHDA_CLUSTER_ADDRESS: 16,
}

# The CCNC_0x161/0x162 definitions entered the common DBC through research on
# 2023-24 Palisade/Telluride HDA2 vehicles. This is not an EV6 support claim.
DBC_RESEARCH_SOURCE = "https://github.com/commaai/opendbc/pull/1269"


class ClusterFeature(StrEnum):
  LANE_CHANGE_ARROWS = "lane_change_arrows"
  LANE_LINES = "lane_lines"
  NAVIGATION_ICON = "navigation_icon"
  GENERIC_TARGET = "generic_target"
  VEHICLE_TARGET = "vehicle_target"
  PEDESTRIAN_TARGET = "pedestrian_target"
  BICYCLE_TARGET = "bicycle_target"
  MOTORCYCLE_TARGET = "motorcycle_target"
  CONE_TARGET = "cone_target"


class Compatibility(StrEnum):
  VERIFIED = "verified"
  UNCONFIRMED = "unconfirmed"
  NOT_APPLICABLE = "not_applicable"


class DataAvailability(StrEnum):
  AVAILABLE = "available"
  CONDITIONAL = "conditional"
  MISSING = "missing"


class LaneChangePhase(StrEnum):
  OFF = "off"
  PREPARING = "preparing"
  STARTING = "starting"
  FINISHING = "finishing"


class Direction(StrEnum):
  NONE = "none"
  LEFT = "left"
  RIGHT = "right"


class LaneColor(StrEnum):
  HIDDEN = "hidden"
  WHITE = "white"
  GREEN = "green"
  ORANGE = "orange"


class TargetKind(StrEnum):
  GENERIC = "generic"
  VEHICLE = "vehicle"
  PEDESTRIAN = "pedestrian"
  BICYCLE = "bicycle"
  MOTORCYCLE = "motorcycle"
  CONE = "cone"


TARGET_FEATURE = {
  TargetKind.GENERIC: ClusterFeature.GENERIC_TARGET,
  TargetKind.VEHICLE: ClusterFeature.VEHICLE_TARGET,
  TargetKind.PEDESTRIAN: ClusterFeature.PEDESTRIAN_TARGET,
  TargetKind.BICYCLE: ClusterFeature.BICYCLE_TARGET,
  TargetKind.MOTORCYCLE: ClusterFeature.MOTORCYCLE_TARGET,
  TargetKind.CONE: ClusterFeature.CONE_TARGET,
}


@dataclass(frozen=True)
class FirmwareEvidence:
  address: int
  fw_version: bytes
  bus: int | None = None

  def matches(self, car_fw: Any) -> bool:
    return (int(car_fw.address) == self.address and bytes(car_fw.fwVersion) == self.fw_version and
            (self.bus is None or int(car_fw.bus) == self.bus))


@dataclass(frozen=True)
class VerifiedClusterProfile:
  """An exact vehicle profile backed by passive captures and cluster testing.

  Adding an entry is intentionally not enough to transmit CAN: the corresponding
  packer, bus route, and minimal Panda allowlist must be reviewed together.
  """

  profile_id: str
  car_fingerprint: Any
  required_flags: int
  status_bus: int
  object_bus: int
  features: frozenset[ClusterFeature]
  required_firmware: tuple[FirmwareEvidence, ...]
  evidence: tuple[str, ...]

  def matches(self, CP: Any) -> bool:
    car_fw = tuple(CP.carFw)
    firmware_matches = bool(self.required_firmware) and all(
      any(requirement.matches(fw) for fw in car_fw) for requirement in self.required_firmware
    )
    return (CP.carFingerprint == self.car_fingerprint and
            int(CP.flags) & self.required_flags == self.required_flags and
            firmware_matches and bool(self.evidence))


# No EV6 0x161/0x162 profile has been verified. Keep this empty until an exact
# cluster/head-unit version, received bus, payload, rate, counter/checksum, and
# field-to-screen correlation have all been demonstrated.
VERIFIED_PROFILES: tuple[VerifiedClusterProfile, ...] = ()


@dataclass(frozen=True)
class FeatureGate:
  compatibility: Compatibility
  data: DataAvailability
  reason: str

  @property
  def can_activate(self) -> bool:
    return self.compatibility == Compatibility.VERIFIED and self.data != DataAvailability.MISSING


@dataclass(frozen=True)
class TargetObservation:
  track_id: int
  kind: TargetKind
  distance_m: float
  lateral_m: float
  age_s: float
  valid: bool = True
  classification_reliable: bool = False


@dataclass(frozen=True)
class ClusterInputs:
  lane_change_phase: LaneChangePhase = LaneChangePhase.OFF
  lane_change_direction: Direction = Direction.NONE
  model_valid: bool = False
  model_age_s: float = float("inf")
  left_lane_probability: float = 0.0
  right_lane_probability: float = 0.0
  lateral_active: bool = False
  left_lane_warning: bool = False
  right_lane_warning: bool = False
  navigation_valid: bool = False
  navigation_age_s: float = float("inf")
  targets: tuple[TargetObservation, ...] = ()


@dataclass(frozen=True)
class ClusterDisplayState:
  left_arrow: bool = False
  right_arrow: bool = False
  left_lane: LaneColor = LaneColor.HIDDEN
  right_lane: LaneColor = LaneColor.HIDDEN
  navigation_icon: bool = False
  targets: tuple[TargetObservation, ...] = ()
  active_features: frozenset[ClusterFeature] = field(default_factory=frozenset)


def is_ev6_hda2_cluster_candidate(CP: Any | None) -> bool:
  """Return candidate status only; this does not mean transmission is safe."""
  return bool(CP is not None and CP.brand == "hyundai" and CP.carFingerprint == CAR.KIA_EV6 and
              CP.flags & HyundaiFlags.CANFD and CP.flags & HyundaiFlags.CANFD_LKA_STEER_MSG)


def resolve_verified_profile(CP: Any | None) -> VerifiedClusterProfile | None:
  if not is_ev6_hda2_cluster_candidate(CP):
    return None
  return next((profile for profile in VERIFIED_PROFILES if profile.matches(CP)), None)


def verified_features_for_car(CP: Any | None) -> frozenset[ClusterFeature]:
  profile = resolve_verified_profile(CP)
  return profile.features if profile is not None else frozenset()


def feature_gates(CP: Any | None) -> dict[ClusterFeature, FeatureGate]:
  candidate = is_ev6_hda2_cluster_candidate(CP)
  verified = verified_features_for_car(CP)
  compatibility = Compatibility.UNCONFIRMED if candidate else Compatibility.NOT_APPLICABLE

  data_status = {
    ClusterFeature.LANE_CHANGE_ARROWS: DataAvailability.AVAILABLE,
    ClusterFeature.LANE_LINES: DataAvailability.CONDITIONAL,
    ClusterFeature.NAVIGATION_ICON: DataAvailability.CONDITIONAL,
    ClusterFeature.GENERIC_TARGET: DataAvailability.CONDITIONAL,
    # modelV2/radarState do not expose reliable classes for these shapes.
    ClusterFeature.VEHICLE_TARGET: DataAvailability.MISSING,
    ClusterFeature.PEDESTRIAN_TARGET: DataAvailability.MISSING,
    ClusterFeature.BICYCLE_TARGET: DataAvailability.MISSING,
    ClusterFeature.MOTORCYCLE_TARGET: DataAvailability.MISSING,
    ClusterFeature.CONE_TARGET: DataAvailability.MISSING,
  }

  gates: dict[ClusterFeature, FeatureGate] = {}
  for feature in ClusterFeature:
    feature_compatibility = Compatibility.VERIFIED if feature in verified else compatibility
    if data_status[feature] == DataAvailability.MISSING:
      reason = "reliable object classification is not present in modelV2 or radarState"
    elif feature_compatibility == Compatibility.UNCONFIRMED:
      reason = "EV6 cluster/head-unit compatibility and the 0x161/0x162 bus have not been verified"
    elif feature_compatibility == Compatibility.NOT_APPLICABLE:
      reason = "requires a fingerprinted Kia EV6 HDA2 CAN-FD platform"
    else:
      reason = "verified profile; activation still requires fresh valid source data"
    gates[feature] = FeatureGate(feature_compatibility, data_status[feature], reason)
  return gates


def _lane_color(detected: bool, active: bool, warning: bool) -> LaneColor:
  if not detected:
    return LaneColor.HIDDEN
  if warning:
    return LaneColor.ORANGE
  return LaneColor.GREEN if active else LaneColor.WHITE


def build_display_state(user_enabled: bool, verified_features: frozenset[ClusterFeature], data: ClusterInputs,
                        model_timeout_s: float = 0.5, navigation_timeout_s: float = 2.5,
                        target_timeout_s: float = 0.5, lane_probability_threshold: float = 0.5,
                        max_targets: int = 4) -> ClusterDisplayState:
  """Build semantic display intent; this function never packs or transmits CAN."""
  if not user_enabled:
    return ClusterDisplayState()

  active_features: set[ClusterFeature] = set()
  left_arrow = right_arrow = False
  if ClusterFeature.LANE_CHANGE_ARROWS in verified_features:
    executing = data.lane_change_phase in (LaneChangePhase.STARTING, LaneChangePhase.FINISHING)
    left_arrow = executing and data.lane_change_direction == Direction.LEFT
    right_arrow = executing and data.lane_change_direction == Direction.RIGHT
    if left_arrow or right_arrow:
      active_features.add(ClusterFeature.LANE_CHANGE_ARROWS)

  left_lane = right_lane = LaneColor.HIDDEN
  model_fresh = data.model_valid and 0.0 <= data.model_age_s <= model_timeout_s
  if ClusterFeature.LANE_LINES in verified_features and model_fresh:
    left_detected = data.left_lane_probability >= lane_probability_threshold
    right_detected = data.right_lane_probability >= lane_probability_threshold
    left_lane = _lane_color(left_detected, data.lateral_active, data.left_lane_warning)
    right_lane = _lane_color(right_detected, data.lateral_active, data.right_lane_warning)
    if left_lane != LaneColor.HIDDEN or right_lane != LaneColor.HIDDEN:
      active_features.add(ClusterFeature.LANE_LINES)

  navigation_icon = (ClusterFeature.NAVIGATION_ICON in verified_features and data.navigation_valid and
                     0.0 <= data.navigation_age_s <= navigation_timeout_s)
  if navigation_icon:
    active_features.add(ClusterFeature.NAVIGATION_ICON)

  selected_targets: list[TargetObservation] = []
  for target in sorted(data.targets, key=lambda item: (item.distance_m, item.track_id)):
    feature = TARGET_FEATURE[target.kind]
    if feature not in verified_features or not target.valid or not (0.0 <= target.age_s <= target_timeout_s):
      continue
    if target.kind != TargetKind.GENERIC and not target.classification_reliable:
      continue
    if not (0.0 <= target.distance_m <= 204.7):
      continue
    selected_targets.append(target)
    active_features.add(feature)
    if len(selected_targets) >= max_targets:
      break

  return ClusterDisplayState(
    left_arrow=left_arrow,
    right_arrow=right_arrow,
    left_lane=left_lane,
    right_lane=right_lane,
    navigation_icon=navigation_icon,
    targets=tuple(selected_targets),
    active_features=frozenset(active_features),
  )
