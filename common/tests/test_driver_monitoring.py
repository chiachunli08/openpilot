from pathlib import Path

from openpilot.common.driver_monitoring import is_driver_monitoring_disabled, set_driver_monitoring_disabled
from openpilot.common.params import UnknownKeyName


class FakeParams:
  def __init__(self, value=False, stale_prebuilt=False):
    self.value = value
    self.stale_prebuilt = stale_prebuilt

  def get_bool(self, _key):
    return self.value

  def put_bool(self, _key, value):
    if self.stale_prebuilt:
      raise UnknownKeyName(_key)
    self.value = value


def test_marker_fallback_for_stale_prebuilt(tmp_path: Path):
  marker = tmp_path / "disable_driver_monitoring"
  params = FakeParams(stale_prebuilt=True)

  set_driver_monitoring_disabled(True, params, marker)
  assert marker.is_file()
  assert is_driver_monitoring_disabled(params, marker)

  set_driver_monitoring_disabled(False, params, marker)
  assert not marker.exists()
  assert not is_driver_monitoring_disabled(params, marker)


def test_param_remains_canonical_with_current_prebuilt(tmp_path: Path):
  marker = tmp_path / "disable_driver_monitoring"
  params = FakeParams()

  set_driver_monitoring_disabled(True, params, marker)
  assert params.value
  assert is_driver_monitoring_disabled(params, marker)

  set_driver_monitoring_disabled(False, params, marker)
  assert not params.value
  assert not is_driver_monitoring_disabled(params, marker)
