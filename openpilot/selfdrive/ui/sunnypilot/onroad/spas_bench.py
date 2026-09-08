"""Exercise the production SPAS builder without any CAN publisher or ECU access."""
import math
from types import SimpleNamespace


def duration_seconds(value):
  try:
    return max(3, min(8, int(value)))
  except (ValueError, TypeError, OverflowError):
    return 7


class RecordingPacker:
  def make_can_msg(self, name, bus, values):
    return name, bus, dict(values)


class SpasBenchSession:
  def __init__(self, builder=None):
    self.builder = builder
    self.direction = None
    self.deadline = None
    self.messages = []

  def _build(self, left, right):
    if self.builder is None:
      from opendbc.car.hyundai.hyundaicanfd import create_spas_messages
      self.builder = create_spas_messages
    # Synthetic bus for an in-memory unit test, not a vehicle bus selection.
    self.messages = self.builder(RecordingPacker(), SimpleNamespace(ECAN=1), left, right)

  def start(self, direction, duration, now):
    if direction not in ('left', 'right') or not math.isfinite(now):
      raise ValueError('Invalid bench request')
    self._build(direction == 'left', direction == 'right')
    self.direction = direction
    self.deadline = now + duration_seconds(duration)

  def stop(self):
    if self.direction is not None:
      self._build(False, False)
    self.direction = self.deadline = None

  def update(self, now):
    if self.deadline is not None and (not math.isfinite(now) or now >= self.deadline):
      self.stop()

  def remaining(self, now):
    return 0 if self.deadline is None else max(0, math.ceil(self.deadline - now))

  @property
  def control_value(self):
    return next((values['BLINKER_CONTROL'] for name, _, values in self.messages if name == 'SPAS2'), 0)
