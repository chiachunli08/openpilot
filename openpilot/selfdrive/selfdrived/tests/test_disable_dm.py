from opendbc.car.structs import car

from openpilot.common.params import Params
from openpilot.common.test import OpenpilotTestCase
from openpilot.selfdrive.controls.lib.driver_monitoring import get_force_decel
from openpilot.selfdrive.selfdrived.camera_config import get_camera_packets
from openpilot.system.manager.process_config import managed_processes


class TestDisableDM(OpenpilotTestCase):
  def setup_method(self):
    self.params = Params()
    self.params.clear_all()
    self.CP = car.CarParams.new_message()

  def test_default_is_disabled(self):
    assert self.params.get_default_value("DisableDM") == 1

  def test_camera_packets(self):
    assert get_camera_packets(False) == ["narrowRoadCameraState", "cabinCameraState", "wideRoadCameraState"]
    assert get_camera_packets(True) == ["narrowRoadCameraState", "wideRoadCameraState"]

  def test_dm_processes_follow_param(self):
    for disabled, should_run in ((False, True), (True, False)):
      self.params.put("DisableDM", int(disabled), block=True)
      for name in ("dmonitoringmodeld", "dmonitoringd"):
        assert managed_processes[name].should_run(True, self.params, self.CP) is should_run

  def test_dm_cannot_force_decel_when_disabled(self):
    assert not get_force_decel(True, True, False)
    assert get_force_decel(False, True, False)
    assert get_force_decel(True, False, True)

  def test_driver_view_cannot_override_disabled_dm(self):
    self.params.put("DisableDM", 1, block=True)
    self.params.put_bool("IsDriverViewEnabled", True, block=True)
    for name in ("dmonitoringmodeld", "dmonitoringd"):
      assert not managed_processes[name].should_run(False, self.params, self.CP)
