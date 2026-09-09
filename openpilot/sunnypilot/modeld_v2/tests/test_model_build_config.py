"""Check generated SCons targets and their rebuild dependencies without a GPU."""
import os
import runpy
import shlex
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
MODEL_DIR = ROOT / "openpilot/selfdrive/modeld"


class Node:
  def __init__(self, path):
    path = str(path)
    self.path = (ROOT / path[1:]) if path.startswith("#") else (MODEL_DIR / path)
    self.abspath, self.relpath = str(self.path), os.path.relpath(self.path, ROOT)

  def __str__(self):
    return self.abspath

  def File(self, path):
    return Node(self.path / path)


class BuildGraph:
  def __init__(self):
    self.commands = []
    self.side_effects = []

  def Clone(self):
    return self

  def Dir(self, path):
    return Node(path)

  def Command(self, target, source, action):
    node = (target, source, action)
    self.commands.append(node)
    return node

  def SideEffect(self, lock, node):
    self.side_effects.append((lock, node))


class TestModelBuildConfig(unittest.TestCase):
  def build_graph(self, arch, skip=False):
    graph = BuildGraph()
    from openpilot.common.file_chunker import get_chunk_targets
    with patch.dict(os.environ, {"SKIP_TINYGRAD_COMPILE": "1" if skip else ""}), \
         patch("glob.glob", return_value=[]), patch("os.path.getsize", return_value=1_000_000), \
         patch("openpilot.selfdrive.modeld.helpers.chestnut_present", return_value=True), \
         patch("openpilot.common.file_chunker.get_existing_chunks", side_effect=lambda path: [path]), \
         patch("openpilot.common.file_chunker.get_chunk_targets", wraps=get_chunk_targets) as chunks, \
         patch("SCons.Script.Action", side_effect=lambda function, label: function), \
         patch("SCons.Script.Value", side_effect=lambda value: value):
      runpy.run_path(str(MODEL_DIR / "SConscript"), init_globals={
        "env": graph, "arch": arch, "Import": lambda *args: None, "File": Node, "Dir": Node,
      })
    return graph, chunks.call_args_list

  def test_both_cameras_and_chunk_budget_on_all_build_hosts(self):
    for arch in ("comma_arm64", "x86_64", "Darwin"):
      with self.subTest(arch=arch):
        graph, chunk_calls = self.build_graph(arch)
        dm_warps = [str(target) for target, _, _ in graph.commands if "dm_warp_" in str(target)]
        self.assertTrue(any("1928x1208" in target for target in dm_warps))
        self.assertTrue(any("1344x760" in target for target in dm_warps))
        driving = [call for call in chunk_calls if "driving_tinygrad" in str(call.args[0])]
        self.assertEqual(len(driving), 2)
        self.assertTrue(all(call.args[1] >= 4 * 1_000_000 for call in driving))
        for _, sources, _ in graph.commands:
          if any("driving_supercombo.onnx" in str(source) for source in sources):
            self.assertIn("1928x1208 1344x760", sources)

  def test_chestnut_flags_and_port_are_rebuild_dependencies(self):
    graph, _ = self.build_graph("comma_arm64")
    self.assertEqual(len(graph.side_effects), 1)
    _, (_, sources, action) = graph.side_effects[0]
    flags = next(source for source in sources if isinstance(source, str) and source.startswith("DEBUG="))
    values = dict(part.split("=", 1) for part in shlex.split(flags))
    self.assertEqual(values, {"DEBUG": "1", "DEV": "USB+AMD:LLVM", "FRAME_DEV": "CPU", "FLOAT16": "1",
                              "JIT_BATCH_SIZE": "0", "GMMU": "0", "TC_OPT": "2", "TC_MIN_GLOBALS": "32"})
    self.assertTrue(any(str(source).endswith("compile_optimizations.py") for source in sources))
    command = action.__defaults__[0]
    self.assertTrue(command.startswith(flags))
    self.assertIn("taskset -c 7", command)
    self.assertIn("--camera-resolutions 1928x1208 1344x760", command)

  def test_prebuilt_skip_keeps_both_driver_monitoring_warps(self):
    graph, _ = self.build_graph("comma_arm64", skip=True)
    self.assertFalse(graph.side_effects)
    self.assertFalse(any("driving_supercombo.onnx" in str(source) for _, sources, _ in graph.commands for source in sources))
    self.assertEqual(sum("dm_warp_" in str(target) for target, _, _ in graph.commands), 2)


if __name__ == "__main__":
  unittest.main()
