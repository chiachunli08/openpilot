"""Compile-only port of tinygrad f6fc4e3's TC_MIN_GLOBALS heuristic.

Keep sunnypilot's e837e36 runtime paired with its downloaded model catalog. The
upstream heuristic uses OptOps.SPLIT; this port uses that revision's equivalent
UPCAST/LOCAL operations. No serialized types or inference code are replaced.

Source (MIT): https://github.com/tinygrad/tinygrad/commit/f6fc4e3f2c3db5fae1e19cbfbc3ad9fc579a12ae
"""

UPSTREAM_OPTIMIZER_COMMIT = "f6fc4e3f2c3db5fae1e19cbfbc3ad9fc579a12ae"
_original_heuristic = None


def _hand_coded_optimizations(k):
  from tinygrad.codegen.opt import Opt, OptOps, KernelOptError
  from tinygrad.helpers import Context, TC_OPT, TC_SELECT, TC_MIN_GLOBALS, USE_TC, prod
  from tinygrad.uop.ops import AxisType, resolve

  if not TC_MIN_GLOBALS:
    return _original_heuristic(k)

  if USE_TC > 0 and (len(k.axes_of(AxisType.GROUP_REDUCE, AxisType.REDUCE)) == 1 or TC_OPT.value >= 1):
    for axis in range(3):
      tk = k.copy()
      try:
        rngs = tk.apply_opt(Opt(OptOps.TC, axis, (TC_SELECT.value, TC_OPT.value, USE_TC.value)))
      except KernelOptError:
        continue

      def split(idx, size, op, tk=tk, rngs=rngs):
        rngs[idx] = tk.apply_opt(Opt(op, tk.rngs.index(rngs[idx]), size))[0]

      # Upcast M, local N, then upcast N only if enough global work remains.
      if (size := next((s for s in [5, 4, 3, 2] if rngs[1].src[0].divides(s) is not None), None)) is not None:
        split(1, size, OptOps.UPCAST)
      if (size := next((s for s in [4, 2] if rngs[0].src[0].divides(s) is not None), None)) is not None:
        split(0, size, OptOps.LOCAL)
      if ((size := next((s for s in [5, 4, 3, 2] if rngs[0].src[0].divides(s) is not None), None)) is not None and
          resolve(prod(tk.full_shape[i] for i in tk.axes_of(AxisType.GLOBAL)) >= size * TC_MIN_GLOBALS.value, False)):
        split(0, size, OptOps.UPCAST)
      return tk

  # Tensor cores did not apply. Retain the pinned compiler's other optimizations.
  with Context(TC=0):
    return _original_heuristic(k)


def _compile_kernel(task):
  # tinygrad spawns workers without reimporting the compiler's __main__. Install
  # the port before applying the task's Context, including on replacement workers.
  configure_tensor_core_optimizer()
  from tinygrad.codegen import to_program
  from tinygrad.helpers import Context
  with Context(**task[2]):
    return task[0], to_program(*task[1])


def configure_tensor_core_optimizer() -> dict:
  """Called by compiler entry points, never while importing them in modeld."""
  global _original_heuristic
  from tinygrad import helpers

  if _original_heuristic is not None:
    implementation = "sunnypilot-e837e36-backport"
  elif hasattr(helpers, "TC_MIN_GLOBALS"):
    implementation = "native"
  else:
    import tinygrad.codegen as codegen
    import tinygrad.engine.realize as realize
    from tinygrad.codegen.opt import OptOps
    from tinygrad.codegen.opt import heuristic

    if not all(hasattr(OptOps, name) for name in ("TC", "UPCAST", "LOCAL")):
      raise RuntimeError("Unsupported tinygrad optimizer; cannot apply TC_MIN_GLOBALS")
    helpers.TC_MIN_GLOBALS = helpers.ContextVar("TC_MIN_GLOBALS", 0)
    _original_heuristic = heuristic.hand_coded_optimizations
    heuristic.hand_coded_optimizations = _hand_coded_optimizations
    # The flag affects both cache identity and the context sent to workers.
    codegen.to_program_config = (*codegen.to_program_config, helpers.TC_MIN_GLOBALS)
    codegen.to_program_context = (*codegen.to_program_context, helpers.TC_MIN_GLOBALS)
    realize.to_program_context = codegen.to_program_context
    realize._compile_kernel = _compile_kernel
    implementation = "sunnypilot-e837e36-backport"

  return {"implementation": implementation, "tc_min_globals": helpers.TC_MIN_GLOBALS.value,
          "heuristic_source_commit": UPSTREAM_OPTIMIZER_COMMIT}
