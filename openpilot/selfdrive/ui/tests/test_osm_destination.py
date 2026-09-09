"""Exercise destination callbacks without loading the native display or Params library."""
import ast
import builtins
import datetime
import json
import threading
import unittest
from concurrent.futures import Future, ThreadPoolExecutor
from enum import IntEnum
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

from openpilot.sunnypilot.navd.destination_input import parse_coordinate_destination
from openpilot.sunnypilot.navd.mapbox_token_codec import decode_mapbox_public_token, decode_mapbox_secret_token


class TestOsmDestination(unittest.TestCase):
  def setUp(self):
    root = Path(__file__).resolve().parents[3]
    # Use the real Params conversion table and method, without its native library.
    tree = ast.parse((root / "common/params.py").read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ParamKeyType" or
             isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PYTHON_2_CPP" for t in n.targets)]
    params_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Params")
    nodes += [n for n in params_class.body if isinstance(n, ast.FunctionDef) and n.name == "python2cpp"]
    casts = {"IntEnum": IntEnum, "builtins": builtins, "datetime": datetime, "json": json}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "params.py", "exec"), casts)
    self.params = Mock()
    self.params.put.side_effect = lambda key, value, **kw: casts["python2cpp"](None, type(value), casts["ParamKeyType"].JSON, value, key)
    self.gui = Mock()
    self.state = NS(params=self.params, is_onroad=lambda: False)
    self.requests = NS(get=Mock(), RequestException=ConnectionError)
    self.main_thread = threading.get_ident()

    def dialog(*args, **kwargs):
      self.assertEqual(threading.get_ident(), self.main_thread)
      return NS(**kwargs)

    namespace = {"ui_state": self.state, "gui_app": self.gui, "tr": lambda s: s, "ConfirmDialog": dialog, "alert_dialog": lambda s: s,
                 "DialogResult": NS(CONFIRM=1), "requests": self.requests, "parse_coordinate_destination": parse_coordinate_destination,
                 "decode_mapbox_public_token": decode_mapbox_public_token, "decode_mapbox_secret_token": decode_mapbox_secret_token}
    source = root / "selfdrive/ui/sunnypilot/layouts/settings/osm.py"
    layout = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.ClassDef))
    methods = {"_resolve_navigation_destination", "_finish_navigation_destination", "_save_navigation_destination"}
    layout.bases = []
    layout.body = [n for n in layout.body if isinstance(n, ast.FunctionDef) and n.name in methods]
    exec(compile(ast.Module(body=[layout], type_ignores=[]), str(source), "exec"), namespace)
    self.layout = namespace["OSMLayout"]()
    self.layout._navigation_destination = Mock()

  def test_coordinates_resolve_in_worker_and_confirm_on_main_thread(self):
    with ThreadPoolExecutor() as executor:
      job = executor.submit(self.layout._resolve_navigation_destination, "25.033, 121.565")
      destination = job.result()
    self.gui.push_widget.assert_not_called()
    self.layout._destination_job = job
    self.layout._finish_navigation_destination()
    confirmation = self.gui.push_widget.call_args.args[0]
    confirmation.callback(1)
    self.params.put.assert_called_once_with("NavDestination", destination, block=True)
    self.assertIsNone(self.layout._destination_job)
    # The former JSON-string callback fails against the actual Params contract.
    with self.assertRaises(TypeError):
      self.params.put("NavDestination", json.dumps(destination))

  def test_cancel_does_not_save(self):
    self.layout._save_navigation_destination(0, {})
    self.params.put.assert_not_called()

  def test_write_failure_shows_error(self):
    self.params.put.side_effect = OSError("disk")
    self.layout._save_navigation_destination(1, {})
    self.assertIn("Unable to save", self.gui.push_widget.call_args.args[0])

  def test_search_failure_restores_button(self):
    self.layout._destination_job = Future()
    self.layout._destination_job.set_exception(ConnectionError())
    self.layout._finish_navigation_destination()
    self.assertIn("Unable to resolve", self.gui.push_widget.call_args.args[0])
    self.layout._navigation_destination.action_item.set_enabled.assert_called_once_with(True)

  def test_onroad_discards_completed_search(self):
    self.state.is_onroad = lambda: True
    self.layout._destination_job = Future()
    self.layout._destination_job.set_result({})
    self.layout._finish_navigation_destination()
    self.gui.push_widget.assert_not_called()

  def test_address_search_returns_data_without_touching_ui(self):
    self.params.get.side_effect = lambda key: "pk.test" if key == "MapboxPublicKey" else "en"
    self.requests.get.return_value.json.return_value = {
      "features": [{"geometry": {"coordinates": [121.565, 25.033]}, "properties": {"name": "Taipei"}}]}
    with ThreadPoolExecutor() as executor:
      result = executor.submit(self.layout._resolve_navigation_destination, "Taipei").result()
    self.assertEqual(result["latitude"], 25.033)
    self.assertEqual(result["place_name"], "Taipei")
    self.gui.push_widget.assert_not_called()
