from openpilot.selfdrive.selfdrived.blind_spot import LEFT, RIGHT, warning_direction


def test_warning_direction():
  cases = [
    (True, False, True, False, LEFT),
    (True, False, True, True, LEFT),
    (True, False, False, True, None),
    (False, True, False, True, RIGHT),
    (False, True, True, True, RIGHT),
    (False, True, True, False, None),
    (False, False, True, True, None),
    (True, True, True, True, None),
  ]

  for case in cases:
    left_blinker, right_blinker, left_blindspot, right_blindspot, expected = case
    assert warning_direction(left_blinker, right_blinker, left_blindspot, right_blindspot) == expected
