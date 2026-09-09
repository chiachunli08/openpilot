#!/usr/bin/env python3
"""Offroad downloader and QCOM precompiler for the pinned taco2 nav model."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np
import requests

from openpilot.common.hardware.hw import Paths
from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.modeld.helpers import dump_oob

TACO2_COMMIT = "a8c957e9d98cb3c334ab60c09e731c262605ae56"
NAVMODEL_SHA256 = "f851f19b0a9e2299639f18856e4879ee863918227b7cef6a07eb6b94a273a9aa"
NAVMODEL_SIZE = 12_259_173
NAVMODEL_URL = ("https://media.githubusercontent.com/media/commaai/openpilot/"
                f"{TACO2_COMMIT}/selfdrive/modeld/models/navmodel.onnx")
ONNX_FILENAME = "taco2_navmodel.onnx"
PKL_FILENAME = "taco2_navmodel_qcom.pkl"
COMPILE_INFO_FILENAME = "taco2_navmodel_qcom.json"
COMPILE_VERSION = "2:e837e367aac9e1a66e689f4f32ce20ca9367df13:qcom-model-flags"


def model_paths(root: str | Path | None = None) -> tuple[Path, Path]:
  model_root = Path(root or Paths.navigation_model_root())
  return model_root / ONNX_FILENAME, model_root / PKL_FILENAME


def compiled_model_matches(pkl_path: Path) -> bool:
  info_path = pkl_path.with_name(COMPILE_INFO_FILENAME)
  try:
    info = json.loads(info_path.read_text())
    return (pkl_path.is_file() and pkl_path.stat().st_size > 1024 and
            info.get("compileVersion") == COMPILE_VERSION and info.get("sourceSha256") == NAVMODEL_SHA256)
  except (OSError, ValueError, TypeError):
    return False


def file_matches(path: Path, expected_sha256: str = NAVMODEL_SHA256, expected_size: int = NAVMODEL_SIZE) -> bool:
  if not path.is_file() or path.stat().st_size != expected_size:
    return False
  with path.open("rb") as file:
    return hashlib.file_digest(file, "sha256").hexdigest() == expected_sha256


def download_navmodel(destination: Path) -> None:
  destination.parent.mkdir(parents=True, exist_ok=True)
  partial = destination.with_suffix(destination.suffix + ".partial")
  digest = hashlib.sha256()
  size = 0
  try:
    with requests.get(NAVMODEL_URL, stream=True, timeout=(20, 30)) as response:
      response.raise_for_status()
      with partial.open("wb") as file:
        for chunk in response.iter_content(256 * 1024):
          if not chunk:
            continue
          file.write(chunk)
          digest.update(chunk)
          size += len(chunk)
    if size != NAVMODEL_SIZE or digest.hexdigest() != NAVMODEL_SHA256:
      raise ValueError("taco2 navigation model hash or size mismatch")
    os.replace(partial, destination)
  finally:
    partial.unlink(missing_ok=True)


def compile_navmodel(onnx_path: Path, output_path: Path) -> None:
  # Match the repository's current QCOM compiler setup and serialize the JIT
  # while parked so no compilation is needed at the start of a drive.
  os.environ.update({
    "DEV": "QCOM",
    "IMAGE": "1",
    "FLOAT16": "1",
    "NOLOCALS": "1",
    "JIT_BATCH_SIZE": "0",
    "OPENPILOT_HACKS": "1",
    "GMMU": "0",
    "TC_MIN_GLOBALS": "32",
  })
  os.environ.pop("TC_OCCUPANCY_OPT", None)
  from tinygrad.device import Device
  from tinygrad.engine.jit import TinyJit
  from tinygrad.nn.onnx import OnnxRunner
  from tinygrad.tensor import Tensor
  from openpilot.sunnypilot.modeld_v2.compile_optimizations import configure_tensor_core_optimizer

  optimizer = configure_tensor_core_optimizer()
  runner = OnnxRunner(str(onnx_path))

  def execute(input_img):
    tensor = input_img.to(Device.DEFAULT)
    return next(iter(runner({"input_img": tensor}).values())).cast("float32").realize()

  host = np.zeros((1, 1, 256, 256), dtype=np.float32)
  input_tensor = Tensor(host, device="NPY").realize()
  compiled = TinyJit(execute, prune=True)
  for _ in range(3):
    output = compiled(input_tensor)
    Device.default.synchronize()
    if output.shape != (1, 228):
      raise ValueError(f"unexpected taco2 output shape: {output.shape}")

  output_path.parent.mkdir(parents=True, exist_ok=True)
  partial = output_path.with_suffix(output_path.suffix + ".partial")
  info_path = output_path.with_name(COMPILE_INFO_FILENAME)
  info_partial = info_path.with_suffix(info_path.suffix + ".partial")
  try:
    with partial.open("wb") as file:
      dump_oob({
        "run_model": compiled,
        "metadata": {
          "sourceCommit": TACO2_COMMIT,
          "sourceSha256": NAVMODEL_SHA256,
          "inputName": "input_img",
          "inputShape": (1, 1, 256, 256),
          "outputShape": (1, 228),
          "normalization": "uint8/255",
          "compilerOptimizer": optimizer,
          "compileVersion": COMPILE_VERSION,
        },
      }, file)
    os.replace(partial, output_path)
    info_partial.write_text(json.dumps({"compileVersion": COMPILE_VERSION, "sourceSha256": NAVMODEL_SHA256}))
    os.replace(info_partial, info_path)
  finally:
    partial.unlink(missing_ok=True)
    info_partial.unlink(missing_ok=True)


class NavigationModelManager:
  def __init__(self, params: Params | None = None, root: str | Path | None = None) -> None:
    self.params = params or Params()
    self.onnx_path, self.pkl_path = model_paths(root)

  def prepare(self) -> bool:
    try:
      if not file_matches(self.onnx_path):
        self.params.put("NavigationModelInstallStatus", "downloading")
        download_navmodel(self.onnx_path)
      if compiled_model_matches(self.pkl_path):
        if self.params.get("NavigationModelInstallStatus") != "ready":
          self.params.put("NavigationModelInstallStatus", "ready")
        return True
      self.params.put("NavigationModelInstallStatus", "compiling")
      compile_navmodel(self.onnx_path, self.pkl_path)
      self.params.put("NavigationModelInstallStatus", "ready")
      return True
    except Exception:
      # The URL contains no user credential, but still avoid dumping transport
      # details into normal logs. The UI exposes a retryable error state.
      cloudlog.warning("taco2 navigation model preparation failed")
      self.params.put("NavigationModelInstallStatus", "error")
      return False


def main() -> None:
  manager = NavigationModelManager()
  while True:
    if manager.params.get("NavigationModelInstallStatus") != "ready" or not compiled_model_matches(manager.pkl_path):
      manager.prepare()
    time.sleep(30)


if __name__ == "__main__":
  main()
