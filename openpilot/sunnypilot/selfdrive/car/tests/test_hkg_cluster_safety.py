import unittest

from opendbc.car.hyundai.values import HyundaiSafetyFlags
from opendbc.car.structs import CarParams
from opendbc.safety.tests.common import make_msg
from opendbc.safety.tests.libsafety import libsafety_py


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


if __name__ == "__main__":
  unittest.main()
