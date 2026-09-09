from types import SimpleNamespace

import pytest

from openpilot.selfdrive.ui.sunnypilot.onroad.corner_radar_layout import (
  DisplayCornerTarget, marker_position, panel_bounds, select_display_targets,
)


def target(**values):
  defaults = dict(sensorGroup=0, sourceBus=1, trackId=1, distance=10.0, ageSec=0.05, candidateActive=True)
  return SimpleNamespace(**(defaults | values))


def test_multiple_nearest_targets_per_group():
  records = [target(sensorGroup=group, trackId=i, distance=i + 1) for group in range(4) for i in range(8)]
  chosen = select_display_targets(list(reversed(records)))
  assert len(chosen) == 12
  for group in range(4):
    assert [t.distance_m for t in chosen if t.sensor_group == group] == [1, 2, 3]


@pytest.mark.parametrize('values', [dict(distance=0), dict(distance=float('nan')), dict(distance=121),
                                  dict(ageSec=-1), dict(ageSec=float('nan')), dict(ageSec=0.36),
                                  dict(sourceBus=128), dict(sensorGroup=4), dict(candidateActive=False)])
def test_invalid_targets_are_hidden(values):
  assert select_display_targets([target(**values)]) == []


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
        px, py = marker_position(DisplayCornerTarget(group, 1, column, 120), column, 30, width)
        assert x + 12 <= px <= x + panel_width - 12
        assert 85 <= py <= 265


def test_small_viewport_hides_panels_instead_of_overlapping():
  assert panel_bounds(0, 800, -1) is None
  assert marker_position(DisplayCornerTarget(0, 1, 1, 10), 0, 0, 800) is None


def test_distance_moves_markers_in_separate_front_rear_regions():
  for group in range(4):
    near = marker_position(DisplayCornerTarget(group, 1, 1, 1), 0, 0, 2160)[1]
    far = marker_position(DisplayCornerTarget(group, 1, 1, 120), 0, 0, 2160)[1]
    assert far < near < 180 if group < 2 else 180 < near < far
