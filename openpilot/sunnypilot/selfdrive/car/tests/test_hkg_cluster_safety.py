import unittest

from opendbc.car.hyundai.values import HyundaiSafetyFlags
from opendbc.car.structs import CarParams
from opendbc.safety.tests.common import CANPackerSafety, make_msg
from opendbc.safety.tests.libsafety import libsafety_py
from openpilot.sunnypilot.selfdrive.car.hkg_cluster_display import HKG_CLUSTER_TEST_PAGES, cluster_test_page_values


class TestUnverifiedHkgClusterMessagesRemainBlocked(unittest.TestCase):
  def test_161_and_162_are_rejected_on_every_exposed_ev6_hda2_bus(self):
    safety = libsafety_py.libsafety
    safety_modes = (
      HyundaiSafetyFlags.CANFD_LKA_STEER_MSG | HyundaiSafetyFlags.EV_GAS,
      HyundaiSafetyFlags.CANFD_LKA_STEER_MSG | HyundaiSafetyFlags.EV_GAS | HyundaiSafetyFlags.LONG,
    )
    for safety_param in safety_modes:
      self.assertEqual(safety.set_safety_hooks(CarParams.SafetyModel.hyundaiCanfd, safety_param), 0)
      safety.init_tests()
      for address in (0x161, 0x162):
        for bus in (0, 1, 2):
          with self.subTest(safety_param=int(safety_param), address=address, bus=bus):
            self.assertFalse(safety.safety_tx_hook(make_msg(bus, address, 32)))


class TestParkOnlyHkgClusterSafetyGate(unittest.TestCase):
  BASE_PARAM = (HyundaiSafetyFlags.CANFD_LKA_STEER_MSG | HyundaiSafetyFlags.CANFD_ALT_BUTTONS |
                HyundaiSafetyFlags.EV_GAS | HyundaiSafetyFlags.CANFD_HKG_CLUSTER_TEST)

  def setUp(self):
    self.safety = libsafety_py.libsafety
    self.packer = CANPackerSafety("hyundai_canfd_generated")
    self._reset(self.BASE_PARAM)

  def _reset(self, safety_param):
    self.assertEqual(self.safety.set_safety_hooks(CarParams.SafetyModel.hyundaiCanfd, safety_param), 0)
    self.safety.init_tests()

  def _rx_vehicle_state(self, *, gear=0, gas=0, wheel_speed=0.0):
    accelerator = self.packer.make_can_msg_safety("ACCELERATOR", 1, {
      "GEAR": gear,
      "ACCELERATOR_PEDAL": gas,
    })
    wheels = self.packer.make_can_msg_safety("WHEEL_SPEEDS", 1, {
      "WHL_SpdFLVal": wheel_speed,
      "WHL_SpdFRVal": wheel_speed,
      "WHL_SpdRLVal": wheel_speed,
      "WHL_SpdRRVal": wheel_speed,
    })
    self.safety.safety_rx_hook(accelerator)
    self.safety.safety_rx_hook(wheels)

  def _page_messages(self, page_index=0, bus=1):
    status = cluster_test_page_values(HKG_CLUSTER_TEST_PAGES[page_index])
    return (
      self.packer.make_can_msg_safety("CCNC_0x161", bus, status),
    )

  def test_every_restricted_page_is_allowed_only_when_parked_and_disengaged(self):
    self._rx_vehicle_state()
    self.safety.set_controls_allowed(False)
    for page_index, page in enumerate(HKG_CLUSTER_TEST_PAGES):
      for message in self._page_messages(page_index):
        with self.subTest(page=page.name, address=message.addr):
          self.assertTrue(self.safety.safety_tx_hook(message))

  def test_wrong_bus_and_length_are_rejected(self):
    self._rx_vehicle_state()
    for message in self._page_messages(bus=0):
      self.assertFalse(self.safety.safety_tx_hook(message))
    for address in (0x161, 0x162):
      self.assertFalse(self.safety.safety_tx_hook(make_msg(1, address, 8)))

  def test_requires_park_standstill_no_gas_and_controls_disallowed(self):
    interlocks = (
      {"gear": 5},
      {"wheel_speed": 1.0},
      {"gas": 1},
    )
    for state in interlocks:
      with self.subTest(state=state):
        self._reset(self.BASE_PARAM)
        self._rx_vehicle_state(**state)
        self.assertTrue(all(not self.safety.safety_tx_hook(message) for message in self._page_messages()))

    self._reset(self.BASE_PARAM)
    self._rx_vehicle_state()
    self.safety.set_controls_allowed(True)
    self.assertTrue(all(not self.safety.safety_tx_hook(message) for message in self._page_messages()))

    self._reset(self.BASE_PARAM)
    self._rx_vehicle_state()
    self.safety.set_controls_allowed_lateral(True)
    self.assertTrue(all(not self.safety.safety_tx_hook(message) for message in self._page_messages()))

  def test_checksum_and_forbidden_warning_fields_are_rejected(self):
    self._rx_vehicle_state()
    status, = self._page_messages()
    corrupt = bytearray(status.data)
    corrupt[0] ^= 0x1
    self.assertFalse(self.safety.safety_tx_hook(make_msg(1, 0x161, 32, bytes(corrupt))))

    warning = self.packer.make_can_msg_safety("CCNC_0x161", 1, {"ALERTS_2": 1})
    fault = self.packer.make_can_msg_safety("CCNC_0x162", 1, {"FAULT_HDA": 1})
    self.assertFalse(self.safety.safety_tx_hook(warning))
    self.assertFalse(self.safety.safety_tx_hook(fault))

  def test_flag_is_required_and_longitudinal_variant_uses_same_gate(self):
    for safety_param, expected in (
      (self.BASE_PARAM & ~HyundaiSafetyFlags.CANFD_HKG_CLUSTER_TEST, False),
      (self.BASE_PARAM | HyundaiSafetyFlags.LONG, True),
    ):
      with self.subTest(safety_param=int(safety_param)):
        self._reset(safety_param)
        self._rx_vehicle_state()
        self.assertEqual(self.safety.safety_tx_hook(self._page_messages()[0]), expected)

  def test_hard_transmit_budget_stops_a_runaway_sender(self):
    self._rx_vehicle_state()
    message = self._page_messages()[0]
    for count in range(700):
      self.assertTrue(self.safety.safety_tx_hook(message), count)
    self.assertFalse(self.safety.safety_tx_hook(message))


if __name__ == "__main__":
  unittest.main()
