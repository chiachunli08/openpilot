#!/usr/bin/env python3
import time

from openpilot.cereal import messaging
from openpilot.common.realtime import Ratekeeper
from openpilot.sunnypilot.selfdrive.car.corner_radar import CornerRadarTracker, RESEARCH_COMMIT


def boot_time_ns() -> int:
  return time.clock_gettime_ns(getattr(time, "CLOCK_BOOTTIME", time.CLOCK_MONOTONIC))


def main() -> None:
  can_sock = messaging.sub_sock("can", timeout=20)
  pm = messaging.PubMaster(["cornerRadarStateSP"])
  tracker = CornerRadarTracker()
  rk = Ratekeeper(20)

  while True:
    for event in messaging.drain_sock(can_sock, wait_for_one=True):
      for frame in event.can:
        tracker.ingest(event.logMonoTime, int(frame.src), int(frame.address), bytes(frame.dat))

    now_nanos = boot_time_ns()
    tracker.expire(now_nanos)
    msg = messaging.new_message("cornerRadarStateSP", valid=True)
    state = msg.cornerRadarStateSP
    state.researchSource = RESEARCH_COMMIT
    state.observedBuses = sorted(tracker.observed_buses)
    state.candidateFrames = tracker.candidate_frames
    state.rejectedLength = tracker.rejected_length
    state.timestampErrors = tracker.timestamp_errors
    state.droppedRawFrames = tracker.dropped_raw_frames

    targets = state.init("targets", len(tracker.targets))
    for output, target in zip(targets, tracker.targets.values(), strict=True):
      record = target.record
      output.trackId = target.track_id
      output.sensorGroup = record.sensor_group
      output.sourceBus = record.source_bus
      output.address = record.address
      output.slot = record.slot
      output.candidateActive = record.candidate_active
      output.statusValidated = record.status_validated
      output.distance = record.distance_m
      output.encodedAngle = record.encoded_angle_deg
      output.correctedAngle = record.corrected_angle_deg
      output.longitudinal = record.longitudinal_m
      output.lateral = record.lateral_m
      output.relativeSpeedValid = False
      output.targetIdentityValidated = False
      output.mountingValidated = False
      output.ageSec = max((now_nanos - record.timestamp_nanos) / 1e9, 0.0)
      if target.estimated_radial_speed_mps is not None:
        output.estimatedRadialSpeed = target.estimated_radial_speed_mps
        output.estimatedRadialSpeedValid = True

    raw_frames = tracker.pop_raw_frames()
    raw = state.init("rawFrames", len(raw_frames))
    for output, frame in zip(raw, raw_frames, strict=True):
      output.timestampNanos = frame.timestamp_nanos
      output.sourceBus = frame.source_bus
      output.address = frame.address
      output.data = frame.data
      output.acceptedLength = frame.accepted_length
      output.timestampAccepted = frame.timestamp_accepted

    pm.send("cornerRadarStateSP", msg)
    rk.keep_time()


if __name__ == "__main__":
  main()
