import unittest

try:
  from onnx import TensorProto, helper
except ImportError:
  helper = None  # optional developer dependency, not required by the OSM tool

from openpilot.sunnypilot.navd.tools.audit_route_model import inspect_graph


@unittest.skipIf(helper is None, "model audit tests require the optional onnx package")
class TestAuditRouteModel(unittest.TestCase):
  def model(self, connected, navigation=True):
    inputs = [helper.make_tensor_value_info("vision", TensorProto.FLOAT, [1, 64])]
    if navigation:
      inputs.append(helper.make_tensor_value_info("nav_features", TensorProto.FLOAT, [1, 64]))
    output = helper.make_tensor_value_info("plan", TensorProto.FLOAT, [1, 64])
    node = helper.make_node("Identity", ["nav_features" if connected else "vision"], ["plan"])
    return helper.make_model(helper.make_graph([node], "probe", inputs, [output]))

  def test_no_navigation_input(self):
    self.assertEqual(inspect_graph(self.model(False, navigation=False))["status"], "no_named_navigation_input")

  def test_unused_navigation_input_does_not_prove_route_conditioning(self):
    report = inspect_graph(self.model(False))
    self.assertEqual(report["direct_output_dependencies"], {"nav_features": []})
    self.assertFalse(report["model_input_ready"])

  def test_connected_input_still_requires_trained_encoder_contract(self):
    report = inspect_graph(self.model(True))
    self.assertEqual(report["direct_output_dependencies"], {"nav_features": ["plan"]})
    self.assertEqual(report["status"], "requires_paired_encoder_and_weight_validation")
    self.assertFalse(report["model_input_ready"])


if __name__ == "__main__":
  unittest.main()
