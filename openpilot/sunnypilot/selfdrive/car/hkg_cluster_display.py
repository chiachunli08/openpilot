"""Safety gates for optional Hyundai/Kia stock-cluster extensions.

This module deliberately separates normal semantic display intent from a narrow
parked research sender. Normal CCNC output still requires an exact verified
profile; the one-shot test has independent application and Panda interlocks.
The common DBC alone is not compatibility evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from opendbc.can import CANPacker
from opendbc.car import Bus, structs
from opendbc.car.hyundai.hyundaicanfd import CanBus
from opendbc.car.hyundai.values import CAR, DBC, HyundaiFlags
from openpilot.cereal import log
from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog


CCNC_STATUS_ADDRESS = 0x161
CCNC_OBJECTS_ADDRESS = 0x162
LFAHDA_CLUSTER_ADDRESS = 0x1E0
EXPECTED_PAYLOAD_BYTES = {
  CCNC_STATUS_ADDRESS: 32,
  CCNC_OBJECTS_ADDRESS: 32,
  LFAHDA_CLUSTER_ADDRESS: 16,
}

HKG_CLUSTER_PERMISSION_PARAM = "HkgStockClusterDisplay"
HKG_CLUSTER_TEST_PARAM = "HkgStockClusterDisplayTest"
HKG_CLUSTER_TEST_STATUS_PARAM = "HkgStockClusterDisplayTestStatus"
HKG_LCA_ICONS_PARAM = "HkgLaneChangeAssistIcons"
HKG_LCA_ICONS_STATUS_PARAM = "HkgLaneChangeAssistIconsStatus"

# The CCNC_0x161/0x162 definitions entered the common DBC through research on
# 2023-24 Palisade/Telluride HDA2 vehicles. This is not an EV6 support claim.
DBC_RESEARCH_SOURCE = "https://github.com/commaai/opendbc/pull/1269"


class ClusterFeature(StrEnum):
  LANE_CHANGE_ICONS = "lane_change_icons"
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


class AssistDisplayStatus(StrEnum):
  """Vehicle-independent lane-change-assist display semantics."""

  HIDDEN = "hidden"
  STANDBY = "standby"
  READY = "ready"
  ACTIVE = "active"


# Verified CCNC_0x161 enum values. READY and ACTIVE intentionally use the same
# steady green icon: no public evidence establishes a separate flashing value.
CCNC_LCA_ICON_VALUE = {
  AssistDisplayStatus.HIDDEN: 0,
  AssistDisplayStatus.STANDBY: 1,
  AssistDisplayStatus.READY: 2,
  AssistDisplayStatus.ACTIVE: 2,
}


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
  status_frequency_hz: float = 0.0
  status_template: tuple[tuple[str, float], ...] = ()
  status_template_complete: bool = False

  def matches(self, CP: Any) -> bool:
    car_fw = tuple(CP.carFw)
    firmware_matches = bool(self.required_firmware) and all(
      any(requirement.matches(fw) for fw in car_fw) for requirement in self.required_firmware
    )
    status_features = {ClusterFeature.LANE_CHANGE_ICONS, ClusterFeature.LANE_CHANGE_ARROWS,
                       ClusterFeature.LANE_LINES, ClusterFeature.NAVIGATION_ICON}
    status_frame_verified = not bool(self.features & status_features) or (
      self.status_frequency_hz > 0.0 and bool(self.status_template) and self.status_template_complete
    )
    return (CP.carFingerprint == self.car_fingerprint and
            int(CP.flags) & self.required_flags == self.required_flags and
            firmware_matches and bool(self.evidence) and status_frame_verified)


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
  lane_change_ready: bool | None = None
  left_lane_change_blocked: bool = False
  right_lane_change_blocked: bool = False
  left_lane_warning: bool = False
  right_lane_warning: bool = False
  navigation_valid: bool = False
  navigation_age_s: float = float("inf")
  targets: tuple[TargetObservation, ...] = ()


@dataclass(frozen=True)
class ClusterDisplayState:
  left_lca_icon: AssistDisplayStatus = AssistDisplayStatus.HIDDEN
  right_lca_icon: AssistDisplayStatus = AssistDisplayStatus.HIDDEN
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
    ClusterFeature.LANE_CHANGE_ICONS: DataAvailability.AVAILABLE,
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
  model_fresh = data.model_valid and 0.0 <= data.model_age_s <= model_timeout_s

  left_lca_icon = right_lca_icon = AssistDisplayStatus.HIDDEN
  if ClusterFeature.LANE_CHANGE_ICONS in verified_features and model_fresh and data.lateral_active:
    left_lca_icon = right_lca_icon = AssistDisplayStatus.STANDBY
    direction_blocked = ((data.lane_change_direction == Direction.LEFT and data.left_lane_change_blocked) or
                         (data.lane_change_direction == Direction.RIGHT and data.right_lane_change_blocked))
    executing = data.lane_change_phase in (LaneChangePhase.STARTING, LaneChangePhase.FINISHING)
    explicitly_ready = data.lane_change_phase == LaneChangePhase.PREPARING and data.lane_change_ready is True
    if executing or (explicitly_ready and not direction_blocked):
      status = AssistDisplayStatus.ACTIVE if executing else AssistDisplayStatus.READY
      if data.lane_change_direction == Direction.LEFT:
        left_lca_icon = status
      elif data.lane_change_direction == Direction.RIGHT:
        right_lca_icon = status
    active_features.add(ClusterFeature.LANE_CHANGE_ICONS)

  left_arrow = right_arrow = False
  if ClusterFeature.LANE_CHANGE_ARROWS in verified_features and model_fresh and data.lateral_active:
    executing = data.lane_change_phase in (LaneChangePhase.STARTING, LaneChangePhase.FINISHING)
    left_arrow = executing and data.lane_change_direction == Direction.LEFT
    right_arrow = executing and data.lane_change_direction == Direction.RIGHT
    if left_arrow or right_arrow:
      active_features.add(ClusterFeature.LANE_CHANGE_ARROWS)

  left_lane = right_lane = LaneColor.HIDDEN
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
    left_lca_icon=left_lca_icon,
    right_lca_icon=right_lca_icon,
    left_arrow=left_arrow,
    right_arrow=right_arrow,
    left_lane=left_lane,
    right_lane=right_lane,
    navigation_icon=navigation_icon,
    targets=tuple(selected_targets),
    active_features=frozenset(active_features),
  )


def ccnc_lca_icon_values(state: ClusterDisplayState) -> dict[str, int]:
  """Map semantic state to only the two verified CCNC icon fields.

  This helper does not create a complete 0x161 payload. Callers must not pack or
  transmit these values without an exact verified profile, a captured full-frame
  template, collision handling, and an independent Panda safety authorization.
  """
  return {
    "LCA_LEFT_ICON": CCNC_LCA_ICON_VALUE[state.left_lca_icon],
    "LCA_RIGHT_ICON": CCNC_LCA_ICON_VALUE[state.right_lca_icon],
  }


def lane_change_inputs_from_model(model_v2: Any, *, lateral_active: bool, model_valid: bool,
                                  model_age_s: float, left_blocked: bool = False,
                                  right_blocked: bool = False,
                                  lane_change_ready: bool | None = None) -> ClusterInputs:
  """Normalize the shared stock/modeld_v2 modelV2 metadata into display input.

  Both model execution paths publish these cereal enums. `lane_change_ready`
  deliberately defaults to unknown because neither path currently publishes the
  AutoLaneChangeController's internal readiness decision.
  """
  phase_map = {
    log.LaneChangeState.off: LaneChangePhase.OFF,
    log.LaneChangeState.preLaneChange: LaneChangePhase.PREPARING,
    log.LaneChangeState.laneChangeStarting: LaneChangePhase.STARTING,
    log.LaneChangeState.laneChangeFinishing: LaneChangePhase.FINISHING,
  }
  direction_map = {
    log.LaneChangeDirection.none: Direction.NONE,
    log.LaneChangeDirection.left: Direction.LEFT,
    log.LaneChangeDirection.right: Direction.RIGHT,
  }
  meta = model_v2.meta
  return ClusterInputs(
    lane_change_phase=phase_map.get(meta.laneChangeState, LaneChangePhase.OFF),
    lane_change_direction=direction_map.get(meta.laneChangeDirection, Direction.NONE),
    model_valid=model_valid,
    model_age_s=model_age_s,
    lateral_active=lateral_active,
    lane_change_ready=lane_change_ready,
    left_lane_change_blocked=left_blocked,
    right_lane_change_blocked=right_blocked,
  )


@dataclass(frozen=True)
class ClusterTestPage:
  """One synthetic, display-only page in the guarded stationary test."""

  name: str
  duration_s: float
  status_values: tuple[tuple[str, float], ...] = ()


NEUTRAL_STATUS_VALUES: dict[str, float] = {
  "LCA_LEFT_ARROW": 0,
  "LCA_RIGHT_ARROW": 0,
  "CENTERLINE": 0,
  "TARGET": 0,
  "TARGET_DISTANCE": 0,
  "LANELINE_LEFT": 1,
  "LANELINE_LEFT_POSITION": 15,
  "LANELINE_RIGHT": 1,
  "LANELINE_RIGHT_POSITION": 15,
  "LANELINE_CURVATURE": 15,
  "LANE_HIGHLIGHT": 0,
  "LANE_HIGHLIGHT_DISTANCE": 0,
  "LANE_LEFT": 0,
  "LANE_RIGHT": 0,
  "LANE_ZOOM": 1,
  "HDA_ICON": 0,
  "NAV_ICON": 0,
  "LFA_ICON": 0,
  "LCA_LEFT_ICON": 0,
  "LCA_RIGHT_ICON": 0,
}

def _test_page(name: str, *, status: dict[str, float] | None = None,
               duration_s: float = 3.0) -> ClusterTestPage:
  return ClusterTestPage(name, duration_s, tuple((status or {}).items()))


# Each page intentionally leaves collision/AEB, fault, alert, sound, speed-limit,
# DAW, vibration, and unknown fields at zero. Panda independently enforces this
# restricted subset and rejects payloads that escape it.
HKG_CLUSTER_TEST_PAGES: tuple[ClusterTestPage, ...] = (
  _test_page("clear_start"),
  _test_page("left_lane_change", status={
    "LCA_LEFT_ARROW": 1, "LCA_LEFT_ICON": 2, "LANELINE_LEFT": 6, "LANELINE_RIGHT": 2,
  }),
  _test_page("right_lane_change", status={
    "LCA_RIGHT_ARROW": 1, "LCA_RIGHT_ICON": 2, "LANELINE_LEFT": 2, "LANELINE_RIGHT": 6,
  }),
  _test_page("lane_lines_white", status={
    "CENTERLINE": 1, "LANELINE_LEFT": 2, "LANELINE_RIGHT": 2, "LANE_HIGHLIGHT": 2,
    "LANE_HIGHLIGHT_DISTANCE": 50, "LANE_LEFT": 1, "LANE_RIGHT": 1, "LANE_ZOOM": 0,
  }),
  _test_page("lane_lines_green", status={
    "CENTERLINE": 1, "LANELINE_LEFT": 6, "LANELINE_RIGHT": 6, "LANE_HIGHLIGHT": 1,
    "LANE_HIGHLIGHT_DISTANCE": 50, "LANE_LEFT": 1, "LANE_RIGHT": 1, "LANE_ZOOM": 0,
    "HDA_ICON": 2, "LFA_ICON": 2,
  }),
  _test_page("lane_lines_orange", status={
    "CENTERLINE": 1, "LANELINE_LEFT": 4, "LANELINE_RIGHT": 4, "LANE_HIGHLIGHT": 4,
    "LANE_HIGHLIGHT_DISTANCE": 50, "LANE_LEFT": 1, "LANE_RIGHT": 1, "LANE_ZOOM": 0,
  }),
  _test_page("navigation_gray", status={"NAV_ICON": 1, "HDA_ICON": 1, "LFA_ICON": 1}),
  _test_page("navigation_green", status={"NAV_ICON": 2, "HDA_ICON": 2, "LFA_ICON": 2}),
  _test_page("navigation_white", status={"NAV_ICON": 4, "HDA_ICON": 3, "LFA_ICON": 3}),
  _test_page("clear_end"),
)


def cluster_test_page_values(page: ClusterTestPage) -> dict[str, float]:
  status = dict(NEUTRAL_STATUS_VALUES)
  status.update(page.status_values)
  return status


class HkgClusterDisplayTestController:
  """One-shot active display test with application-level interlocks.

  This controller is deliberately outside the normal Hyundai actuation path. It
  sends only while an initialization-time safety flag is present, then disables
  the local one-shot request on completion or any abort.
  """

  SAFE_OBSERVATION_NS = 2_000_000_000
  WAIT_TIMEOUT_NS = 120_000_000_000
  SEND_INTERVAL_NS = 50_000_000  # 20 Hz, matching public CCNC implementations

  def __init__(self, CP: Any, params: Params | Any | None = None, packer: CANPacker | Any | None = None):
    self.CP = CP
    self.params = params or Params()
    vehicle_safety_active = bool(CP.safetyConfigs and
                                 CP.safetyConfigs[-1].safetyModel == structs.CarParams.SafetyModel.hyundaiCanfd)
    self.enabled = bool(is_ev6_hda2_cluster_candidate(CP) and CP.flags & HyundaiFlags.EV and
                        CP.flags & HyundaiFlags.CANFD_HKG_CLUSTER_TEST and not CP.passive and vehicle_safety_active)
    self.CAN = CanBus(CP) if self.enabled else None
    self.packer = packer or (CANPacker(DBC[CP.carFingerprint][Bus.pt]) if self.enabled else None)
    self.first_update_nanos: int | None = None
    self.safe_since_nanos: int | None = None
    self.test_started_nanos: int | None = None
    self.last_send_nanos: int | None = None
    self.page_index = -1
    self.done = not self.enabled
    self.status = "not_armed" if not self.enabled else "armed_waiting_for_park"
    if self.enabled:
      self._set_status(self.status)
    elif self.params.get_bool(HKG_CLUSTER_TEST_PARAM):
      self.params.put_bool(HKG_CLUSTER_TEST_PARAM, False)
      self.status = "not_armed_incompatible_or_passive"
      self.params.put(HKG_CLUSTER_TEST_STATUS_PARAM, self.status)

  def _set_status(self, status: str) -> None:
    if status == self.status and self.params.get(HKG_CLUSTER_TEST_STATUS_PARAM) == status:
      return
    self.status = status
    self.params.put(HKG_CLUSTER_TEST_STATUS_PARAM, status)

  def _finish(self, status: str) -> None:
    if self.done:
      return
    self.done = True
    self._set_status(status)
    self.params.put_bool(HKG_CLUSTER_TEST_PARAM, False)
    if status == "complete":
      cloudlog.warning("HKG stock-cluster display test completed")
    else:
      cloudlog.error({"event": "HKG stock-cluster display test stopped", "reason": status})

  @staticmethod
  def _received_cluster_message(can_packets: Any) -> tuple[int, int] | None:
    for _, frames in can_packets or ():
      for address, _, source_bus in frames:
        if address in (CCNC_STATUS_ADDRESS, CCNC_OBJECTS_ADDRESS) and 0 <= source_bus < 128:
          return int(address), int(source_bus)
    return None

  @staticmethod
  def _safe_vehicle_state(CS: Any, CC: Any) -> bool:
    return bool(CS.canValid and CS.standstill and abs(float(CS.vEgoRaw)) <= 0.1 and
                CS.gearShifter == structs.CarState.GearShifter.park and not CS.gasPressed and
                not CC.enabled and not CC.latActive and not CC.longActive)

  @staticmethod
  def _page_at(elapsed_s: float) -> tuple[int, ClusterTestPage] | None:
    boundary = 0.0
    for index, page in enumerate(HKG_CLUSTER_TEST_PAGES):
      boundary += page.duration_s
      if elapsed_s < boundary:
        return index, page
    return None

  def update(self, CS: Any, CC: Any, can_packets: Any, now_nanos: int) -> list[tuple[int, bytes, int]]:
    if self.done:
      return []

    if not self.params.get_bool(HKG_CLUSTER_PERMISSION_PARAM) or not self.params.get_bool(HKG_CLUSTER_TEST_PARAM):
      self._finish("cancelled_setting_disabled")
      return []

    if self.first_update_nanos is None:
      self.first_update_nanos = now_nanos

    collision = self._received_cluster_message(can_packets)
    if collision is not None:
      self._finish(f"aborted_stock_{collision[0]:#x}_on_bus_{collision[1]}")
      return []

    safe = self._safe_vehicle_state(CS, CC)
    if self.test_started_nanos is not None and not safe:
      self._finish("aborted_vehicle_interlock")
      return []

    if self.test_started_nanos is None:
      if now_nanos - self.first_update_nanos >= self.WAIT_TIMEOUT_NS:
        self._finish("aborted_wait_timeout")
        return []
      if not safe:
        self.safe_since_nanos = None
        self._set_status("waiting_require_park_standstill_disengaged")
        return []
      if self.safe_since_nanos is None:
        self.safe_since_nanos = now_nanos
      if now_nanos - self.safe_since_nanos < self.SAFE_OBSERVATION_NS:
        self._set_status("observing_for_stock_message_conflict")
        return []
      self.test_started_nanos = now_nanos
      self.last_send_nanos = None

    elapsed_s = (now_nanos - self.test_started_nanos) * 1e-9
    selected = self._page_at(elapsed_s)
    if selected is None:
      self._finish("complete")
      return []

    page_index, page = selected
    if page_index != self.page_index:
      self.page_index = page_index
      self._set_status(f"running_{page_index + 1:02d}_of_{len(HKG_CLUSTER_TEST_PAGES):02d}_{page.name}")

    if self.last_send_nanos is not None and now_nanos - self.last_send_nanos < self.SEND_INTERVAL_NS:
      return []
    self.last_send_nanos = now_nanos

    status_values = cluster_test_page_values(page)
    assert self.CAN is not None and self.packer is not None
    return [
      self.packer.make_can_msg("CCNC_0x161", self.CAN.ECAN, status_values),
    ]
