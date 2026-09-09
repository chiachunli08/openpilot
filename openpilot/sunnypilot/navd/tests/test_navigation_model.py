from pathlib import Path

import numpy as np
import pyray as rl
import pytest

from openpilot.sunnypilot.navd.navigation_model_manager import (COMPILE_INFO_FILENAME, COMPILE_VERSION,
                                                                NAVMODEL_SHA256, compiled_model_matches, file_matches)
from openpilot.sunnypilot.navd.navigation_modeld import parse_navmodel_output, read_model_image


def test_output_layout_matches_taco2_nav_header():
  raw = np.arange(228, dtype=np.float32)
  parsed = parse_navmodel_output(raw)
  assert parsed["position_x"].shape == (33,)
  assert parsed["position_y"].shape == (33,)
  assert np.array_equal(parsed["desire_prediction"], raw[132:164])
  assert np.array_equal(parsed["features"], raw[164:228])


def test_output_rejects_wrong_length_or_nonfinite():
  with pytest.raises(ValueError):
    parse_navmodel_output(np.zeros(227))
  raw = np.zeros(228)
  raw[0] = np.nan
  with pytest.raises(ValueError):
    parse_navmodel_output(raw)


def test_model_image_is_uint8_normalized_like_taco2_tf8(tmp_path: Path):
  path = tmp_path / "input.png"
  image = rl.gen_image_color(256, 256, rl.Color(128, 128, 128, 255))
  try:
    assert rl.export_image(image, str(path))
  finally:
    rl.unload_image(image)
  data = read_model_image(path)
  assert data.shape == (1, 1, 256, 256)
  assert data.dtype == np.float32
  assert np.allclose(data, 128 / 255.0)


def test_hash_verification_is_size_and_content_bound(tmp_path: Path):
  path = tmp_path / "model"
  path.write_bytes(b"model")
  import hashlib
  assert file_matches(path, hashlib.sha256(b"model").hexdigest(), 5)
  assert not file_matches(path, "0" * 64, 5)
  assert not file_matches(path, hashlib.sha256(b"model").hexdigest(), 6)


def test_compiled_model_sidecar_is_bound_to_compiler_and_source(tmp_path: Path):
  model = tmp_path / "taco2_navmodel_qcom.pkl"
  model.write_bytes(b"x" * 2048)
  info = model.with_name(COMPILE_INFO_FILENAME)
  info.write_text(f'{{"compileVersion":"{COMPILE_VERSION}","sourceSha256":"{NAVMODEL_SHA256}"}}')
  assert compiled_model_matches(model)
  info.write_text(f'{{"compileVersion":"old","sourceSha256":"{NAVMODEL_SHA256}"}}')
  assert not compiled_model_matches(model)
