import math


LEAD_DEPARTURE_MIN_DISTANCE = 2.0
LEAD_DEPARTURE_MAX_DISTANCE = 60.0
LEAD_DEPARTURE_STOPPED_SPEED = 0.5
LEAD_DEPARTURE_MOVING_SPEED = 0.8
LEAD_DEPARTURE_MOVING_REL_SPEED = 0.4
LEAD_DEPARTURE_DISTANCE_GAIN = 1.0
LEAD_DEPARTURE_DISTANCE_REL_SPEED = 0.2
LEAD_DEPARTURE_ARM_TIME = 1.0
LEAD_DEPARTURE_CONFIRM_TIME = 0.3
LEAD_DEPARTURE_LOSS_TIME = 0.3


class LeadDepartureDetector:
  """Detect a stopped lead pulling away while ego remains stationary."""

  def __init__(self, dt: float):
    self.arm_frames = max(1, round(LEAD_DEPARTURE_ARM_TIME / dt))
    self.confirm_frames = max(1, round(LEAD_DEPARTURE_CONFIRM_TIME / dt))
    self.loss_frames = max(1, round(LEAD_DEPARTURE_LOSS_TIME / dt))
    self.reset()

  def reset(self) -> None:
    self.stationary_frames = 0
    self.departure_frames = 0
    self.missing_frames = 0
    self.anchor_distance: float | None = None
    self.track_id: int | None = None
    self.armed = False
    self.notified = False

  @staticmethod
  def _valid_lead(status: bool, d_rel: float, v_lead: float, v_rel: float) -> bool:
    return (status and math.isfinite(d_rel) and math.isfinite(v_lead) and math.isfinite(v_rel) and
            LEAD_DEPARTURE_MIN_DISTANCE <= d_rel <= LEAD_DEPARTURE_MAX_DISTANCE)

  def update(self, ego_stopped: bool, status: bool, d_rel: float, v_lead: float, v_rel: float, track_id: int = -1) -> bool:
    if not ego_stopped:
      self.reset()
      return False

    if not self._valid_lead(status, d_rel, v_lead, v_rel):
      self.missing_frames += 1
      if self.missing_frames >= self.loss_frames:
        self.reset()
      return False

    self.missing_frames = 0
    track_id = int(track_id)
    if self.track_id is not None and self.track_id >= 0 and track_id >= 0 and track_id != self.track_id:
      self.reset()

    if self.track_id is None:
      self.track_id = track_id

    if self.notified:
      return False

    lead_stopped = abs(v_lead) <= LEAD_DEPARTURE_STOPPED_SPEED and abs(v_rel) <= LEAD_DEPARTURE_STOPPED_SPEED
    if not self.armed:
      if not lead_stopped:
        self.stationary_frames = 0
        self.anchor_distance = None
        return False

      self.stationary_frames += 1
      if self.anchor_distance is None:
        self.anchor_distance = float(d_rel)
      else:
        self.anchor_distance = 0.9 * self.anchor_distance + 0.1 * float(d_rel)
      self.armed = self.stationary_frames >= self.arm_frames
      return False

    distance_gain = float(d_rel) - self.anchor_distance
    moving = ((v_lead >= LEAD_DEPARTURE_MOVING_SPEED and v_rel >= LEAD_DEPARTURE_MOVING_REL_SPEED) or
              (distance_gain >= LEAD_DEPARTURE_DISTANCE_GAIN and v_rel >= LEAD_DEPARTURE_DISTANCE_REL_SPEED))
    self.departure_frames = self.departure_frames + 1 if moving else 0

    if self.departure_frames >= self.confirm_frames:
      self.notified = True
      self.armed = False
      return True
    return False
