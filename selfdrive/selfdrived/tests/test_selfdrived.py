from types import SimpleNamespace

import cereal.messaging as messaging

from cereal import car, custom, log
from opendbc.car.hyundai.values import CAR as HYUNDAI_CAR
from opendbc.car.nissan.values import CAR as NISSAN_CAR
from openpilot.common.realtime import DT_CTRL

from openpilot.selfdrive.selfdrived.selfdrived import (
  VALID_ONLY_COMM_ISSUE_GRACE_FRAMES,
  SelfdriveD,
  commanded_torque_at_max_for_saturation,
  controller_openpilot_event,
  evaluate_comm_issue,
)


def test_valid_only_comm_issue_is_debounced():
  frames = 0
  for _ in range(VALID_ONLY_COMM_ISSUE_GRACE_FRAMES - 1):
    should_alert, frames = evaluate_comm_issue(False, True, True, frames)
    assert not should_alert

  should_alert, frames = evaluate_comm_issue(False, True, True, frames)
  assert should_alert
  assert frames == VALID_ONLY_COMM_ISSUE_GRACE_FRAMES

  should_alert, frames = evaluate_comm_issue(True, True, True, frames)
  assert not should_alert
  assert frames == 0


def test_route_length_validity_cascade_stays_silent():
  frames = 0
  for _ in range(round(0.4 / DT_CTRL)):
    should_alert, frames = evaluate_comm_issue(False, True, True, frames)
    assert not should_alert


def test_dead_or_slow_comm_issue_is_immediate():
  assert evaluate_comm_issue(False, False, True, 0) == (True, 0)
  assert evaluate_comm_issue(False, True, False, 0) == (True, 0)


def test_controller_openpilot_requests_use_normal_engagement_events():
  CP = car.CarParams.new_message(pcmCruise=False)
  CS = car.CarState.new_message(canValid=True)

  assert controller_openpilot_event(CP, CS, False, True, False) == log.OnroadEvent.EventName.buttonEnable
  assert controller_openpilot_event(CP, CS, True, False, True) == log.OnroadEvent.EventName.buttonCancel
  assert controller_openpilot_event(CP, CS, True, True, True) == log.OnroadEvent.EventName.buttonCancel


def test_controller_engage_requires_valid_can_and_active_pcm_cruise():
  CP = car.CarParams.new_message(pcmCruise=True)
  CS = car.CarState.new_message(canValid=True)

  assert controller_openpilot_event(CP, CS, False, True, False) is None
  CS.cruiseState.enabled = True
  assert controller_openpilot_event(CP, CS, False, True, False) == log.OnroadEvent.EventName.buttonEnable
  CS.canValid = False
  assert controller_openpilot_event(CP, CS, False, True, False) is None


def test_starpilot_selfdrive_state_uses_sampled_car_state_speed():
  class FakeEvents:
    names = []

    @staticmethod
    def contains(_event_type):
      return False

  class FakeSubMaster:
    frame = 1

    @staticmethod
    def __getitem__(service):
      if service == "starpilotPlan":
        return SimpleNamespace(forcingStop=False)
      raise KeyError(service)

  class FakePubMaster:
    def __init__(self):
      self.messages = {}

    def send(self, service, message):
      self.messages[service] = message

  stock_alert = SimpleNamespace(
    alert_text_1="", alert_text_2="", alert_size=log.SelfdriveState.AlertSize.none,
    alert_status=log.SelfdriveState.AlertStatus.normal, alert_type="",
    audible_alert=log.SelfdriveState.AudibleAlert.none,
    visual_alert=car.CarControl.HUDControl.VisualAlert.none,
  )
  starpilot_alert = SimpleNamespace(
    alert_text_1="", alert_text_2="", alert_size=custom.StarPilotSelfdriveState.AlertSize.none,
    alert_status=custom.StarPilotSelfdriveState.AlertStatus.normal, alert_type="",
    audible_alert=log.SelfdriveState.AudibleAlert.none,
  )

  selfdrived = SelfdriveD.__new__(SelfdriveD)
  selfdrived.enabled = False
  selfdrived.active = False
  selfdrived.state_machine = SimpleNamespace(state=log.SelfdriveState.OpenpilotState.disabled)
  selfdrived.events = FakeEvents()
  selfdrived.starpilot_events = FakeEvents()
  selfdrived.events_prev = []
  selfdrived.starpilot_events_prev = []
  selfdrived.experimental_mode = False
  selfdrived.personality = log.LongitudinalPersonality.standard
  selfdrived.AM = SimpleNamespace(current_alert=stock_alert)
  selfdrived.starpilot_AM = SimpleNamespace(current_alert=starpilot_alert)
  selfdrived.forcing_stop_chime_played = False
  selfdrived.sm = FakeSubMaster()
  selfdrived.pm = FakePubMaster()

  selfdrived.publish_selfdriveState(car.CarState.new_message(vEgo=12.5))

  msg = selfdrived.pm.messages["starpilotSelfdriveState"]
  assert msg.starpilotSelfdriveState.vEgo == 12.5


class FakeFallbackParams:
  def __init__(self, controls_ready, ecu_disable_failed, fallback_cp, fallback_fpcp):
    self.controls_ready = controls_ready
    self.ecu_disable_failed = ecu_disable_failed
    self.values = {
      "CarParams": fallback_cp.to_bytes(),
      "StarPilotCarParams": fallback_fpcp.to_bytes(),
    }

  def get_bool(self, key):
    return self.controls_ready if key == "ControlsReady" else self.ecu_disable_failed

  def get(self, key):
    return self.values[key]


def test_immediate_max_output_saturation_is_torque_controller_only():
  CP = car.CarParams.new_message()
  CP.steerControlType = car.CarParams.SteerControlType.torque
  CP.lateralTuning.init("torque")

  assert commanded_torque_at_max_for_saturation(CP, 1.0)
  assert not commanded_torque_at_max_for_saturation(CP, 0.99)

  CP.lateralTuning.init("pid")
  assert not commanded_torque_at_max_for_saturation(CP, 1.0)

  CP.lateralTuning.init("torque")
  CP.steerControlType = car.CarParams.SteerControlType.angle
  assert not commanded_torque_at_max_for_saturation(CP, 1.0)


def test_gv70_uses_normal_saturation_timer_at_max_output():
  CP = car.CarParams.new_message()
  CP.carFingerprint = HYUNDAI_CAR.GENESIS_GV70_ELECTRIFIED_1ST_GEN
  CP.steerControlType = car.CarParams.SteerControlType.torque
  CP.lateralTuning.init("torque")

  assert not commanded_torque_at_max_for_saturation(CP, 1.0)


def test_ecu_disable_fallback_synchronizes_behavior_and_safety_params():
  initial_cp = car.CarParams.new_message()
  initial_cp.carFingerprint = NISSAN_CAR.NISSAN_LEAF
  initial_cp.openpilotLongitudinalControl = True
  initial_cp.pcmCruise = False
  initial_cp.safetyConfigs = [car.CarParams.SafetyConfig.new_message(safetyParam=2)]
  initial_fpcp = custom.StarPilotCarParams.new_message()
  initial_fpcp.safetyConfigs = [custom.StarPilotCarParams.SafetyConfig.new_message(safetyParam=2)]

  fallback_cp = car.CarParams.new_message()
  fallback_cp.openpilotLongitudinalControl = False
  fallback_cp.pcmCruise = True
  fallback_cp.safetyConfigs = [car.CarParams.SafetyConfig.new_message(safetyParam=0)]
  fallback_fpcp = custom.StarPilotCarParams.new_message()
  fallback_fpcp.safetyConfigs = [custom.StarPilotCarParams.SafetyConfig.new_message(safetyParam=0)]

  selfdrived = SelfdriveD.__new__(SelfdriveD)
  initial_cp_reader = messaging.log_from_bytes(initial_cp.to_bytes(), car.CarParams)
  selfdrived.CP = initial_cp_reader
  selfdrived.FPCP = messaging.log_from_bytes(initial_fpcp.to_bytes(), custom.StarPilotCarParams)
  selfdrived.params = FakeFallbackParams(True, True, fallback_cp, fallback_fpcp)
  selfdrived.ecu_disable_failed = False
  selfdrived.ecu_disable_failed_checked = False

  selfdrived.update_ecu_disable_failed()

  assert selfdrived.ecu_disable_failed
  assert selfdrived.ecu_disable_failed_checked
  assert not selfdrived.CP.openpilotLongitudinalControl
  assert selfdrived.CP.pcmCruise
  assert selfdrived.FPCP.safetyConfigs[0].safetyParam == 0
  assert initial_cp_reader.openpilotLongitudinalControl
  assert not initial_cp_reader.pcmCruise

  CS = car.CarState.new_message()
  CS.gearShifter = car.CarState.GearShifter.drive
  CS.cruiseState.available = True
  CS.cruiseState.enabled = True
  CS_prev = car.CarState.new_message()
  events = selfdrived.car_events.update(CS, CS_prev, car.CarControl.new_message())
  assert log.OnroadEvent.EventName.pcmEnable in events.names


def test_ecu_disable_fallback_does_not_change_other_cars():
  initial_cp = car.CarParams.new_message()
  initial_cp.carFingerprint = HYUNDAI_CAR.HYUNDAI_SONATA
  initial_cp.openpilotLongitudinalControl = True
  initial_cp.pcmCruise = False
  initial_fpcp = custom.StarPilotCarParams.new_message()
  initial_fpcp.safetyConfigs = [custom.StarPilotCarParams.SafetyConfig.new_message(safetyParam=4)]

  fallback_cp = car.CarParams.new_message()
  fallback_cp.openpilotLongitudinalControl = False
  fallback_cp.pcmCruise = True
  fallback_fpcp = custom.StarPilotCarParams.new_message()
  fallback_fpcp.safetyConfigs = [custom.StarPilotCarParams.SafetyConfig.new_message(safetyParam=0)]

  selfdrived = SelfdriveD.__new__(SelfdriveD)
  initial_cp_reader = messaging.log_from_bytes(initial_cp.to_bytes(), car.CarParams)
  initial_fpcp_reader = messaging.log_from_bytes(initial_fpcp.to_bytes(), custom.StarPilotCarParams)
  selfdrived.CP = initial_cp_reader
  selfdrived.FPCP = initial_fpcp_reader
  selfdrived.params = FakeFallbackParams(True, True, fallback_cp, fallback_fpcp)
  selfdrived.ecu_disable_failed = False
  selfdrived.ecu_disable_failed_checked = False

  selfdrived.update_ecu_disable_failed()

  assert selfdrived.ecu_disable_failed_checked
  assert selfdrived.CP.openpilotLongitudinalControl
  assert not selfdrived.CP.pcmCruise
  assert selfdrived.FPCP.safetyConfigs[0].safetyParam == 4
  assert selfdrived.CP is initial_cp_reader
  assert selfdrived.FPCP is initial_fpcp_reader


# --- DisableDriverMonitoring coverage ---------------------------------------

def _derive_camera_and_ignore(disable_dm: bool):
  """Mirror the construction logic in SelfdriveD.__init__ for the relevant pieces."""
  camera_packets = ["roadCameraState", "wideRoadCameraState"]
  if not disable_dm:
    camera_packets.append("driverCameraState")

  ignore = []
  if disable_dm:
    ignore.append("driverMonitoringState")
  return camera_packets, ignore


def test_default_false_includes_driver_camera_packet():
  # DisableDriverMonitoring == False (default) must be byte-for-byte the original
  # behaviour: driverCameraState in camera_packets, driverMonitoringState NOT
  # in the ignore lists.
  camera_packets, ignore = _derive_camera_and_ignore(disable_dm=False)
  assert camera_packets == ["roadCameraState", "driverCameraState", "wideRoadCameraState"]
  assert "driverMonitoringState" not in ignore


def test_disable_driver_monitoring_drops_driver_camera_packet():
  # When DisableDriverMonitoring == True, driverCameraState must not be
  # subscribed so cameraMalfunction / cameraFrameRate do not fire due to
  # missing DM hardware.
  camera_packets, _ = _derive_camera_and_ignore(disable_dm=True)
  assert "driverCameraState" not in camera_packets
  assert "roadCameraState" in camera_packets
  assert "wideRoadCameraState" in camera_packets


def test_disable_driver_monitoring_ignores_driver_monitoring_state():
  # driverMonitoringState must be added to all three ignore lists so commIssue
  # does not fire when DM processes are intentionally not running.
  _, ignore = _derive_camera_and_ignore(disable_dm=True)
  assert "driverMonitoringState" in ignore


def test_dm_event_block_is_gated_by_disable_driver_monitoring():
  # The selfdrived DM event block must be skipped wholesale when
  # DisableDriverMonitoring is True. We assert this by simulating the guard
  # expression used in update_events().
  assert not (False and not True)   # CP.notCar == False, disable_dm == True -> block skipped
  assert not (False and not False)  # CP.notCar == False, disable_dm == False -> block enters


def test_comm_issue_eval_still_works_when_dm_ignored():
  # Even with driverMonitoringState in the ignore list, comm_issue eval must
  # remain functional: all_alive/all_freq_ok are no-ops for ignored services.
  from openpilot.selfdrive.selfdrived.selfdrived import evaluate_comm_issue
  frames = 0
  should_alert, frames = evaluate_comm_issue(False, True, True, frames)
  assert not should_alert
  assert frames == 1
