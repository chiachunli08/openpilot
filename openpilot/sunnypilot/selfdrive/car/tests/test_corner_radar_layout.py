from types import SimpleNamespace

import pytest

from openpilot.selfdrive.ui.sunnypilot.onroad.corner_radar_layout import (
  DisplayCornerTarget,
  estimate_corner_object_velocity,
  marker_position,
  panel_bounds,
  scene_position,
  select_display_targets,
)


def target(**values):
  defaults = dict(
    sensorGroup=0,
    sourceBus=1,
    trackId=1,
    distance=10.0,
    longitudinal=9.5,
    lateral=1.0,
    ageSec=0.05,
    candidateActive=True,
    estimatedRadialSpeed=0.0,
    estimatedRadialSpeedValid=False,
  )
  return SimpleNamespace(**(defaults | values))


def display_target(group=0, distance=10.0, longitudinal=9.5, lateral=1.0, radial_speed=None):
  return DisplayCornerTarget(group, 1, 1, distance, longitudinal, lateral, radial_speed)


def test_multiple_nearest_targets_per_group():
  records = [
    target(sensorGroup=group, trackId=i, distance=i + 1, longitudinal=i + 1)
    for group in range(4) for i in range(8)
  ]
  chosen = select_display_targets(list(reversed(records)))
  assert len(chosen) == 12
  for group in range(4):
    assert [t.distance_m for t in chosen if t.sensor_group == group] == [1, 2, 3]


@pytest.mark.parametrize('values', [
  dict(distance=0), dict(distance=float('nan')), dict(distance=121),
  dict(longitudinal=float('nan')), dict(lateral=float('nan')),
  dict(ageSec=-1), dict(ageSec=float('nan')), dict(ageSec=0.36),
  dict(sourceBus=128), dict(sensorGroup=4), dict(candidateActive=False),
])
def test_invalid_targets_are_hidden(values):
  assert select_display_targets([target(**values)]) == []


def test_radial_speed_is_only_exposed_when_valid_and_finite():
  chosen = select_display_targets([target(estimatedRadialSpeed=-2.5, estimatedRadialSpeedValid=True)])
  assert chosen[0].estimated_radial_speed_mps == pytest.approx(-2.5)

  chosen = select_display_targets([target(estimatedRadialSpeed=float('nan'), estimatedRadialSpeedValid=True)])
  assert chosen[0].estimated_radial_speed_mps is None


def test_frozen_message_ages_out_without_new_receive():
  assert select_display_targets([target()], 0.1)
  assert not select_display_targets([target()], 0.31)
  assert not select_display_targets([target()], -0.1)
  assert not select_display_targets([target()], float('nan'))
  assert not select_display_targets([])


@pytest.mark.parametrize('width', [1080, 1440, 1920, 2160])
def test_panels_do_not_overlap_speed_or_either_blindspot_layout(width):
  for side in (-1, 1):
    x, panel_width = panel_bounds(30, width, side)
    center = 30 + width / 2
    assert x >= 30 + 148
    assert x + panel_width <= 30 + width - 148
    assert x + panel_width <= center - 250 if side < 0 else x >= center + 250
    for group in ((0, 2) if side < 0 else (1, 3)):
      for column in range(3):
        px, py = marker_position(display_target(group=group, distance=120, longitudinal=20), column, 30, width)
        assert x + 12 <= px <= x + panel_width - 12
        assert 85 <= py <= 265


def test_small_viewport_hides_panels_instead_of_overlapping():
  assert panel_bounds(0, 800, -1) is None
  assert marker_position(display_target(), 0, 0, 800) is None


def test_distance_moves_markers_in_separate_front_rear_regions():
  for group in range(4):
    near = marker_position(display_target(group=group, distance=1), 0, 0, 2160)[1]
    far = marker_position(display_target(group=group, distance=120), 0, 0, 2160)[1]
    assert far < near < 180 if group < 2 else 180 < near < far


def test_scene_projection_uses_radar_left_positive_coordinates():
  left = scene_position(30.0, 2.0, 0.0, 0.0, 1920.0, 1080.0)
  center = scene_position(30.0, 0.0, 0.0, 0.0, 1920.0, 1080.0)
  right = scene_position(30.0, -2.0, 0.0, 0.0, 1920.0, 1080.0)
  assert left is not None and center is not None and right is not None
  assert left[0] < center[0] < right[0]


def test_scene_projection_rejects_rear_and_extreme_side_targets():
  assert scene_position(-5.0, 1.0, 0.0, 0.0, 1920.0, 1080.0) is None
  assert scene_position(30.0, 9.0, 0.0, 0.0, 1920.0, 1080.0) is None
  assert scene_position(101.0, 0.0, 0.0, 0.0, 1920.0, 1080.0) is None


def test_corner_speed_estimate_is_marked_as_approximate_input():
  tracked = display_target(distance=20.0, longitudinal=20.0, lateral=0.0, radial_speed=-2.0)
  velocity = estimate_corner_object_velocity(tracked, ego_speed_mps=12.0)
  assert velocity is not None
  abs_long, abs_lat, speed = velocity
  assert abs_long == pytest.approx(10.0)
  assert abs_lat == pytest.approx(0.0)
  assert speed == pytest.approx(10.0)


def test_corner_speed_estimate_requires_valid_range_rate():
  assert estimate_corner_object_velocity(display_target(radial_speed=None), 12.0) is None
