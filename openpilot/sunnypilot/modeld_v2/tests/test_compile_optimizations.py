"""Exercise the compiler port without a Chestnut or vehicle connection."""
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


class TestCompileOptimizations(unittest.TestCase):
  def run_python(self, source, *args):
    env = dict(os.environ, DEV="PYTHON::gfx1201", PARALLEL="0", TC_OPT="2", TC_MIN_GLOBALS="32")
    result = subprocess.run([sys.executable, "-c", textwrap.dedent(source), *args], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=60)
    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

  def test_importing_runtime_helpers_does_not_install_optimizer(self):
    self.run_python("""
      from tinygrad.codegen.opt import heuristic
      import tinygrad.codegen as codegen
      original, config = heuristic.hand_coded_optimizations, codegen.to_program_config
      import openpilot.selfdrive.modeld.compile_modeld
      import openpilot.sunnypilot.modeld_v2.compile_modeld
      assert heuristic.hand_coded_optimizations is original
      assert codegen.to_program_config == config
    """)

  def test_flag_changes_program_and_cache_identity(self):
    self.run_python("""
      from openpilot.sunnypilot.modeld_v2.compile_optimizations import configure_tensor_core_optimizer
      first = configure_tensor_core_optimizer()
      assert first == configure_tensor_core_optimizer()
      from tinygrad import Tensor, Device, dtypes
      from tinygrad.codegen import to_program, to_program_key
      from tinygrad.helpers import Context, prod
      from tinygrad.uop.ops import Ops
      a, b = Tensor.empty(256, 16, dtype=dtypes.half), Tensor.empty(16, 256, dtype=dtypes.half)
      ast, renderer = (a @ b).schedule_linear().src[-1].src[0], Device.default.renderer
      with Context(TC_MIN_GLOBALS=0):
        old_key, old = to_program_key(ast, renderer), to_program(ast, renderer)
      with Context(TC_MIN_GLOBALS=32):
        new_key, new = to_program_key(ast, renderer), to_program(ast, renderer)
        assert to_program(ast, renderer) is new
      assert old_key != new_key
      assert old.src[-1].arg != new.src[-1].arg
      assert prod(new.arg.global_size) > prod(old.arg.global_size)
      assert any(u.op is Ops.WMMA for u in new.src[1].src)
    """)

  def test_spawned_workers_apply_flag_and_match_parent(self):
    self.run_python("""
      from openpilot.sunnypilot.modeld_v2.compile_optimizations import configure_tensor_core_optimizer
      configure_tensor_core_optimizer()
      from tinygrad import Tensor, Device, dtypes
      import tinygrad.codegen as codegen
      import tinygrad.engine.realize as realize
      from tinygrad.engine.worker import get_worker_pool, terminate_worker_pool
      from tinygrad.helpers import Context
      a, b = Tensor.empty(256, 16, dtype=dtypes.half), Tensor.empty(16, 256, dtype=dtypes.half)
      ast, renderer = (a @ b).schedule_linear().src[-1].src[0], Device.default.renderer
      expected, tasks = [], []
      for index, floor in enumerate((0, 32)):
        with Context(TC_MIN_GLOBALS=floor):
          expected.append(codegen.to_program(ast, renderer))
          context = {v.key: v.value for v in realize.to_program_context}
          assert context['TC_MIN_GLOBALS'] == floor
          tasks.append((index, (ast, renderer), context))
      try:
        with Context(PARALLEL=2):
          results = get_worker_pool().map(realize._compile_kernel, tasks)
        for index, program in results:
          assert program.arg.global_size == expected[index].arg.global_size
          assert program.arg.local_size == expected[index].arg.local_size
          assert program.src[-1].arg == expected[index].src[-1].arg
      finally:
        terminate_worker_pool()
    """)

  def test_rdna4_math_and_pickle_replay_without_compiler_patch(self):
    with tempfile.TemporaryDirectory() as directory:
      self.run_python("""
        import sys
        from pathlib import Path
        import numpy as np
        from openpilot.sunnypilot.modeld_v2.compile_optimizations import configure_tensor_core_optimizer
        configure_tensor_core_optimizer()
        from openpilot.selfdrive.modeld.helpers import dump_oob
        from tinygrad import Tensor, TinyJit
        from tinygrad.helpers import Context
        rng = np.random.default_rng(42)
        a = rng.uniform(-1, 1, (32, 16)).astype(np.float16)
        b = rng.uniform(-1, 1, (16, 32)).astype(np.float16)
        expected = a.astype(np.float32) @ b.astype(np.float32)
        np.savez(Path(sys.argv[1]) / 'inputs.npz', a=a, b=b, expected=expected)
        for floor in (0, 32):
          with Context(TC_MIN_GLOBALS=floor):
            jit = TinyJit(lambda x, y: (x @ y).float().realize())
            for _ in range(3):
              result = jit(Tensor(a), Tensor(b)).numpy()
              np.testing.assert_allclose(result, expected, atol=3e-3, rtol=3e-3)
            with open(Path(sys.argv[1]) / f'{floor}.pkl', 'wb') as f:
              dump_oob(jit, f)
      """, directory)
      self.run_python("""
        import sys
        from pathlib import Path
        import numpy as np
        from tinygrad import Tensor
        from tinygrad.codegen.opt import heuristic
        from openpilot.selfdrive.modeld.helpers import load_oob
        assert heuristic.hand_coded_optimizations.__module__ == 'tinygrad.codegen.opt.heuristic'
        data = np.load(Path(sys.argv[1]) / 'inputs.npz')
        for floor in (0, 32):
          with open(Path(sys.argv[1]) / f'{floor}.pkl', 'rb') as f:
            jit = load_oob(f)
          for scale in (1.0, -1.0):
            actual = jit(Tensor(data['a'] * scale), Tensor(data['b'])).numpy()
            np.testing.assert_allclose(actual, data['expected'] * scale, atol=3e-3, rtol=3e-3)
      """, directory)


if __name__ == "__main__":
  unittest.main()
