import time


def boot_time_ns() -> int:
  # Match pandad's nanos_since_boot(), including time spent suspended on Linux.
  return time.clock_gettime_ns(getattr(time, "CLOCK_BOOTTIME", time.CLOCK_MONOTONIC))


class MapboxQrScanSession:
  HEARTBEAT_KEY = "MapboxQrScanHeartbeat"
  HEARTBEAT_INTERVAL_NS = 500_000_000
  TIMEOUT_NS = 90_000_000_000

  def __init__(self, params, memory_params, clock=boot_time_ns):
    self.params = params
    self.memory_params = memory_params
    self.clock = clock
    self.active = False
    self._previous_driver_view = False

  def start(self, ignition: bool) -> None:
    self._started = self.clock()
    self._last_heartbeat = self._started
    self._ignition_at_start = ignition
    self._previous_driver_view = self.params.get_bool("IsDriverViewEnabled")
    self.active = True
    try:
      self.memory_params.put(self.HEARTBEAT_KEY, str(self._started), block=True)
      self.params.put_bool("IsDriverViewEnabled", True, block=True)
    except Exception:
      self.stop()
      raise

  def update(self, onroad: bool, ignition: bool) -> bool:
    if not self.active:
      return False
    now = self.clock()
    if onroad or (ignition and not self._ignition_at_start) or now - self._started >= self.TIMEOUT_NS:
      self.stop()
      return False
    if now - self._last_heartbeat >= self.HEARTBEAT_INTERVAL_NS:
      self.memory_params.put(self.HEARTBEAT_KEY, str(now), block=True)
      self._last_heartbeat = now
    return True

  def stop(self) -> None:
    if self.active:
      self.active = False
      try:
        self.memory_params.remove(self.HEARTBEAT_KEY)
      finally:
        self.params.put_bool("IsDriverViewEnabled", self._previous_driver_view, block=True)
