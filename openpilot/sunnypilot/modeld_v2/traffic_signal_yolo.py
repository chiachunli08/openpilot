"""Display-only traffic-signal detection using spare Chestnut GPU headroom.

The driving model always has priority. This helper runs in the same modeld process because
Chestnut must have a single GPU/USB owner. It never feeds detections into planning/control.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import time
import urllib.request

import numpy as np

from openpilot.common.hardware.hw import Paths
from openpilot.common.swaglog import cloudlog
from openpilot.sunnypilot.modeld_v2.traffic_signal_settings import is_enabled
from openpilot.system.camerad.cameras.nv12_info import get_nv12_info

MODEL_URL = "https://raw.githubusercontent.com/UsamaMasood12/YOLO11s-Traffic-Signal-Detection/main/runs/detect/yolo11s_custom_dataset/weights/best.onnx"
MODEL_GIT_BLOB_SHA1 = "acf5b39c8e83184587410f484dcb2213fee3bb4e"
MODEL_SIZE = 37_936_019
MODEL_INPUT = 640
CLASSES = ("green", "left-green", "left-red", "left-yellow", "red", "yellow")
STATE_PATH = Path("/dev/shm/sunnypilot_traffic_signal_yolo.json")
MODEL_PATH = Path(Paths.model_root()) / "traffic_signal_yolo11s.onnx"

# Conservative admission-control limits. The primary driving model runs at 20 Hz (50 ms cadence).
# YOLO is admitted only when the previous primary pass is comfortably below that budget, and the
# complete auxiliary path has already been measured on a real stationary camera frame.
TARGET_PERIOD_S = 0.50  # 2 Hz maximum after validation
SLOW_PERIOD_S = 1.00
MAIN_MODEL_MAX_MS = 22.0
MAX_YOLO_INFERENCE_MS = 12.0
MAX_AUX_TOTAL_MS = 18.0
HARD_AUX_TOTAL_MS = 25.0
MAX_PREVIOUS_FRAME_DROP_PCT = 0.5
BACKOFF_S = 5.0
SLOW_BACKOFF_S = 10.0
CONFIDENCE_THRESHOLD = 0.60


def _publish_state(**kwargs) -> None:
  state = {"timestamp": time.time(), **kwargs}
  tmp = STATE_PATH.with_suffix(".tmp")
  try:
    tmp.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, STATE_PATH)
  except OSError:
    pass


def _git_blob_sha1(path: Path) -> str:
  size = path.stat().st_size
  h = hashlib.sha1(f"blob {size}\0".encode())
  with path.open("rb") as f:
    for chunk in iter(lambda: f.read(1024 * 1024), b""):
      h.update(chunk)
  return h.hexdigest()


def model_ready() -> bool:
  try:
    return MODEL_PATH.stat().st_size == MODEL_SIZE and _git_blob_sha1(MODEL_PATH) == MODEL_GIT_BLOB_SHA1
  except OSError:
    return False


def _download_model() -> None:
  if model_ready():
    return
  MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
  fd, tmp_name = tempfile.mkstemp(prefix="traffic_signal_yolo_", suffix=".onnx", dir=MODEL_PATH.parent)
  os.close(fd)
  tmp = Path(tmp_name)
  try:
    _publish_state(active=False, status="downloading")
    req = urllib.request.Request(MODEL_URL, headers={"User-Agent": "sunnypilot-traffic-signal-visuals"})
    with urllib.request.urlopen(req, timeout=20) as src, tmp.open("wb") as dst:
      while chunk := src.read(1024 * 1024):
        dst.write(chunk)
    if tmp.stat().st_size != MODEL_SIZE or _git_blob_sha1(tmp) != MODEL_GIT_BLOB_SHA1:
      raise RuntimeError("traffic-signal model integrity check failed")
    os.replace(tmp, MODEL_PATH)
    _publish_state(active=False, status="downloaded")
  except Exception:
    cloudlog.exception("traffic signal YOLO download failed")
    _publish_state(active=False, status="download_error")
  finally:
    tmp.unlink(missing_ok=True)


def _letterbox_rgb_from_nv12(buf, cam_w: int, cam_h: int) -> np.ndarray:
  import cv2

  stride, y_height, uv_height, _ = get_nv12_info(cam_w, cam_h)
  raw = np.frombuffer(buf.data, dtype=np.uint8, count=stride * (y_height + uv_height))
  y = raw[:stride * y_height].reshape(y_height, stride)[:cam_h, :cam_w]
  uv = raw[stride * y_height:stride * (y_height + uv_height)].reshape(uv_height, stride)[:cam_h // 2, :cam_w]
  nv12 = np.vstack((y, uv))
  rgb = cv2.cvtColor(nv12, cv2.COLOR_YUV2RGB_NV12)

  scale = min(MODEL_INPUT / cam_w, MODEL_INPUT / cam_h)
  new_w, new_h = max(1, round(cam_w * scale)), max(1, round(cam_h * scale))
  resized = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
  canvas = np.full((MODEL_INPUT, MODEL_INPUT, 3), 114, dtype=np.uint8)
  x0, y0 = (MODEL_INPUT - new_w) // 2, (MODEL_INPUT - new_h) // 2
  canvas[y0:y0 + new_h, x0:x0 + new_w] = resized
  return canvas


def _decode(output: np.ndarray) -> tuple[str | None, float]:
  """Return the most relevant high-confidence signal from a standard Ultralytics detect head.

  YOLO11 detect exports normally expose [cx, cy, w, h, class...] with either (C,N) or (N,C)
  layout. We only need the best class for the HUD, so duplicate-box NMS is unnecessary here.
  """
  arr = np.asarray(output)
  while arr.ndim > 2:
    arr = arr[0]
  if arr.ndim != 2:
    return None, 0.0
  expected = 4 + len(CLASSES)
  if arr.shape[0] == expected:
    arr = arr.T
  elif arr.shape[1] != expected:
    return None, 0.0

  scores = arr[:, 4:4 + len(CLASSES)]
  boxes = arr[:, :4]
  if not scores.size or not np.isfinite(scores).all() or not np.isfinite(boxes).all():
    return None, 0.0
  best_class_per_box = np.argmax(scores, axis=1)
  best_score_per_box = scores[np.arange(len(scores)), best_class_per_box]
  valid = np.where(best_score_per_box >= CONFIDENCE_THRESHOLD)[0]
  if not len(valid):
    return None, 0.0

  # Prefer signals near the forward field and suppress tiny far-away candidates. This is only a HUD
  # relevance heuristic; it is never used as a driving decision.
  centers_x = boxes[valid, 0] / MODEL_INPUT
  widths = np.clip(boxes[valid, 2] / MODEL_INPUT, 0.0, 1.0)
  heights = np.clip(boxes[valid, 3] / MODEL_INPUT, 0.0, 1.0)
  center_weight = 1.0 - np.minimum(np.abs(centers_x - 0.5), 0.5) * 0.55
  size_weight = np.clip(np.sqrt(widths * heights) * 5.0, 0.55, 1.0)
  ranked = best_score_per_box[valid] * center_weight * size_weight
  idx = valid[int(np.argmax(ranked))]
  cls_idx = int(best_class_per_box[idx])
  return CLASSES[cls_idx], float(best_score_per_box[idx])


class TrafficSignalYolo:
  def __init__(self, cam_w: int, cam_h: int):
    self.cam_w = cam_w
    self.cam_h = cam_h
    self.runner = None
    self.jit = None
    self.input_name: str | None = None
    self.qualified = False
    self.runtime_validated = False
    self.last_run = 0.0
    self.backoff_until = 0.0
    self.period_s = TARGET_PERIOD_S
    self.last_inference_ms = math.inf
    self.last_aux_total_ms = math.inf
    self._download_thread: threading.Thread | None = None
    self._load_failed = False
    _publish_state(active=False, status="disabled")

  def _ensure_download(self) -> None:
    if model_ready() or (self._download_thread is not None and self._download_thread.is_alive()):
      return
    self._download_thread = threading.Thread(target=_download_model, daemon=True)
    self._download_thread.start()

  def _load_and_benchmark(self) -> bool:
    if self.runner is not None:
      return self.qualified
    if self._load_failed or not model_ready():
      return False
    try:
      from tinygrad import Tensor, TinyJit, dtypes
      from tinygrad.device import Device
      from tinygrad.nn.onnx import OnnxRunner

      _publish_state(active=False, status="warming")
      self.runner = OnnxRunner(str(MODEL_PATH))
      self.input_name = next(iter(self.runner.graph_inputs))

      def run_model(x):
        return next(iter(self.runner({self.input_name: x}).values()))

      self.jit = TinyJit(run_model)
      dummy = Tensor(np.zeros((1, 3, MODEL_INPUT, MODEL_INPUT), dtype=np.uint8), device=Device.DEFAULT).cast(dtypes.float32) / 255.0
      timings = []
      for _ in range(4):
        st = time.perf_counter()
        self.jit(dummy).realize()
        Device[Device.DEFAULT].synchronize()
        timings.append((time.perf_counter() - st) * 1000.0)
      # Ignore the compile-heavy first pass. Moving operation is still blocked until a complete real
      # camera-frame path is measured while stationary.
      self.last_inference_ms = max(timings[1:])
      self.qualified = self.last_inference_ms <= MAX_YOLO_INFERENCE_MS
      _publish_state(active=False, status="awaiting_stationary_validation" if self.qualified else "insufficient_headroom",
                     inferenceMs=round(self.last_inference_ms, 2))
      return self.qualified
    except Exception:
      self._load_failed = True
      self.runner = self.jit = None
      cloudlog.exception("traffic signal YOLO load/warmup failed")
      _publish_state(active=False, status="load_error")
      return False

  def _run_once(self, buf, main_model_ms: float, previous_frame_drop_pct: float) -> tuple[float, float, str | None, float]:
    from tinygrad import Tensor, dtypes
    from tinygrad.device import Device

    aux_st = time.perf_counter()
    rgb = _letterbox_rgb_from_nv12(buf, self.cam_w, self.cam_h)
    inp = Tensor(rgb, device=Device.DEFAULT).permute(2, 0, 1).unsqueeze(0).cast(dtypes.float32) / 255.0

    infer_st = time.perf_counter()
    out = self.jit(inp)
    out.realize()
    Device[Device.DEFAULT].synchronize()
    inference_ms = (time.perf_counter() - infer_st) * 1000.0

    cls_name, confidence = _decode(out.numpy())
    aux_total_ms = (time.perf_counter() - aux_st) * 1000.0
    self.last_inference_ms = inference_ms
    self.last_aux_total_ms = aux_total_ms
    return inference_ms, aux_total_ms, cls_name, confidence

  def maybe_run(self, buf, main_model_ms: float, previous_frame_drop_pct: float,
                speed_mps: float, controls_active: bool) -> None:
    if not is_enabled():
      _publish_state(active=False, status="disabled")
      return

    # Downloads and ONNX/JIT warmup never happen while moving or while lateral/longitudinal control is active.
    stationary_idle = speed_mps < 0.1 and not controls_active
    if not model_ready():
      if stationary_idle:
        self._ensure_download()
      else:
        _publish_state(active=False, status="model_not_ready")
      return

    if self.runner is None:
      if stationary_idle:
        self._load_and_benchmark()
      else:
        _publish_state(active=False, status="waiting_for_stationary_warmup")
      return

    if not self.qualified:
      return

    now = time.monotonic()
    if now < self.backoff_until or now - self.last_run < self.period_s:
      return

    # Before any moving inference, validate the complete real-frame path while stationary. This
    # includes NV12 conversion, resize, USB/GPU input, inference, GPU->CPU result and decoding.
    if not self.runtime_validated and not stationary_idle:
      _publish_state(active=False, status="waiting_for_stationary_validation")
      return

    if self.runtime_validated and (previous_frame_drop_pct > MAX_PREVIOUS_FRAME_DROP_PCT or main_model_ms > MAIN_MODEL_MAX_MS):
      self.backoff_until = now + BACKOFF_S
      _publish_state(active=False, status="backoff", mainModelMs=round(main_model_ms, 2),
                     frameDropPerc=round(previous_frame_drop_pct, 2), auxTotalMs=round(self.last_aux_total_ms, 2))
      return

    try:
      inference_ms, aux_total_ms, cls_name, confidence = self._run_once(buf, main_model_ms, previous_frame_drop_pct)
      self.last_run = now

      # A stationary validation failure means this device/model combination is not admitted for driving.
      if not self.runtime_validated:
        if inference_ms <= MAX_YOLO_INFERENCE_MS and aux_total_ms <= MAX_AUX_TOTAL_MS:
          self.runtime_validated = True
          self.period_s = TARGET_PERIOD_S
        else:
          self.qualified = False
          _publish_state(active=False, status="stationary_validation_failed",
                         inferenceMs=round(inference_ms, 2), auxTotalMs=round(aux_total_ms, 2),
                         mainModelMs=round(main_model_ms, 2))
          return

      # Runtime jitter gets an escalating response. Moderate overruns back off and drop to 1 Hz;
      # a large overrun disables further inference until modeld restarts and re-validates stationary.
      if inference_ms > MAX_YOLO_INFERENCE_MS or aux_total_ms > MAX_AUX_TOTAL_MS:
        self.backoff_until = now + SLOW_BACKOFF_S
        self.period_s = SLOW_PERIOD_S
        if aux_total_ms > HARD_AUX_TOTAL_MS:
          self.qualified = False
          self.runtime_validated = False
          status = "runtime_disabled_slow"
        else:
          status = "runtime_backoff_slow"
        _publish_state(active=False, status=status, inferenceMs=round(inference_ms, 2),
                       auxTotalMs=round(aux_total_ms, 2), mainModelMs=round(main_model_ms, 2))
        return

      # Restore normal rate only after a comfortably fast pass.
      if aux_total_ms <= MAX_AUX_TOTAL_MS * 0.8:
        self.period_s = TARGET_PERIOD_S

      _publish_state(active=cls_name is not None, status="detected" if cls_name else "clear",
                     signal=cls_name or "none", confidence=round(confidence, 4),
                     inferenceMs=round(inference_ms, 2), auxTotalMs=round(aux_total_ms, 2),
                     mainModelMs=round(main_model_ms, 2), frameDropPerc=round(previous_frame_drop_pct, 2),
                     rateHz=round(1.0 / self.period_s, 2))
    except Exception:
      self.backoff_until = now + SLOW_BACKOFF_S
      cloudlog.exception("traffic signal YOLO inference failed")
      _publish_state(active=False, status="inference_error")
