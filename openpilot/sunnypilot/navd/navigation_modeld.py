#!/usr/bin/env python3
"""Run taco2's navigation model on verified model-map frames."""
from __future__ import annotations

import ctypes
from pathlib import Path
import time

import numpy as np
import pyray as rl
from tinygrad.tensor import Tensor

from openpilot.cereal import messaging
from openpilot.common.file_chunker import open_file_chunked
from openpilot.common.hardware import HARDWARE
from openpilot.common.hardware.hw import Paths
from openpilot.common.params import Params
from openpilot.common.realtime import Ratekeeper
from openpilot.selfdrive.modeld.helpers import load_oob
from openpilot.sunnypilot.navd.mapbox_mapd import MODEL_FILENAME, model_map_supported
from openpilot.sunnypilot.navd.navigation_model_manager import (COMPILE_VERSION, NAVMODEL_SHA256, TACO2_COMMIT,
                                                                compiled_model_matches, file_matches, model_paths)

OUTPUT_LEN = 228
PLAN_POINTS = 33


def read_model_image(path: str | Path) -> np.ndarray:
  rl.set_trace_log_level(rl.LOG_ERROR)
  image = rl.load_image(str(path))
  if not rl.is_image_valid(image):
    raise ValueError("invalid model map image")
  try:
    if image.width != 256 or image.height != 256:
      raise ValueError("model map must be 256x256")
    rl.image_format(image, rl.PIXELFORMAT_UNCOMPRESSED_GRAYSCALE)
    address = int(rl.ffi.cast("uintptr_t", image.data))
    raw = ctypes.string_at(address, 256 * 256)
    return np.frombuffer(raw, dtype=np.uint8).astype(np.float32).reshape(1, 1, 256, 256) / 255.0
  finally:
    rl.unload_image(image)


def parse_navmodel_output(raw: np.ndarray) -> dict[str, np.ndarray]:
  output = np.asarray(raw, dtype=np.float32).reshape(-1)
  if output.size != OUTPUT_LEN or not np.all(np.isfinite(output)):
    raise ValueError("invalid taco2 navigation model output")
  mean = output[:PLAN_POINTS * 2].reshape(PLAN_POINTS, 2)
  log_std = output[PLAN_POINTS * 2:PLAN_POINTS * 4].reshape(PLAN_POINTS, 2)
  std = np.exp(np.clip(log_std, -20.0, 20.0))
  return {
    "position_x": mean[:, 0], "position_y": mean[:, 1],
    "position_x_std": std[:, 0], "position_y_std": std[:, 1],
    "desire_prediction": output[132:164], "features": output[164:228],
  }


class NavigationModelDaemon:
  def __init__(self, params: Params | None = None, sm=None, pm=None, device_type: str | None = None) -> None:
    self.params = params or Params()
    self.device_type = device_type if device_type is not None else HARDWARE.get_device_type()
    self.sm = sm or messaging.SubMaster(["mapboxNavigationStateSP", "navigationStateSP"])
    self.pm = pm or messaging.PubMaster(["navigationModelStateSP"])
    self.onnx_path, self.pkl_path = model_paths()
    self.asset_ready = model_map_supported(self.device_type) and file_matches(self.onnx_path)
    self.run_model = None
    self.host_input = np.zeros((1, 1, 256, 256), dtype=np.float32)
    self.input_tensor = None
    self.last_generation = -1
    self.last_result: dict[str, np.ndarray] | None = None
    self.last_route_id = ""
    self.last_input_mono_time = 0
    self.last_execution_time = 0.0
    if model_map_supported(self.device_type):
      self._load()

  def _load(self) -> None:
    if not compiled_model_matches(self.pkl_path):
      return
    try:
      bundle = load_oob(open_file_chunked(self.pkl_path))
      metadata = bundle.get("metadata", {})
      if (tuple(metadata.get("inputShape", ())) != (1, 1, 256, 256) or
          tuple(metadata.get("outputShape", ())) != (1, 228) or
          metadata.get("sourceCommit") != TACO2_COMMIT or
          metadata.get("sourceSha256") != NAVMODEL_SHA256 or
          metadata.get("compileVersion") != COMPILE_VERSION):
        return
      self.run_model = bundle["run_model"]
      self.input_tensor = Tensor(self.host_input, device="NPY").realize()
    except Exception:
      self.run_model = None
      self.input_tensor = None
      self.params.put("NavigationModelInstallStatus", "error")

  def _publish(self, status: str, *, input_valid: bool = False, features_valid: bool = False) -> None:
    msg = messaging.new_message("navigationModelStateSP")
    state = msg.navigationModelStateSP
    state.enabled = self.params.get_bool("NavigationModelEnabled")
    state.assetReady = self.asset_ready
    state.compiledReady = self.pkl_path.is_file() and self.run_model is not None
    state.running = self.run_model is not None
    state.inputValid = input_valid
    state.featuresValid = features_valid
    state.shadowOnly = not self.params.get_bool("NavigationModelFusionActive")
    state.routeId = self.last_route_id
    state.inputMonoTime = self.last_input_mono_time
    state.executionTime = self.last_execution_time
    if self.last_result is not None:
      state.features = self.last_result["features"].tolist()
      state.desirePrediction = self.last_result["desire_prediction"].tolist()
      state.positionX = self.last_result["position_x"].tolist()
      state.positionY = self.last_result["position_y"].tolist()
      state.positionXStd = self.last_result["position_x_std"].tolist()
      state.positionYStd = self.last_result["position_y_std"].tolist()
    state.status = status
    msg.valid = True
    self.pm.send("navigationModelStateSP", msg)

  def update(self) -> None:
    self.sm.update(0)
    if not self.params.get_bool("NavigationModelEnabled"):
      self._publish("disabled")
      return
    if not model_map_supported(self.device_type):
      self._publish("unsupportedHardware")
      return
    if self.run_model is None or self.input_tensor is None:
      self._publish("modelMissing")
      return
    if not (self.sm.valid["mapboxNavigationStateSP"] and self.sm.alive["mapboxNavigationStateSP"]):
      self._publish("mapUnavailable")
      return
    map_state = self.sm["mapboxNavigationStateSP"]
    route_state = self.sm["navigationStateSP"]
    route_id = str(map_state.routeId)
    route_state_fresh = bool(self.sm.valid["navigationStateSP"] and self.sm.alive["navigationStateSP"] and
                             0 <= time.monotonic() - self.sm.recv_time["navigationStateSP"] <= 2.5)
    input_valid = bool(map_state.modelImageValid and map_state.modelPositionValid and route_id and
                       route_state_fresh and
                       route_state.routeLoaded and route_state.routeId == route_id and
                       0 <= time.monotonic() - self.sm.recv_time["mapboxNavigationStateSP"] <= 2.5)
    if not input_valid:
      self.last_result = None
      self.last_route_id = route_id
      self._publish("mapUnavailable")
      return

    if map_state.generation != self.last_generation:
      try:
        image_path = Path(str(map_state.modelInputPath))
        expected_path = (Path(Paths.mapbox_navigation_shm_root()) / MODEL_FILENAME).resolve()
        if image_path.resolve() != expected_path or not image_path.is_file():
          raise ValueError("model map path is outside the renderer output")
        image = read_model_image(image_path)
        np.copyto(self.host_input, image)
        started = time.perf_counter()
        raw = self.run_model(self.input_tensor)
        self.last_execution_time = time.perf_counter() - started
        if isinstance(raw, tuple):
          raw = raw[0]
        self.last_result = parse_navmodel_output(raw.numpy())
        self.last_generation = map_state.generation
        self.last_route_id = route_id
        self.last_input_mono_time = map_state.modelLocationMonoTime
      except Exception:
        self.last_result = None
        self._publish("error", input_valid=True)
        return

    fused = self.params.get_bool("NavigationModelFusionActive")
    compatible = self.params.get_bool("NavigationModelFusionCompatible")
    status = "fused" if fused else ("runningShadow" if self.last_result is not None else "error")
    if self.params.get_bool("NavigationModelFusionEnabled") and not compatible:
      status = "modelIncompatible"
    self._publish(status, input_valid=True, features_valid=self.last_result is not None)


def main() -> None:
  daemon = NavigationModelDaemon()
  rk = Ratekeeper(2.0)
  while True:
    daemon.update()
    rk.keep_time()


if __name__ == "__main__":
  main()
