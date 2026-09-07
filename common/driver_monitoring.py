from openpilot.common.params import Params


def is_driver_monitoring_disabled(params: Params | None = None) -> bool:
  """Driver monitoring is hard-disabled on this fork (no driver camera hardware)."""
  return True


def set_driver_monitoring_disabled(disabled: bool, params: Params | None = None) -> None:
  """No-op on this fork. Kept as a stable API for callers / tests."""
  return