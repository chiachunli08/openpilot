from types import SimpleNamespace
import unittest

from opendbc.car.can_definitions import CanData
from opendbc.car.hyundai.interface import CarInterface
from opendbc.car.hyundai.values import CAR, HyundaiFlags
from opendbc.car import structs
from openpilot.sunnypilot.selfdrive.car.hkg_cluster_display import (
  CCNC_OBJECTS_ADDRESS,
  CCNC_STATUS_ADDRESS,
  HKG_CLUSTER_TEST_PAGES,
  HKG_CLUSTER_PERMISSION_PARAM,
  HKG_CLUSTER_TEST_PARAM,
  HKG_CLUSTER_TEST_STATUS_PARAM,
  HkgClusterDisplayTestController,
  cluster_test_page_values,
)


class FakeParams:
  def __init__(self, values=None):
    self.values = dict(values or {})

  def get(self, key, **_):
    return self.values.get(key)

  def get_bool(self, key):
    return bool(self.values.get(key, False))

  def put(self, key, value, **_):
    self.values[key] = value

  def put_bool(self, key, value, **_):
    self.values[key] = bool(value)


def make_test_cp(armed=True):
  CP = CarInterface.get_non_essential_params(CAR.KIA_EV6)
  CP.flags |= HyundaiFlags.CANFD_LKA_STEER_MSG.value
  if armed:
    CP.flags |= HyundaiFlags.CANFD_HKG_CLUSTER_TEST.value
  return CP


def safe_state(**overrides):
  values = {
    "canValid": True,
    "standstill": True,
    "vEgoRaw": 0.0,
    "gearShifter": structs.CarState.GearShifter.park,
    "gasPressed": False,
  }
  values.update(overrides)
  return SimpleNamespace(**values)


def disabled_control(**overrides):
  values = {"enabled": False, "latActive": False, "longActive": False}
  values.update(overrides)
  return SimpleNamespace(**values)


class TestHkgClusterActiveTest(unittest.TestCase):
  def setUp(self):
    self.params = FakeParams({HKG_CLUSTER_PERMISSION_PARAM: True, HKG_CLUSTER_TEST_PARAM: True})
    self.controller = HkgClusterDisplayTestController(make_test_cp(), self.params)

  def test_two_second_observation_then_20_hz_status(self):
    self.assertEqual(self.controller.update(safe_state(), disabled_control(), [], 0), [])
    self.assertEqual(self.controller.update(safe_state(), disabled_control(), [], 1_999_999_999), [])

    messages = self.controller.update(safe_state(), disabled_control(), [], 2_000_000_000)
    self.assertEqual([(address, len(dat), bus) for address, dat, bus in messages], [
      (CCNC_STATUS_ADDRESS, 32, 1),
    ])
    self.assertEqual(self.controller.update(safe_state(), disabled_control(), [], 2_049_999_999), [])
    self.assertEqual(len(self.controller.update(safe_state(), disabled_control(), [], 2_050_000_000)), 1)

  def test_original_message_collision_aborts_without_sending(self):
    packet = [(123, [CanData(CCNC_STATUS_ADDRESS, bytes(32), 1)])]
    self.assertEqual(self.controller.update(safe_state(), disabled_control(), packet, 0), [])
    self.assertTrue(self.controller.done)
    self.assertFalse(self.params.get_bool(HKG_CLUSTER_TEST_PARAM))
    self.assertEqual(self.params.get(HKG_CLUSTER_TEST_STATUS_PARAM), "aborted_stock_0x161_on_bus_1")

  def test_same_id_with_unexpected_length_still_aborts(self):
    packet = [(123, [CanData(CCNC_OBJECTS_ADDRESS, bytes(8), 0)])]
    self.assertEqual(self.controller.update(safe_state(), disabled_control(), packet, 0), [])
    self.assertEqual(self.params.get(HKG_CLUSTER_TEST_STATUS_PARAM), "aborted_stock_0x162_on_bus_0")

  def test_vehicle_interlock_change_aborts_after_start(self):
    self.controller.update(safe_state(), disabled_control(), [], 0)
    self.assertEqual(len(self.controller.update(safe_state(), disabled_control(), [], 2_000_000_000)), 1)

    self.assertEqual(self.controller.update(safe_state(gearShifter=structs.CarState.GearShifter.drive),
                                            disabled_control(), [], 2_050_000_000), [])
    self.assertTrue(self.controller.done)
    self.assertEqual(self.params.get(HKG_CLUSTER_TEST_STATUS_PARAM), "aborted_vehicle_interlock")

  def test_unsafe_state_waits_and_times_out_without_sending(self):
    moving = safe_state(standstill=False, vEgoRaw=1.0)
    self.assertEqual(self.controller.update(moving, disabled_control(), [], 0), [])
    self.assertEqual(self.controller.update(moving, disabled_control(), [], 120_000_000_000), [])
    self.assertTrue(self.controller.done)
    self.assertEqual(self.params.get(HKG_CLUSTER_TEST_STATUS_PARAM), "aborted_wait_timeout")

  def test_all_pages_complete_and_one_shot_clears(self):
    self.controller.update(safe_state(), disabled_control(), [], 0)
    self.controller.update(safe_state(), disabled_control(), [], 2_000_000_000)
    duration_ns = int(sum(page.duration_s for page in HKG_CLUSTER_TEST_PAGES) * 1e9)
    self.assertEqual(self.controller.update(safe_state(), disabled_control(), [], 2_000_000_000 + duration_ns), [])
    self.assertTrue(self.controller.done)
    self.assertFalse(self.params.get_bool(HKG_CLUSTER_TEST_PARAM))
    self.assertEqual(self.params.get(HKG_CLUSTER_TEST_STATUS_PARAM), "complete")

  def test_unarmed_controller_never_sends(self):
    controller = HkgClusterDisplayTestController(make_test_cp(armed=False), FakeParams())
    self.assertEqual(controller.update(safe_state(), disabled_control(), [], 3_000_000_000), [])
    self.assertTrue(controller.done)

  def test_unsupported_or_passive_request_is_cleared_at_startup(self):
    CP = make_test_cp()
    CP.passive = True
    params = FakeParams({HKG_CLUSTER_PERMISSION_PARAM: True, HKG_CLUSTER_TEST_PARAM: True})
    controller = HkgClusterDisplayTestController(CP, params)
    self.assertTrue(controller.done)
    self.assertFalse(params.get_bool(HKG_CLUSTER_TEST_PARAM))
    self.assertEqual(params.get(HKG_CLUSTER_TEST_STATUS_PARAM), "not_armed_incompatible_or_passive")

  def test_live_setting_can_cancel_armed_test(self):
    self.controller.update(safe_state(), disabled_control(), [], 0)
    self.params.put_bool(HKG_CLUSTER_PERMISSION_PARAM, False)
    self.assertEqual(self.controller.update(safe_state(), disabled_control(), [], 2_000_000_000), [])
    self.assertTrue(self.controller.done)
    self.assertEqual(self.params.get(HKG_CLUSTER_TEST_STATUS_PARAM), "cancelled_setting_disabled")

  def test_test_pages_cover_requested_fields_but_not_warning_fields(self):
    self.assertEqual(len(HKG_CLUSTER_TEST_PAGES), 10)
    status_keys = set()
    for page in HKG_CLUSTER_TEST_PAGES:
      status = cluster_test_page_values(page)
      status_keys.update(key for key, value in status.items() if value)
      self.assertNotIn("ALERTS_1", status)
      self.assertNotIn("SOUNDS_1", status)

    self.assertTrue({"LCA_LEFT_ARROW", "LCA_RIGHT_ARROW", "LANELINE_LEFT", "LANELINE_RIGHT", "NAV_ICON"} <= status_keys)


if __name__ == "__main__":
  unittest.main()
