from openpilot.cereal import car, log
from openpilot.common.realtime import DT_CTRL
from openpilot.selfdrive.selfdrived.state import StateMachine, SOFT_DISABLE_TIME
from openpilot.selfdrive.selfdrived.events import Events, ET, EVENTS, NormalPermanentAlert, get_current_alert_types

State = log.SelfdriveState.OpenpilotState

# The event types that maintain the current state
MAINTAIN_STATES = {State.enabled: (None,), State.disabled: (None,), State.softDisabling: (ET.SOFT_DISABLE,),
                   State.preEnabled: (ET.PRE_ENABLE,), State.overriding: (ET.OVERRIDE_LATERAL, ET.OVERRIDE_LONGITUDINAL)}
ALL_STATES = tuple(State.schema.enumerants.values())
# The event types checked in DISABLED section of state machine
ENABLE_EVENT_TYPES = (ET.ENABLE, ET.PRE_ENABLE, ET.OVERRIDE_LATERAL, ET.OVERRIDE_LONGITUDINAL)
GearShifter = car.CarState.GearShifter


def make_event(event_types):
  event = {}
  for ev in event_types:
    event[ev] = NormalPermanentAlert("alert")
  EVENTS[0] = event
  return 0


class TestAlwaysLateralAlerts:
  def test_adds_alert_type_while_disengaged(self):
    alert_types = get_current_alert_types([ET.PERMANENT], True, True, GearShifter.drive)
    assert alert_types == [ET.PERMANENT, ET.ALWAYS_LATERAL]

  def test_requires_mode_and_lateral_enabled(self):
    assert get_current_alert_types([ET.PERMANENT], False, True, GearShifter.drive) == [ET.PERMANENT]
    assert get_current_alert_types([ET.PERMANENT], True, False, GearShifter.drive) == [ET.PERMANENT]

  def test_requires_driving_gear(self):
    for gear in (GearShifter.neutral, GearShifter.park, GearShifter.reverse, GearShifter.unknown):
      assert get_current_alert_types([ET.PERMANENT], True, True, gear) == [ET.PERMANENT]

  def test_does_not_duplicate_active_warning(self):
    current_alert_types = [ET.PERMANENT, ET.WARNING]
    alert_types = get_current_alert_types(current_alert_types, True, True, GearShifter.drive)
    assert alert_types == current_alert_types
    assert ET.ALWAYS_LATERAL not in alert_types

  def test_only_expected_events_use_always_lateral_type(self):
    always_lateral_events = {event for event, alerts in EVENTS.items() if ET.ALWAYS_LATERAL in alerts}
    assert always_lateral_events == {
      log.OnroadEvent.EventName.leadCarMoving,
      log.OnroadEvent.EventName.trafficSignGreen,
      log.OnroadEvent.EventName.trafficSignChanged,
    }

  def test_always_lateral_type_serializes(self):
    events = Events()
    events.add(log.OnroadEvent.EventName.leadCarMoving)
    event, = events.to_msg()
    assert event.warning
    assert event.alwaysLateral


class TestStateMachine:
  def setup_method(self):
    self.events = Events()
    self.state_machine = StateMachine()
    self.state_machine.soft_disable_timer = int(SOFT_DISABLE_TIME / DT_CTRL)

  def test_immediate_disable(self):
    for state in ALL_STATES:
      for et in MAINTAIN_STATES[state]:
        self.events.add(make_event([et, ET.IMMEDIATE_DISABLE]))
        self.state_machine.state = state
        self.state_machine.update(self.events)
        assert State.disabled == self.state_machine.state
        self.events.clear()

  def test_user_disable(self):
    for state in ALL_STATES:
      for et in MAINTAIN_STATES[state]:
        self.events.add(make_event([et, ET.USER_DISABLE]))
        self.state_machine.state = state
        self.state_machine.update(self.events)
        assert State.disabled == self.state_machine.state
        self.events.clear()

  def test_soft_disable(self):
    for state in ALL_STATES:
      if state == State.preEnabled:  # preEnabled considers NO_ENTRY instead
        continue
      for et in MAINTAIN_STATES[state]:
        self.events.add(make_event([et, ET.SOFT_DISABLE]))
        self.state_machine.state = state
        self.state_machine.update(self.events)
        assert self.state_machine.state == State.disabled if state == State.disabled else State.softDisabling
        self.events.clear()

  def test_soft_disable_timer(self):
    self.state_machine.state = State.enabled
    self.events.add(make_event([ET.SOFT_DISABLE]))
    self.state_machine.update(self.events)
    for _ in range(int(SOFT_DISABLE_TIME / DT_CTRL)):
      assert self.state_machine.state == State.softDisabling
      self.state_machine.update(self.events)

    assert self.state_machine.state == State.disabled

  def test_no_entry(self):
    # Make sure noEntry keeps us disabled
    for et in ENABLE_EVENT_TYPES:
      self.events.add(make_event([ET.NO_ENTRY, et]))
      self.state_machine.update(self.events)
      assert self.state_machine.state == State.disabled
      self.events.clear()

  def test_no_entry_pre_enable(self):
    # preEnabled with noEntry event
    self.state_machine.state = State.preEnabled
    self.events.add(make_event([ET.NO_ENTRY, ET.PRE_ENABLE]))
    self.state_machine.update(self.events)
    assert self.state_machine.state == State.preEnabled

  def test_maintain_states(self):
    # Given current state's event type, we should maintain state
    for state in ALL_STATES:
      for et in MAINTAIN_STATES[state]:
        self.state_machine.state = state
        self.events.add(make_event([et]))
        self.state_machine.update(self.events)
        assert self.state_machine.state == state
        self.events.clear()
