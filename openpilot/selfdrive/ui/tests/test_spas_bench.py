"""Offline unit tests of the pinned production function; no CAN socket is opened."""
import ast
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from openpilot.selfdrive.ui.sunnypilot.onroad.spas_bench import SpasBenchSession, duration_seconds


ROOT = Path(__file__).resolve().parents[4] / 'opendbc_repo'
tree = ast.parse((ROOT / 'opendbc/car/hyundai/hyundaicanfd.py').read_text())
function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'create_spas_messages')
namespace = {}
# Execute the exact source function while excluding unrelated hardware imports.
exec(compile(ast.Module(body=[function], type_ignores=[]), 'hyundaicanfd.py', 'exec'), namespace)
create_spas_messages = namespace['create_spas_messages']


class RecordingPacker:
  def __init__(self):
    self.calls = []

  def make_can_msg(self, name, bus, values):
    result = (name, bus, values.copy())
    self.calls.append(result)
    return result


class TestSpas(unittest.TestCase):
  def check_request(self, left, right, expected):
    packer = RecordingPacker()
    result = create_spas_messages(packer, SimpleNamespace(ECAN=1), left, right)
    self.assertEqual(result, [('SPAS1', 1, {}), ('SPAS2', 1, {'BLINKER_CONTROL': expected})])
    self.assertEqual(packer.calls, result)

  def test_neutral_control_value_zero(self):
    self.check_request(False, False, 0)

  def test_left_control_value_three(self):
    self.check_request(True, False, 3)

  def test_right_control_value_four(self):
    self.check_request(False, True, 4)

  def test_simultaneous_requests_prioritize_left_not_hazards(self):
    self.check_request(True, True, 3)

  def test_uses_configured_ecan_bus(self):
    for bus in (0, 1, 4, 5):
      with self.subTest(bus=bus):
        result = create_spas_messages(RecordingPacker(), SimpleNamespace(ECAN=bus), True, False)
        self.assertEqual([msg[1] for msg in result], [bus, bus])

  def test_direction_changes_and_neutral_have_no_latched_state(self):
    packer, can = RecordingPacker(), SimpleNamespace(ECAN=1)
    sequence = [(True, False), (False, False), (False, True), (False, False)]
    actual = [create_spas_messages(packer, can, left, right)[1][2]['BLINKER_CONTROL'] for left, right in sequence]
    self.assertEqual(actual, [3, 0, 4, 0])

  def test_repeated_calls_do_not_automatically_stop(self):
    packer, can = RecordingPacker(), SimpleNamespace(ECAN=1)
    for _ in range(1000):
      self.assertEqual(create_spas_messages(packer, can, True, False)[1][2]['BLINKER_CONTROL'], 3)

  def test_message_names_and_controls_match_pinned_dbc(self):
    dbc = (ROOT / 'opendbc/dbc/generator/hyundai/hyundai_canfd.dbc').read_text()
    definitions = {name: (int(address), int(length))
                   for address, name, length in re.findall(r'^BO_ (\d+) (\w+): (\d+)', dbc, re.M)}
    self.assertEqual(definitions['SPAS1'], (0x165, 24))
    self.assertEqual(definitions['SPAS2'], (0x16A, 32))
    block = dbc.split('BO_ 362 SPAS2:', 1)[1].split('\nBO_', 1)[0]
    self.assertRegex(block, r'SG_ BLINKER_CONTROL\s+: 133\|3@1\+')
    value_line = next(line for line in dbc.splitlines() if line.startswith('VAL_ 362 BLINKER_CONTROL '))
    self.assertIn('3 "left blinkers"', value_line)
    self.assertIn('4 "right blinkers"', value_line)
    self.assertIn('1 "hazards"', value_line)


class TestBenchTimer(unittest.TestCase):
  def test_duration_limits_and_default(self):
    for value, expected in [(None, 7), ('bad', 7), (0, 3), (3, 3), (7, 7), (8, 8), (100, 8)]:
      self.assertEqual(duration_seconds(value), expected)

  def test_timeout_at_selected_duration(self):
    for duration in range(3, 9):
      bench = SpasBenchSession(create_spas_messages)
      bench.start('left', duration, 10)
      bench.update(10 + duration - 0.01)
      self.assertEqual(bench.control_value, 3)
      bench.update(10 + duration)
      self.assertEqual(bench.control_value, 0)
      self.assertIsNone(bench.direction)

  def test_stop_is_immediate_and_idempotent(self):
    bench = SpasBenchSession(create_spas_messages)
    bench.start('right', 7, 10)
    self.assertEqual(bench.control_value, 4)
    bench.stop()
    bench.stop()
    self.assertEqual(bench.control_value, 0)
    self.assertEqual(bench.remaining(11), 0)

  def test_switching_direction_restarts_countdown(self):
    bench = SpasBenchSession(create_spas_messages)
    bench.start('left', 7, 10)
    bench.start('right', 3, 11)
    self.assertEqual(bench.control_value, 4)
    self.assertEqual(bench.remaining(12), 2)
    bench.update(14)
    self.assertEqual(bench.control_value, 0)

  def test_invalid_direction_rejected(self):
    bench = SpasBenchSession(create_spas_messages)
    with self.assertRaises(ValueError):
      bench.start('both', 7, 10)
    self.assertFalse(bench.messages)


