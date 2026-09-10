"""Start sunnypilot modeld_v2 with the optional display-only traffic-signal detector attached.

This wrapper deliberately keeps Chestnut access in modeld's process. The primary driving model
runs first on every frame; YOLO only receives opportunistic slots after the main inference returns.
"""

import time

import openpilot.cereal.messaging as messaging
import openpilot.sunnypilot.modeld_v2.modeld as base
from opendbc.car.structs import car
from openpilot.sunnypilot.modeld_v2.traffic_signal_yolo import TrafficSignalYolo

_original_init = base.ModelState.__init__
_original_run = base.ModelState.run


def _patched_init(self, cam_w: int, cam_h: int, chestnut: bool = False):
  _original_init(self, cam_w, cam_h, chestnut)
  self._traffic_signal_yolo = TrafficSignalYolo(cam_w, cam_h) if chestnut else None
  self._traffic_signal_sm = messaging.SubMaster(["carState", "selfdriveState", "selfdriveStateSP", "modelV2"]) if chestnut else None


def _patched_run(self, bufs, transforms, inputs, after_enqueue=None):
  # Measure only the driving model itself. This is the admission signal used by the visual detector.
  st = time.perf_counter()
  output = _original_run(self, bufs, transforms, inputs, after_enqueue)
  main_model_ms = (time.perf_counter() - st) * 1000.0

  detector = getattr(self, "_traffic_signal_yolo", None)
  sm = getattr(self, "_traffic_signal_sm", None)
  if detector is not None and sm is not None and output is not None:
    try:
      # ModelState.warmup() passes numpy arrays. Never download, compile or run YOLO during the
      # driving-model warmup. Real VisionBuf objects expose .data.
      road_buf = next((buf for key, buf in bufs.items() if "big" not in key), None)
      if road_buf is None or not hasattr(road_buf, "data"):
        return output

      sm.update(0)
      speed = max(0.0, float(sm["carState"].vEgo)) if sm.seen["carState"] else 0.0
      parked = bool(sm.seen["carState"] and sm["carState"].gearShifter == car.CarState.GearShifter.park)

      controls_active = False
      if sm.seen["selfdriveState"]:
        controls_active = bool(sm["selfdriveState"].enabled)
      if sm.seen["selfdriveStateSP"]:
        controls_active = controls_active or bool(sm["selfdriveStateSP"].mads.enabled)

      previous_drop = 0.0
      if sm.seen["modelV2"] and sm.valid["modelV2"]:
        previous_drop = float(sm["modelV2"].frameDropPerc)

      # The fifth argument only gates download/warmup/first validation. After validation, normal
      # low-rate detection can run while driving if the primary model has enough measured headroom.
      setup_blocked = controls_active or not parked
      detector.maybe_run(road_buf, main_model_ms, previous_drop, speed, setup_blocked)
    except Exception:
      # Display-only code must never be allowed to take modeld down.
      pass

  return output


base.ModelState.__init__ = _patched_init
base.ModelState.run = _patched_run


if __name__ == "__main__":
  import argparse
  parser = argparse.ArgumentParser()
  parser.add_argument("--demo", action="store_true", help="A boolean for demo mode.")
  args = parser.parse_args()
  base.main(demo=args.demo)
