#!/usr/bin/env python3
"""Render cached Mapbox raster tiles for the C3X UI and taco2 nav model.

The driver-facing and model-facing images intentionally use separate styles
and output files. The model image is only declared valid when every required
tile was rendered with the historical taco2 style and an active route exists.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import ctypes
from dataclasses import dataclass
import math
import os
from pathlib import Path
import time

import pyray as rl
import requests

from openpilot.cereal import log, messaging
from openpilot.common.hardware import HARDWARE
from openpilot.common.hardware.hw import Paths
from openpilot.common.params import Params
from openpilot.common.realtime import Ratekeeper
from openpilot.sunnypilot.navd.mapbox_token_codec import decode_mapbox_token

TILE_SIZE = 512
DISPLAY_SIZE = 640
MODEL_SIZE = 256
MODEL_SOURCE_SIZE = 512
REQUEST_TIMEOUT = 5
DISPLAY_STYLE = ("mapbox", "navigation-night-v1", "navigation-night-v1")
# This is the style referenced by taco2's checked-in style.json. If it can no
# longer be downloaded, model input stays invalid instead of silently changing
# the learned representation.
TACO2_MODEL_STYLE = ("commaai", "ckvmksrpd4n0a14pfdo5heqzr", "taco2-monochrome")
DISPLAY_FILENAME = "display.png"
MODEL_FILENAME = "taco2_model.png"
MAPBOX_API_BASE = "https://api.mapbox.com"
COMMA_MAPS_API_BASE = "https://maps.comma.ai"


def display_map_supported(device_type: str | None = None) -> bool:
  return (device_type if device_type is not None else HARDWARE.get_device_type()) == "tizi"


def model_map_supported(device_type: str | None = None) -> bool:
  # taco2 ran on the Snapdragon 845 platform. Keep model-map execution off all
  # other hardware until a separate runtime/latency validation exists.
  return (device_type if device_type is not None else HARDWARE.get_device_type()) in ("tici", "tizi")


def service_fresh(sm, service: str, now: float | None = None, max_age: float = 2.5) -> bool:
  now = time.monotonic() if now is None else now
  recv_time = getattr(sm, "recv_time", {}).get(service, now)
  return bool(sm.valid[service] and sm.alive[service] and 0 <= now - recv_time <= max_age)


def mercator_world(latitude: float, longitude: float, zoom: int) -> tuple[float, float]:
  latitude = min(85.05112878, max(-85.05112878, latitude))
  scale = TILE_SIZE * (1 << zoom)
  x = (longitude + 180.0) / 360.0 * scale
  sin_lat = math.sin(math.radians(latitude))
  y = (0.5 - math.log((1.0 + sin_lat) / (1.0 - sin_lat)) / (4.0 * math.pi)) * scale
  return x, y


def display_zoom(v_ego: float) -> int:
  if v_ego < 10.0:
    return 16
  if v_ego < 25.0:
    return 15
  return 14


def taco2_tile_zoom(latitude: float) -> int:
  # taco2 map_renderer.cc derives a continuous zoom for 2 m/pixel using 256
  # logical pixels and applies Mapbox GL's one-level correction. Raster tiles
  # are integral, so select the nearest compatible level.
  return max(0, min(22, round(taco2_zoom_level(latitude))))


def taco2_zoom_level(latitude: float) -> float:
  return math.log2(max(1.0, math.cos(math.radians(latitude)) * 40_075_000 / (2.0 * 256))) - 1.0


def taco2_model_location(llk, service_valid: bool, service_alive: bool) -> tuple[float, float, float] | None:
  """Return the taco2 map pose (lat, lon, bearing degrees) when LLK is usable."""
  position = llk.positionGeodetic.value
  orientation = llk.calibratedOrientationNED.value
  valid = bool(service_valid and service_alive and llk.status == log.LiveLocationKalman.Status.valid and
               llk.positionGeodetic.valid and len(position) >= 2 and len(orientation) >= 3)
  if not valid:
    return None
  pose = float(position[0]), float(position[1]), math.degrees(float(orientation[2]))
  return pose if all(math.isfinite(value) for value in pose) else None


def taco2_first_channel_grayscale(image) -> None:
  """Match taco2's RGB888 crop, which selected byte 0 rather than luminance."""
  rl.image_format(image, rl.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8)
  pixel_count = image.width * image.height
  source_address = int(rl.ffi.cast("uintptr_t", image.data))
  red = ctypes.string_at(source_address, pixel_count * 4)[0::4]
  rl.image_format(image, rl.PIXELFORMAT_UNCOMPRESSED_GRAYSCALE)
  destination_address = int(rl.ffi.cast("uintptr_t", image.data))
  ctypes.memmove(destination_address, red, pixel_count)


@dataclass(frozen=True)
class RenderResult:
  valid: bool
  missing_tiles: int
  cached_tiles: int


class MapboxTileRenderer:
  def __init__(self, params: Params | None = None, device_type: str | None = None) -> None:
    rl.set_trace_log_level(rl.LOG_ERROR)
    self.params = params or Params()
    self.device_type = device_type if device_type is not None else HARDWARE.get_device_type()
    self.cache_root = Path(Paths.mapbox_navigation_cache_root())
    self.output_root = Path(Paths.mapbox_navigation_shm_root())
    self.cache_root.mkdir(parents=True, exist_ok=True)
    self.output_root.mkdir(parents=True, exist_ok=True)
    self._comma_maps_token_value = ""
    self._comma_maps_token_refresh = 0.0

  def _token(self) -> str:
    encoded = self.params.get("MapboxPublicKey") or self.params.get("MapboxSecretKey") or ""
    try:
      return decode_mapbox_token(encoded) if encoded else ""
    except ValueError:
      return ""

  def _comma_maps_token(self) -> str:
    # taco2 used maps.comma.ai with a device-signed JWT when no bundled
    # Mapbox token was available. Reuse that authenticated path for its
    # private historical style without ever persisting or logging the JWT.
    now = time.monotonic()
    if self._comma_maps_token_value and now < self._comma_maps_token_refresh:
      return self._comma_maps_token_value
    dongle_id = self.params.get("DongleId") or ""
    if not dongle_id:
      return ""
    try:
      from openpilot.common.api.comma_connect import CommaConnectApi
      self._comma_maps_token_value = CommaConnectApi(dongle_id).get_token(expiry_hours=4 * 7 * 24)
      self._comma_maps_token_refresh = now + 7 * 24 * 3600
    except Exception:
      # Key and JWT implementations vary across supported installations.
      self._comma_maps_token_value = ""
      self._comma_maps_token_refresh = 0.0
    return self._comma_maps_token_value

  def _credentials(self, style: tuple[str, str, str]) -> tuple[str, str]:
    if style == TACO2_MODEL_STYLE and (token := self._comma_maps_token()):
      return COMMA_MAPS_API_BASE, token
    return MAPBOX_API_BASE, self._token()

  def _tile_path(self, style: tuple[str, str, str], zoom: int, x: int, y: int) -> Path:
    return self.cache_root / style[2] / str(zoom) / str(x) / f"{y}.png"

  @staticmethod
  def _valid_image(path: Path) -> bool:
    try:
      if not path.is_file() or path.stat().st_size < 64:
        return False
      with path.open("rb") as file:
        signature = file.read(12)
      return signature.startswith(b"\x89PNG\r\n\x1a\n") or signature.startswith(b"\xff\xd8\xff")
    except OSError:
      return False

  def _download_tile(self, style: tuple[str, str, str], zoom: int, x: int, y: int,
                     api_base: str, token: str, network_available: bool) -> tuple[Path | None, bool]:
    x %= 1 << zoom
    if y < 0 or y >= 1 << zoom:
      return None, False
    path = self._tile_path(style, zoom, x, y)
    if self._valid_image(path):
      return path, True
    if not token or not network_available:
      return None, False

    owner, style_id, _ = style
    url = f"{api_base}/styles/v1/{owner}/{style_id}/tiles/{TILE_SIZE}/{zoom}/{x}/{y}"
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp.png")
    try:
      response = requests.get(url, params={"access_token": token}, timeout=REQUEST_TIMEOUT)
      response.raise_for_status()
      if len(response.content) > 10 * 1024 * 1024:
        return None, False
      path.parent.mkdir(parents=True, exist_ok=True)
      tmp.write_bytes(response.content)
      if not self._valid_image(tmp):
        return None, False
      os.replace(tmp, path)
      return path, False
    except (OSError, requests.RequestException):
      # A requests exception can contain the token-bearing URL. Do not log it.
      return None, False
    finally:
      try:
        tmp.unlink(missing_ok=True)
      except OSError:
        pass

  def _get_tiles(self, style: tuple[str, str, str], zoom: int, center_x: float, center_y: float,
                 api_base: str, token: str, network_available: bool) -> tuple[dict[tuple[int, int], Path], int]:
    center_tile_x, center_tile_y = int(center_x // TILE_SIZE), int(center_y // TILE_SIZE)
    coords = [(center_tile_x + dx, center_tile_y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
    tiles: dict[tuple[int, int], Path] = {}
    cached = 0
    with ThreadPoolExecutor(max_workers=6) as executor:
      futures = {coord: executor.submit(self._download_tile, style, zoom, *coord, api_base, token, network_available)
                 for coord in coords}
      for coord, future in futures.items():
        path, from_cache = future.result()
        if path is not None:
          tiles[coord] = path
          cached += int(from_cache)
    return tiles, cached

  @staticmethod
  def _draw_route(canvas, route: list[tuple[float, float]], zoom: int, origin_x: float, origin_y: float,
                  color: rl.Color, thickness: float) -> None:
    if len(route) < 2:
      return
    world_width = TILE_SIZE * (1 << zoom)
    points: list[rl.Vector2] = []
    center_world_x = origin_x + 1.5 * TILE_SIZE
    for latitude, longitude in route:
      x, y = mercator_world(latitude, longitude, zoom)
      while x - center_world_x > world_width / 2:
        x -= world_width
      while center_world_x - x > world_width / 2:
        x += world_width
      points.append(rl.Vector2(x - origin_x, y - origin_y))
    for start, end in zip(points, points[1:]):
      rl.image_draw_line_ex(canvas, start, end, int(round(thickness)), color)

  @staticmethod
  def _heading_crop(canvas, ego_x: float, ego_y: float, bearing: float, output_size: int,
                    source_size: int | None = None, pixel_scale: float = 1.0):
    source_size = source_size or int(math.ceil(output_size * math.sqrt(2.0))) + 4
    source_size = min(source_size, canvas.width, canvas.height)
    left = min(max(0, int(round(ego_x - source_size / 2))), canvas.width - source_size)
    top = min(max(0, int(round(ego_y - source_size / 2))), canvas.height - source_size)
    cropped = rl.image_copy(canvas)
    rl.image_crop(cropped, rl.Rectangle(left, top, source_size, source_size))
    rl.image_rotate(cropped, int(round(bearing)) % 360)
    crop_size = max(1, round(output_size / pixel_scale))
    final_left = max(0, (cropped.width - crop_size) // 2)
    final_top = max(0, (cropped.height - crop_size) // 2)
    rl.image_crop(cropped, rl.Rectangle(final_left, final_top, crop_size, crop_size))
    if crop_size != output_size:
      rl.image_resize(cropped, output_size, output_size)
    return cropped

  @staticmethod
  def _export(image, path: Path) -> bool:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp.png")
    try:
      if not rl.export_image(image, str(tmp)):
        return False
      os.replace(tmp, path)
      return True
    except OSError:
      return False
    finally:
      try:
        tmp.unlink(missing_ok=True)
      except OSError:
        pass

  def render(self, *, style: tuple[str, str, str], latitude: float, longitude: float, bearing: float,
             zoom: int, route: list[tuple[float, float]], output_path: Path, output_size: int,
             network_available: bool, model_input: bool = False, pixel_scale: float = 1.0) -> RenderResult:
    center_x, center_y = mercator_world(latitude, longitude, zoom)
    api_base, token = self._credentials(style)
    tiles, cached = self._get_tiles(style, zoom, center_x, center_y, api_base, token, network_available)
    center_tile_x, center_tile_y = int(center_x // TILE_SIZE), int(center_y // TILE_SIZE)
    origin_x = (center_tile_x - 1) * TILE_SIZE
    origin_y = (center_tile_y - 1) * TILE_SIZE
    background = rl.Color(18, 20, 24, 255) if not model_input else rl.Color(0, 0, 0, 255)
    canvas = rl.gen_image_color(TILE_SIZE * 3, TILE_SIZE * 3, background)
    loaded = 0
    try:
      for (tile_x, tile_y), path in tiles.items():
        tile = rl.load_image(str(path))
        if not rl.is_image_valid(tile):
          continue
        try:
          if tile.width != TILE_SIZE or tile.height != TILE_SIZE:
            rl.image_resize(tile, TILE_SIZE, TILE_SIZE)
          dx = (tile_x - (center_tile_x - 1)) * TILE_SIZE
          dy = (tile_y - (center_tile_y - 1)) * TILE_SIZE
          rl.image_draw(canvas, tile, rl.Rectangle(0, 0, TILE_SIZE, TILE_SIZE),
                        rl.Rectangle(dx, dy, TILE_SIZE, TILE_SIZE), rl.WHITE)
          loaded += 1
        finally:
          rl.unload_image(tile)

      route_color = rl.Color(128, 128, 128, 255) if model_input else rl.Color(48, 178, 255, 255)
      self._draw_route(canvas, route, zoom, origin_x, origin_y, route_color, 5.0 / pixel_scale if model_input else 18.0)
      source_size = MODEL_SOURCE_SIZE if model_input else None
      image = self._heading_crop(canvas, center_x - origin_x, center_y - origin_y, bearing, output_size, source_size, pixel_scale)
      try:
        if model_input:
          taco2_first_channel_grayscale(image)
        else:
          center = output_size / 2
          rl.image_draw_circle_v(image, rl.Vector2(center, center), 22, rl.Color(255, 255, 255, 245))
          rl.image_draw_triangle(image, rl.Vector2(center, center - 18), rl.Vector2(center - 13, center + 13),
                                 rl.Vector2(center + 13, center + 13), rl.Color(22, 115, 255, 255))
        exported = self._export(image, output_path)
      finally:
        rl.unload_image(image)
    finally:
      rl.unload_image(canvas)
    missing = 9 - loaded
    return RenderResult(exported and loaded > 0, missing, cached)


class MapboxMapDaemon:
  def __init__(self, params: Params | None = None, sm=None, pm=None, device_type: str | None = None) -> None:
    self.params = params or Params()
    self.device_type = device_type if device_type is not None else HARDWARE.get_device_type()
    self.sm = sm or messaging.SubMaster(["gpsLocationExternal", "liveLocationKalman", "carState", "deviceState",
                                         "navRoute", "navInstruction", "navigationStateSP"])
    self.pm = pm or messaging.PubMaster(["mapboxNavigationStateSP"])
    self.renderer = MapboxTileRenderer(self.params, self.device_type)
    self.generation = 0

  def _publish(self, *, status: str, display_valid: bool = False, model_valid: bool = False,
               missing: int = 0, cached: bool = False, latitude: float = 0.0, longitude: float = 0.0,
               bearing: float = 0.0, zoom: int = 0, route_id: str = "", location_mono_time: int = 0,
               model_position_valid: bool = False, model_location_mono_time: int = 0,
               render_time: float = 0.0) -> None:
    msg = messaging.new_message("mapboxNavigationStateSP")
    state = msg.mapboxNavigationStateSP
    state.displaySupported = display_map_supported(self.device_type)
    state.displayEnabled = self.params.get_bool("MapboxMapDisplayEnabled") and state.displaySupported
    state.displayImageValid = display_valid
    state.modelImageValid = model_valid
    state.usedCachedTiles = cached
    state.missingTiles = missing
    state.generation = self.generation
    state.displayImagePath = str(self.renderer.output_root / DISPLAY_FILENAME) if display_valid else ""
    state.modelInputPath = str(self.renderer.output_root / MODEL_FILENAME) if model_valid else ""
    state.latitude, state.longitude, state.bearingDeg = latitude, longitude, bearing
    state.zoom = zoom
    state.routeId = route_id
    state.locationMonoTime = location_mono_time
    state.modelPositionValid = model_position_valid
    state.modelLocationMonoTime = model_location_mono_time
    state.renderTime = render_time
    state.status = status
    msg.valid = True
    self.pm.send("mapboxNavigationStateSP", msg)

  def update(self) -> None:
    self.sm.update(0)
    now = time.monotonic()
    display_enabled = self.params.get_bool("MapboxMapDisplayEnabled") and display_map_supported(self.device_type)
    model_enabled = self.params.get_bool("NavigationModelEnabled") and model_map_supported(self.device_type)
    if not display_enabled and not model_enabled:
      status = "unsupportedHardware" if self.params.get_bool("MapboxMapDisplayEnabled") else "disabled"
      self._publish(status=status)
      return

    gps = self.sm["gpsLocationExternal"]
    display_location_valid = bool(service_fresh(self.sm, "gpsLocationExternal", now) and gps.hasFix and
                                  math.isfinite(gps.latitude) and math.isfinite(gps.longitude))

    # Match taco2: the model-facing map follows liveLocationKalman, not raw GPS.
    # This stays independent from the driver-facing display map's location.
    llk = self.sm["liveLocationKalman"]
    model_fresh = service_fresh(self.sm, "liveLocationKalman", now)
    model_pose = taco2_model_location(llk, model_fresh, model_fresh)
    model_location_valid = model_pose is not None
    if ((display_enabled and not display_location_valid) and
        (not model_enabled or not model_location_valid)):
      self._publish(status="waitingForLocation", model_position_valid=model_location_valid)
      return
    if ((model_enabled and not model_location_valid) and
        (not display_enabled or not display_location_valid)):
      self._publish(status="waitingForLocation")
      return

    network_available = bool(service_fresh(self.sm, "deviceState", now) and self.sm.seen["deviceState"] and
                             self.sm["deviceState"].networkType != log.DeviceState.NetworkType.none)
    route_loaded = bool(service_fresh(self.sm, "navRoute", now) and service_fresh(self.sm, "navigationStateSP", now) and
                        self.sm["navigationStateSP"].routeLoaded)
    route = ([(float(c.latitude), float(c.longitude)) for c in self.sm["navRoute"].coordinates]
             if route_loaded else [])
    route_id = str(self.sm["navigationStateSP"].routeId) if route_loaded else ""
    display_latitude = float(gps.latitude) if display_location_valid else model_pose[0]
    display_longitude = float(gps.longitude) if display_location_valid else model_pose[1]
    display_bearing = float(gps.bearingDeg) if display_location_valid and math.isfinite(gps.bearingDeg) else 0.0
    model_latitude, model_longitude, model_bearing = model_pose or (0.0, 0.0, 0.0)
    display_location_mono_time = self.sm.logMonoTime["gpsLocationExternal"] if display_location_valid else 0
    model_location_mono_time = self.sm.logMonoTime["liveLocationKalman"] if model_location_valid else 0
    v_ego = float(self.sm["carState"].vEgo) if self.sm.valid["carState"] else 0.0
    zoom = display_zoom(v_ego)
    self._publish(status="loadingTiles", latitude=display_latitude, longitude=display_longitude,
                  bearing=display_bearing, zoom=zoom, route_id=route_id,
                  location_mono_time=display_location_mono_time, model_position_valid=model_location_valid,
                  model_location_mono_time=model_location_mono_time)
    started = time.monotonic()
    display_result = RenderResult(False, 0, 0)
    model_result = RenderResult(False, 0, 0)
    if display_enabled and display_location_valid:
      display_result = self.renderer.render(style=DISPLAY_STYLE, latitude=display_latitude, longitude=display_longitude,
                                            bearing=display_bearing, zoom=zoom, route=route,
                                            output_path=self.renderer.output_root / DISPLAY_FILENAME,
                                            output_size=DISPLAY_SIZE, network_available=network_available)
    if model_enabled and model_location_valid and route_loaded:
      model_zoom = taco2_zoom_level(model_latitude)
      tile_zoom = taco2_tile_zoom(model_latitude)
      model_result = self.renderer.render(style=TACO2_MODEL_STYLE, latitude=model_latitude, longitude=model_longitude,
                                          bearing=model_bearing, zoom=tile_zoom, route=route,
                                          output_path=self.renderer.output_root / MODEL_FILENAME,
                                          output_size=MODEL_SIZE, network_available=network_available, model_input=True,
                                          pixel_scale=2 ** (model_zoom - tile_zoom))
      # Partial model images are not compatible with the taco2 input contract.
      model_result = RenderResult(model_result.valid and model_result.missing_tiles == 0,
                                  model_result.missing_tiles, model_result.cached_tiles)

    self.generation += 1
    mapbox_token_available = bool(self.renderer._token())
    model_token_available = bool(self.renderer._comma_maps_token()) or mapbox_token_available
    # The shared status fields describe the driver map whenever it exists.
    # Model-map health remains independent through modelImageValid and the
    # navigationModelStateSP status, so a private-style failure cannot make a
    # healthy C3X display claim that its own tiles are incomplete.
    selected_result = display_result if display_enabled else model_result
    missing = selected_result.missing_tiles
    all_requested_cached = selected_result.cached_tiles > 0 and not network_available
    missing_credentials = not (mapbox_token_available if display_enabled else model_token_available)
    # The driver-facing map must never claim to be online/current when its raw
    # GPS source is unavailable, even if the independent taco2 LLK render is
    # healthy. The model-facing validity remains available in its own fields.
    if display_enabled and not display_location_valid:
      status = "waitingForLocation"
    elif missing:
      status = "missingToken" if missing_credentials else "incomplete"
    elif not route_loaded:
      status = "waitingForRoute"
    else:
      status = "cached" if all_requested_cached else "online"
    self._publish(status=status, display_valid=display_result.valid, model_valid=model_result.valid,
                  missing=missing, cached=all_requested_cached, latitude=display_latitude, longitude=display_longitude,
                  bearing=display_bearing, zoom=zoom, route_id=route_id,
                  location_mono_time=display_location_mono_time, model_position_valid=model_location_valid,
                  model_location_mono_time=model_location_mono_time,
                  render_time=time.monotonic() - started)


def main() -> None:
  daemon = MapboxMapDaemon()
  rk = Ratekeeper(1.0)
  while True:
    daemon.update()
    rk.keep_time()


if __name__ == "__main__":
  main()
