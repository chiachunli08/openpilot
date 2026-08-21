import os
from typing import cast

from openpilot.system.hardware.base import HardwareBase
from openpilot.system.hardware.tici.hardware import Tici
from openpilot.system.hardware.pc.hardware import Pc

TICI = os.path.isfile('/TICI')
AGNOS = os.path.isfile('/AGNOS')
PC = not TICI


def driver_camera_available() -> bool:
  """Return whether this build should expect driver-camera messages."""
  return os.getenv("NO_DRIVER_CAMERA", "0") != "1" and not os.path.exists("/tmp/lite_hw")


if TICI:
  HARDWARE = cast(HardwareBase, Tici())
else:
  HARDWARE = cast(HardwareBase, Pc())

# Only comma 3/3X expose the DMA-BUF EGL extensions used by the zero-copy
# camera renderer and the direct EGL frame-pacing calls. /TICI is also present
# on comma 4, so it identifies the AGNOS hardware family rather than this GPU
# capability.
EGL_DMA_BUF_SUPPORTED = TICI and HARDWARE.get_device_type() in ("tici", "tizi")
