import numpy as np
import pytest

from openpilot.common.transformations.camera import CameraConfig, scale_intrinsics


def test_scale_intrinsics_for_c3x_c4_preprocess():
  source = CameraConfig(1928, 1208, 567.0)
  scaled = scale_intrinsics(source.intrinsics, source.size, (1344, 760))
  assert np.allclose(scaled[0], [567.0 * 1344 / 1928, 0.0, 672.0])
  assert np.allclose(scaled[1], [0.0, 567.0 * 760 / 1208, 380.0])
  assert np.allclose(scaled[2], [0.0, 0.0, 1.0])


def test_scale_intrinsics_rejects_invalid_dimensions():
  with pytest.raises(ValueError):
    scale_intrinsics(np.eye(3), (0, 1208), (1344, 760))
