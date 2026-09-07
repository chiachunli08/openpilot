from __future__ import annotations

from pathlib import Path

from openpilot.common.params import Params, UnknownKeyName


DISABLE_DRIVER_MONITORING_PARAM = "DisableDriverMonitoring"
DISABLE_DRIVER_MONITORING_MARKER = Path("/data/disable_driver_monitoring")


def is_driver_monitoring_disabled(params: Params | None = None, marker_path: Path = DISABLE_DRIVER_MONITORING_MARKER) -> bool:
  """Read the setting across source/prebuilt rolling updates.

  Older params_pyx prebuilts do not know the new parameter and return False.
  The marker keeps the setting usable and persistent until those artifacts are
  rebuilt, while the parameter remains the canonical value afterwards.
  """
  params = params or Params()
  return params.get_bool(DISABLE_DRIVER_MONITORING_PARAM) or marker_path.is_file()


def set_driver_monitoring_disabled(disabled: bool, params: Params | None = None,
                                   marker_path: Path = DISABLE_DRIVER_MONITORING_MARKER) -> None:
  params = params or Params()

  if disabled:
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.touch()

  try:
    params.put_bool(DISABLE_DRIVER_MONITORING_PARAM, disabled)
  except UnknownKeyName:
    # Expected while a device is still running the prebuilt from before this
    # parameter was added. The persistent marker is the compatibility store.
    pass

  if not disabled:
    marker_path.unlink(missing_ok=True)
