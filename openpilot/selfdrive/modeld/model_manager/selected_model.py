from __future__ import annotations

import os
import numpy as np

from tinygrad.tensor import Tensor

from openpilot.cereal import log
from openpilot.common.file_chunker import open_file_chunked
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.controls.lib.drive_helpers import get_accel_from_plan, get_curvature_from_plan, smooth_value
from openpilot.selfdrive.modeld.helpers import get_tg_input_devices, load_oob
from openpilot.selfdrive.modeld.model_manager.compile_selected import (
  POLICY_INPUTS, WARP_INPUTS, derive_frame_skip, make_split_input_queues, make_supercombo_input_queues,
)
from openpilot.selfdrive.modeld.model_manager.constants import Plan
from openpilot.system.camerad.cameras.nv12_info import get_nv12_info
from openpilot.system.hardware.hw import Paths
from msgq.visionipc import VisionBuf

PROCESS_NAME = "openpilot.selfdrive.modeld.modeld"


def _pkl_exists(path: str) -> bool:
  from openpilot.common.file_chunker import get_manifest_path
  return os.path.exists(path) or os.path.exists(get_manifest_path(path))


def _find_driving_pkl(bundle) -> str | None:
  override = os.environ.get("COMBINED_MODEL_PKL")
  if override and _pkl_exists(override):
    return override
  if bundle is None or not bundle.models:
    return None
  path = os.path.join(Paths.model_root(), bundle.models[0].artifact.fileName)
  return path if _pkl_exists(path) else None


class SelectedModelState:
  inputs: dict[str, np.ndarray]
  prev_desire: np.ndarray

  def __init__(self, cam_w: int, cam_h: int, usbgpu: bool, bundle):
    self.lat_delay = 0.0

    env_pkl = os.environ.get('COMBINED_MODEL_PKL')
    if env_pkl and _pkl_exists(env_pkl):
      model_bundle = None
    else:
      model_bundle = bundle
    self.generation = model_bundle.generation if model_bundle is not None else None
    overrides = {override.key: override.value for override in model_bundle.overrides} if model_bundle else {}

    self.LAT_SMOOTH_SECONDS = float(overrides.get('lat', ".0"))
    self.LONG_SMOOTH_SECONDS = float(overrides.get('long', ".0"))
    self.MIN_LAT_CONTROL_SPEED = 0.3
    self.PLANPLUS_CONTROL: float = 1.0
    self.usbgpu = usbgpu
    self.selected_model = True

    pkl_path = _find_driving_pkl(model_bundle)
    assert pkl_path is not None, "No driving pkl found — all models must be compiled with compile_modeld.py"
    self._init_combined(pkl_path, cam_w, cam_h, model_bundle)

  def _init_combined(self, pkl_path, cam_w, cam_h, bundle):
    cloudlog.warning(f"loading combined pkl: {pkl_path}")
    jits = load_oob(open_file_chunked(pkl_path))

    input_devices = get_tg_input_devices(PROCESS_NAME, self.usbgpu)
    self.WARP_DEV = input_devices['WARP_DEV']
    self.QUEUE_DEV = input_devices['QUEUE_DEV']
    self.DEV = self.QUEUE_DEV
    metadata = jits['metadata']

    self.is_legacy_model = 'run_policy' not in jits  # remove after next recompile
    if self.is_legacy_model:
      self.warp = jits[(cam_w, cam_h)]['warp_enqueue']
      self.run_policy = jits[(cam_w, cam_h)]['run_policy']
    else:
      self.run_policy = jits['run_policy']
      self.warp = jits[(cam_w, cam_h)]

    if 'model' in metadata:
      model_metadata = metadata['model']
      meta_metadata = model_metadata
      self.vision_output_slices = model_metadata['output_slices']
      self.policy_output_slices = {}
      self._policy_slices_list = []
      self._combined_model_type = 'supercombo'
      self._vision_input_names = [key for key in model_metadata['input_shapes'] if 'img' in key]
      frame_skip = derive_frame_skip({}, model_metadata['input_shapes'])
      self.input_queues, self.numpy_inputs = make_supercombo_input_queues(model_metadata['input_shapes'],
                                                                          frame_skip, device=self.QUEUE_DEV)
    else:
      vision_metadata = metadata['vision']
      policy_keys = [k for k in metadata if k != 'vision']
      if policy_keys == ['policy']:
        self._combined_model_type = 'split'
      else:
        self._combined_model_type = 'multi_policy'
      self.vision_output_slices = vision_metadata['output_slices']
      self._policy_keys = policy_keys
      self._policy_slices_list = [metadata[k]['output_slices'] for k in policy_keys]
      self.policy_output_slices = self._policy_slices_list[0]
      self._has_on_policy = any('on' in k.lower() for k in policy_keys)
      self._vision_input_names = [key for key in vision_metadata['input_shapes'] if 'img' in key]
      first_policy_meta = metadata[policy_keys[0]]
      meta_metadata = first_policy_meta
      frame_skip = derive_frame_skip(vision_metadata['input_shapes'], first_policy_meta['input_shapes'])
      self.input_queues, self.numpy_inputs = make_split_input_queues(vision_metadata['input_shapes'],
                                                                     first_policy_meta['input_shapes'],
                                                                     frame_skip, device=self.QUEUE_DEV)

    self._desire_key = next(key for key in self.numpy_inputs if key.startswith('desire'))
    self._road_key = next(key for key in self._vision_input_names if 'big' not in key)
    self._wide_key = next(key for key in self._vision_input_names if 'big' in key)

    is_20hz = bundle.is20hz if bundle else self._combined_model_type in ('split', 'multi_policy')
    if is_20hz:
      from openpilot.selfdrive.modeld.model_manager.split_model_constants import SplitModelConstants
      self.constants = SplitModelConstants()
    else:
      from openpilot.selfdrive.modeld.model_manager.constants import ModelConstants
      self.constants = ModelConstants()
    from openpilot.selfdrive.modeld.model_manager.helpers import load_meta_constants
    self.meta_constants = load_meta_constants(meta_metadata)
    self.model_freq = self.constants.MODEL_FREQ

    if self._combined_model_type != 'supercombo':
      from openpilot.selfdrive.modeld.model_manager.parse_selected_split import Parser as SplitParser
      self.parser = SplitParser()
    else:
      from openpilot.selfdrive.modeld.model_manager.parse_selected import Parser as CombinedParser
      self.parser = CombinedParser()

    self.prev_desire = np.zeros(self.constants.DESIRE_LEN, dtype=np.float32)
    self.full_frames: dict = {}
    self._blob_cache: dict = {}
    nv12_info = get_nv12_info(cam_w, cam_h)
    self.frame_buf_params = dict.fromkeys(self._vision_input_names, nv12_info)

    yuv_size = self.frame_buf_params[self._road_key][3]
    frame_tensor = Tensor(np.zeros(yuv_size, dtype=np.uint8), device=self.WARP_DEV).contiguous().realize()
    big_frame_tensor = Tensor(np.zeros(yuv_size, dtype=np.uint8), device=self.WARP_DEV).contiguous().realize()

    if self.is_legacy_model: # Remove this conditional hack after recompile
      self.warp(**self.input_queues, frame=frame_tensor, big_frame=big_frame_tensor)
    else:
      self.warp(**{k: self.input_queues[k] for k in WARP_INPUTS}, frame=frame_tensor, big_frame=big_frame_tensor)

    if self.usbgpu:
      self.warmup()

  def warmup(self) -> None:
    dummy_frames = {k: np.zeros(self.frame_buf_params[k][3], dtype=np.uint8) for k in self._vision_input_names}
    transforms = {k: np.eye(3, dtype=np.float32) for k in [self._road_key, self._wide_key] if k}

    dummy_inputs = {}
    for k, v in self.numpy_inputs.items():
      if k not in ['tfm', 'big_tfm', 'prev_feat']:
        dummy_inputs[k] = np.zeros(v.shape, dtype=v.dtype)

    self.run(dummy_frames, transforms, dummy_inputs, prepare_only=False)

    for v in self.numpy_inputs.values():
      v[:] = 0
    self.prev_desire[:] = 0
    self.full_frames.clear()
    self._blob_cache.clear()


  @property
  def mlsim(self) -> bool:
    return bool(self.generation is not None and self.generation >= 11)

  @property
  def vision_input_names(self) -> list[str]:
    return self._vision_input_names

  @property
  def desire_key(self) -> str:
    return self._desire_key

  def run(self, bufs: dict[str, VisionBuf], transforms: dict[str, np.ndarray],
                inputs: dict[str, np.ndarray], prepare_only: bool) -> dict[str, np.ndarray] | None:
    for key in bufs.keys():
      ptr = np.frombuffer(bufs[key].data, dtype=np.uint8).ctypes.data
      yuv_size = self.frame_buf_params[key][3]
      cache_key = (key, ptr)
      if cache_key not in self._blob_cache:
        self._blob_cache[cache_key] = Tensor.from_blob(ptr, (yuv_size,), dtype='uint8', device=self.WARP_DEV)
      self.full_frames[key] = self._blob_cache[cache_key]

    desire_key = self.desire_key
    inputs[desire_key][0] = 0
    self.numpy_inputs[desire_key][:] = np.where(inputs[desire_key] - self.prev_desire > .99, inputs[desire_key], 0)
    self.prev_desire[:] = inputs[desire_key]
    for key in ('traffic_convention', 'lateral_control_params', 'action_t'):
      if key in self.numpy_inputs and key in inputs:
        self.numpy_inputs[key][:] = inputs[key]

    road_key = self._road_key
    wide_key = self._wide_key
    self.numpy_inputs['tfm'][:, :] = transforms[road_key].reshape(3, 3)
    self.numpy_inputs['big_tfm'][:, :] = transforms[wide_key].reshape(3, 3)

    if self.is_legacy_model:  # remove after next recompile
      if prepare_only:
        self.warp(**self.input_queues, frame=self.full_frames[road_key], big_frame=self.full_frames[wide_key])
        return None
      raw_outputs = self.run_policy(**self.input_queues, frame=self.full_frames[road_key], big_frame=self.full_frames[wide_key])
    else:
      if prepare_only:
        self.warp(**{k: self.input_queues[k] for k in WARP_INPUTS}, frame=self.full_frames[road_key], big_frame=self.full_frames[wide_key])
        return None
      warped = self.warp(**{k: self.input_queues[k] for k in WARP_INPUTS}, frame=self.full_frames[road_key], big_frame=self.full_frames[wide_key])
      raw_outputs = self.run_policy(**{k: self.input_queues[k] for k in POLICY_INPUTS if k in self.input_queues}, warped=warped)

    if self._combined_model_type == 'supercombo':
      model_output = raw_outputs.numpy().flatten()
      sliced = {k: model_output[np.newaxis, v] for k, v in self.vision_output_slices.items()}
      outputs = self.parser.parse_outputs(sliced)
      if 'prev_feat' in self.numpy_inputs:
        self.numpy_inputs['prev_feat'][:] = model_output[self.vision_output_slices['hidden_state']]
    else:
      vision_output = raw_outputs[0].numpy().flatten()
      vision_sliced = {k: vision_output[np.newaxis, v] for k, v in self.vision_output_slices.items()}
      outputs = self.parser.parse_vision_outputs(vision_sliced)

      if 'prev_feat' in self.numpy_inputs and 'hidden_state' in self.vision_output_slices:
        self.numpy_inputs['prev_feat'][:] = vision_output[self.vision_output_slices['hidden_state']]

      for i, policy_slices in enumerate(self._policy_slices_list):
        policy_output = raw_outputs[i + 1].numpy().flatten()
        policy_sliced = {k: policy_output[np.newaxis, v] for k, v in policy_slices.items()}
        parsed = self.parser.parse_policy_outputs(policy_sliced)
        if ('off' in self._policy_keys[i]
          and self._has_on_policy
          and any('plan' in self._policy_slices_list[j] for j, k in enumerate(self._policy_keys) if 'on' in k.lower())):

          parsed.pop('plan', None)

        outputs.update(parsed)

      if 'planplus' in outputs and 'plan' in outputs:
        outputs['plan'] = outputs['plan'] + outputs['planplus']

    if 'desired_curvature' in outputs and 'prev_desired_curv' in self.numpy_inputs:
      buf = self.numpy_inputs['prev_desired_curv']
      buf[0, :-1] = buf[0, 1:]
      buf[0, -1, :] = outputs['desired_curvature'][0, :] if not self.mlsim else 0

    if self.usbgpu and not np.all(np.isfinite(outputs.get('plan', np.array([0.])))):
      raise RuntimeError("eGPU model output is not finite")

    return outputs

  def _get_curvature(self, output, plan, v_ego, lat_action_t):
    if not self.mlsim and (desired := output.get("desired_curvature")) is not None:
      return float(desired[0, 0])
    return float(get_curvature_from_plan(plan[:, Plan.T_FROM_CURRENT_EULER][:, 2],
                                         plan[:, Plan.ORIENTATION_RATE][:, 2],
                                         self.constants.T_IDXS, v_ego, lat_action_t))

  def get_action_from_model(self, model_output: dict[str, np.ndarray], prev_action: log.ModelDataV2.Action,
                            lat_action_t: float, long_action_t: float, v_ego: float,
                            v_ego_stopping: float) -> log.ModelDataV2.Action:
    plan = model_output['plan'][0]
    planned_accel, should_stop, _, desired_velocity = get_accel_from_plan(
      plan[:, Plan.VELOCITY][:, 0], plan[:, Plan.ACCELERATION][:, 0], self.constants.T_IDXS,
      action_t=long_action_t, vEgoStopping=v_ego_stopping,
    )
    if 'action' not in model_output:
      desired_accel = planned_accel

      curvature_plan = (plan + (self.PLANPLUS_CONTROL - 1.0) * model_output['planplus'][0]
                        if 'planplus' in model_output and self.PLANPLUS_CONTROL != 1.0 else plan)
      desired_curvature = self._get_curvature(model_output, curvature_plan, v_ego, lat_action_t)
    else:
      desired_accel = model_output['action'][0, 1]
      desired_curvature = model_output['action'][0, 0] / (max(1.0, v_ego))**2

    desired_accel = smooth_value(desired_accel, prev_action.desiredAcceleration, self.LONG_SMOOTH_SECONDS)
    desired_velocity = smooth_value(desired_velocity, prev_action.desiredVelocity, self.LONG_SMOOTH_SECONDS)

    if self.generation is not None and self.generation >= 10: # smooth curvature for post FOF models
      if v_ego > self.MIN_LAT_CONTROL_SPEED:
        desired_curvature = smooth_value(desired_curvature, prev_action.desiredCurvature, self.LAT_SMOOTH_SECONDS)
      else:
        desired_curvature = prev_action.desiredCurvature

    return log.ModelDataV2.Action(desiredCurvature=float(desired_curvature), desiredAcceleration=float(desired_accel),
                                  shouldStop=bool(should_stop), desiredVelocity=float(desired_velocity))
