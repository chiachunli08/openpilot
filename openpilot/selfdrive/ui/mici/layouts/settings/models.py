from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.selfdrive.ui.mici.widgets.button import BigButton
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.widgets.scroller import NavScroller


ACTIVE_KEYS = {
  "qcom": "ModelManager_ActiveBundle",
  "usbgpu": "ModelManager_ActiveBundleUSBGPU",
}
SYNC_KEYS = {
  "qcom": "ModelManager_LastSyncTime",
  "usbgpu": "ModelManager_LastSyncTime_USBGPU",
}


def manager_state():
  try:
    if ui_state.sm.valid["modelManagerSP"]:
      return ui_state.sm["modelManagerSP"]
  except Exception:
    pass
  return None


def bundles_for(source: str):
  state = manager_state()
  if state is None:
    return []
  return list(state.availableBundlesUsbGpu if source == "usbgpu" else state.availableBundlesQcom)


class ModelSelectionLayoutMici(NavScroller):
  def __init__(self, source: str):
    super().__init__()
    params = Params()

    default = BigButton(tr("Default"), tr("Built-in model"), scroll=True)
    default.set_click_callback(lambda: self._select_default(params, source))
    self._scroller.add_widget(default)

    for bundle in bundles_for(source):
      button = BigButton(bundle.displayName, bundle.ref, scroll=True)
      button.set_click_callback(lambda ref=bundle.ref: self._select(params, ref))
      self._scroller.add_widget(button)

  @staticmethod
  def _select_default(params: Params, source: str):
    params.remove(ACTIVE_KEYS[source])
    gui_app.pop_widget()

  @staticmethod
  def _select(params: Params, ref: str):
    params.put("ModelManager_DownloadRef", ref)
    gui_app.pop_widget()


class ModelsLayoutMici(NavScroller):
  def __init__(self):
    super().__init__()
    self._params = Params()
    self._source = "usbgpu" if ui_state.usbgpu_present else "qcom"

    self._source_btn = BigButton(tr("Model hardware"), "")
    self._source_btn.set_click_callback(self._toggle_source)
    self._model_btn = BigButton(tr("Driving model"), "", scroll=True)
    self._model_btn.set_click_callback(self._select_model)
    self._download_btn = BigButton(tr("Cancel download"), "")
    self._download_btn.set_click_callback(lambda: self._params.remove("ModelManager_DownloadRef"))
    refresh_btn = BigButton(tr("Refresh catalog"), "")
    refresh_btn.set_click_callback(self._refresh)
    clear_btn = BigButton(tr("Clear model cache"), "")
    clear_btn.set_click_callback(lambda: self._params.put_bool("ModelManager_ClearCache", True))

    self._scroller.add_widgets([
      self._source_btn,
      self._model_btn,
      self._download_btn,
      refresh_btn,
      clear_btn,
    ])

  def _toggle_source(self):
    self._source = "qcom" if self._source == "usbgpu" else "usbgpu"

  def _select_model(self):
    gui_app.push_widget(ModelSelectionLayoutMici(self._source))

  def _refresh(self):
    self._params.put(SYNC_KEYS[self._source], 0)

  def _active_name(self) -> str:
    state = manager_state()
    if state is None:
      return tr("Default")
    active = state.activeBundleUsbGpu if self._source == "usbgpu" else state.activeBundleQcom
    return active.displayName if active.ref else tr("Default")

  def _update_state(self):
    self._source_btn.set_value("eGPU" if self._source == "usbgpu" else "QCOM")
    self._model_btn.set_value(self._active_name())
    state = manager_state()
    downloading = state is not None and state.selectedBundle.ref and state.selectedSource == self._source
    if downloading:
      progress = max((model.artifact.downloadProgress.progress for model in state.selectedBundle.models), default=0.0)
      self._download_btn.set_value(tr("{progress:.0f}% complete").format(progress=progress))
    else:
      self._download_btn.set_value(tr("No active download"))
    self._download_btn.set_enabled(bool(downloading) and ui_state.is_offroad())
