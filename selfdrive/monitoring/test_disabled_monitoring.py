from openpilot.selfdrive.monitoring.dmonitoringd import disabled_driver_monitoring_state


def test_disabled_driver_monitoring_state():
  msg = disabled_driver_monitoring_state()
  state = msg.driverMonitoringState

  assert msg.valid
  assert len(state.events) == 0
  assert state.awarenessStatus == 1.0
  assert state.awarenessActive == 1.0
  assert state.awarenessPassive == 1.0
  assert not state.isDistracted
  assert not state.isActiveMode
