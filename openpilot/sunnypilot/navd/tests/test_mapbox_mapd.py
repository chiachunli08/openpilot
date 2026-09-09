from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import pyray as rl
import pytest

from openpilot.sunnypilot.navd.mapbox_mapd import (COMMA_MAPS_API_BASE, DISPLAY_STYLE, MAPBOX_API_BASE,
                                                    MODEL_SIZE, TACO2_MODEL_STYLE,
                                                    MapboxTileRenderer, display_map_supported,
                                                    display_zoom, mercator_world, model_map_supported,
                                                    service_fresh, taco2_first_channel_grayscale, taco2_model_location,
                                                    taco2_tile_zoom)
from openpilot.cereal import log


class FakeParams:
  def get(self, _key):
    return None


def _cache_tiles(renderer, style, latitude, longitude, zoom):
  x, y = mercator_world(latitude, longitude, zoom)
  tile_x, tile_y = int(x // 512), int(y // 512)
  for dy in (-1, 0, 1):
    for dx in (-1, 0, 1):
      path = renderer._tile_path(style, zoom, tile_x + dx, tile_y + dy)
      path.parent.mkdir(parents=True, exist_ok=True)
      image = rl.gen_image_color(512, 512, rl.Color(35 + dx * 5, 40 + dy * 5, 45, 255))
      try:
        assert rl.export_image(image, str(path))
      finally:
        rl.unload_image(image)


def test_hardware_gates_are_exact():
  assert display_map_supported("tizi")
  assert not display_map_supported("tici")
  assert not display_map_supported("mici")
  assert model_map_supported("tici") and model_map_supported("tizi")
  assert not model_map_supported("mici")


def test_process_gate_never_starts_display_renderer_on_non_c3x():
  from openpilot.system.manager.process_config import mapbox_navigation_renderer_enabled
  params = Mock()
  params.get_bool.side_effect = lambda key: {
    "NavigationEnabled": True, "MapboxMapDisplayEnabled": True, "NavigationModelEnabled": False,
  }.get(key, False)
  with patch("openpilot.system.manager.process_config.HARDWARE.get_device_type", return_value="tizi"):
    assert mapbox_navigation_renderer_enabled(True, params, Mock())
  with patch("openpilot.system.manager.process_config.HARDWARE.get_device_type", return_value="tici"):
    assert not mapbox_navigation_renderer_enabled(True, params, Mock())
  with patch("openpilot.system.manager.process_config.HARDWARE.get_device_type", return_value="mici"):
    assert not mapbox_navigation_renderer_enabled(True, params, Mock())


def test_navigation_model_processes_require_navigation_supported_hardware_and_drive_state():
  from openpilot.system.manager.process_config import navigation_model_prepare_enabled, navigation_model_runtime_enabled
  params = Mock()
  values = {"NavigationEnabled": True, "NavigationModelEnabled": True}
  params.get_bool.side_effect = lambda key: values.get(key, False)
  with patch("openpilot.system.manager.process_config.HARDWARE.get_device_type", return_value="tizi"):
    assert navigation_model_prepare_enabled(False, params, Mock())
    assert navigation_model_runtime_enabled(True, params, Mock())
    assert not navigation_model_prepare_enabled(True, params, Mock())
    assert not navigation_model_runtime_enabled(False, params, Mock())
  values["NavigationEnabled"] = False
  with patch("openpilot.system.manager.process_config.HARDWARE.get_device_type", return_value="tizi"):
    assert not navigation_model_prepare_enabled(False, params, Mock())
  values["NavigationEnabled"] = True
  with patch("openpilot.system.manager.process_config.HARDWARE.get_device_type", return_value="mici"):
    assert not navigation_model_runtime_enabled(True, params, Mock())


def test_projection_and_speed_zoom():
  assert mercator_world(0.0, 0.0, 0) == (256.0, 256.0)
  assert display_zoom(5.0) == 16
  assert display_zoom(15.0) == 15
  assert display_zoom(30.0) == 14
  assert taco2_tile_zoom(25.0) == 15


def test_taco2_model_pose_uses_llk_and_converts_yaw_to_degrees():
  llk = NS(status=log.LiveLocationKalman.Status.valid,
           positionGeodetic=NS(valid=True, value=[25.0, 121.0, 3.0]),
           calibratedOrientationNED=NS(value=[0.0, 0.0, 0.5]))
  pose = taco2_model_location(llk, True, True)
  assert pose is not None
  assert pose[:2] == (25.0, 121.0)
  assert pose[2] == pytest.approx(28.6478898)
  llk.positionGeodetic.valid = False
  assert taco2_model_location(llk, True, True) is None


def test_stale_map_inputs_are_rejected():
  sm = NS(valid={"gps": True}, alive={"gps": True}, recv_time={"gps": 10.0})
  assert service_fresh(sm, "gps", now=12.0)
  assert not service_fresh(sm, "gps", now=13.0)


def test_taco2_grayscale_uses_first_rgb_channel_not_luminance():
  image = rl.gen_image_color(2, 2, rl.Color(17, 180, 240, 255))
  try:
    taco2_first_channel_grayscale(image)
    assert rl.get_image_color(image, 0, 0).r == 17
  finally:
    rl.unload_image(image)


def test_taco2_private_style_prefers_original_authenticated_map_host(tmp_path: Path):
  renderer = MapboxTileRenderer(FakeParams(), "tizi")
  renderer.cache_root = tmp_path
  renderer._comma_maps_token = lambda: "device-jwt"
  assert renderer._credentials(TACO2_MODEL_STYLE) == (COMMA_MAPS_API_BASE, "device-jwt")
  assert renderer._credentials(DISPLAY_STYLE) == (MAPBOX_API_BASE, "")


def test_cached_tiles_render_display_and_model_inputs(tmp_path: Path):
  renderer = MapboxTileRenderer(FakeParams(), "tizi")
  renderer.cache_root = tmp_path / "cache"
  renderer.output_root = tmp_path / "out"
  renderer.output_root.mkdir()
  latitude, longitude, zoom = 25.0, 121.0, 15
  route = [(25.0, 121.0), (25.001, 121.001)]

  _cache_tiles(renderer, DISPLAY_STYLE, latitude, longitude, zoom)
  display_path = renderer.output_root / "display.png"
  result = renderer.render(style=DISPLAY_STYLE, latitude=latitude, longitude=longitude, bearing=90.0,
                           zoom=zoom, route=route, output_path=display_path, output_size=640,
                           network_available=False)
  assert result.valid and result.missing_tiles == 0 and result.cached_tiles == 9

  _cache_tiles(renderer, TACO2_MODEL_STYLE, latitude, longitude, zoom)
  model_path = renderer.output_root / "model.png"
  result = renderer.render(style=TACO2_MODEL_STYLE, latitude=latitude, longitude=longitude, bearing=90.0,
                           zoom=zoom, route=route, output_path=model_path, output_size=MODEL_SIZE,
                           network_available=False, model_input=True)
  assert result.valid and result.missing_tiles == 0
  image = rl.load_image(str(model_path))
  try:
    assert (image.width, image.height) == (256, 256)
  finally:
    rl.unload_image(image)
