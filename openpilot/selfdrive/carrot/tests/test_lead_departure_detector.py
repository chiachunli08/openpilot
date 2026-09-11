from openpilot.selfdrive.carrot.lead_departure import LeadDepartureDetector


DT = 0.1


def update_for(detector, seconds, *, ego_stopped=True, status=True, d_rel=10.0, v_lead=0.0, v_rel=0.0, track_id=1):
  results = []
  for _ in range(round(seconds / DT)):
    results.append(detector.update(ego_stopped, status, d_rel, v_lead, v_rel, track_id))
  return results


def armed_detector():
  detector = LeadDepartureDetector(dt=DT)
  assert not any(update_for(detector, 1.0))
  assert detector.armed
  return detector


def test_stopped_lead_departure_is_confirmed_once():
  detector = armed_detector()

  assert not any(update_for(detector, 0.2, d_rel=10.4, v_lead=1.2, v_rel=1.2))
  assert detector.update(True, True, 10.6, 1.2, 1.2, 1)
  assert not any(update_for(detector, 1.0, d_rel=12.0, v_lead=2.0, v_rel=2.0))


def test_lead_already_moving_does_not_arm():
  detector = LeadDepartureDetector(dt=DT)

  assert not any(update_for(detector, 2.0, v_lead=1.0, v_rel=1.0))
  assert not detector.armed


def test_single_speed_spike_does_not_trigger():
  detector = armed_detector()

  assert not detector.update(True, True, 10.2, 1.5, 1.5, 1)
  assert not detector.update(True, True, 10.2, 0.0, 0.0, 1)
  assert not any(update_for(detector, 0.3, d_rel=10.2, v_lead=0.0, v_rel=0.0))


def test_slow_pullaway_triggers_after_distance_gain():
  detector = armed_detector()

  assert not any(update_for(detector, 0.2, d_rel=11.2, v_lead=0.35, v_rel=0.35))
  assert detector.update(True, True, 11.3, 0.35, 0.35, 1)


def test_track_change_must_rearm():
  detector = armed_detector()

  assert not any(update_for(detector, 0.5, d_rel=20.0, v_lead=2.0, v_rel=2.0, track_id=2))
  assert not detector.armed
  assert not any(update_for(detector, 1.0, d_rel=20.0, track_id=2))
  assert detector.armed


def test_ego_movement_resets_detector():
  detector = armed_detector()

  assert not detector.update(False, True, 10.5, 1.0, 1.0, 1)
  assert not detector.armed
  assert not detector.notified


def test_short_lead_dropout_is_tolerated():
  detector = armed_detector()

  assert not any(update_for(detector, 0.2, status=False))
  assert detector.armed
  assert not any(update_for(detector, 0.2, d_rel=10.5, v_lead=1.2, v_rel=1.2))
  assert detector.update(True, True, 10.6, 1.2, 1.2, 1)
