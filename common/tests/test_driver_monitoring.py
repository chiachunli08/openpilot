from openpilot.common.driver_monitoring import is_driver_monitoring_disabled, set_driver_monitoring_disabled


class FakeParams:
  def __init__(self):
    self.value = False

  def get_bool(self, _key):
    return self.value

  def put_bool(self, _key, value):
    self.value = value


def test_is_driver_monitoring_disabled_is_hardcoded_true():
  # Driver monitoring is hard-disabled on this fork.
  params = FakeParams()
  assert is_driver_monitoring_disabled(params) is True


def test_set_driver_monitoring_disabled_is_noop():
  # set_driver_monitoring_disabled is kept as a stable API but is a no-op on this fork.
  params = FakeParams()
  set_driver_monitoring_disabled(True, params)
  assert params.value is False
  set_driver_monitoring_disabled(False, params)
  assert params.value is False
  assert is_driver_monitoring_disabled(params) is True