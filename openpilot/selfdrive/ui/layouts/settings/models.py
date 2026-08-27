from openpilot.cereal import custom
from openpilot.common.params import Params
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.widgets import DialogResult, Widget
from openpilot.system.ui.widgets.list_view import button_item, multiple_button_item, text_item
from openpilot.system.ui.widgets.option_dialog import MultiOptionDialog
from openpilot.system.ui.widgets.scroller_tici import Scroller


ACTIVE_KEYS = {
  "qcom": "ModelManager_ActiveBundle",
  "usbgpu": "ModelManager_ActiveBundleUSBGPU",
}
SYNC_KEYS = {
  "qcom": "ModelManager_LastSyncTime",
  "usbgpu": "ModelManager_LastSyncTime_USBGPU",
}


class ModelsLayout(Widget):
  def __init__(self):
    super().__init__()
    self._params = Params()
    self._source = "usbgpu" if ui_state.usbgpu_present else "qcom"
    self._dialog: MultiOptionDialog | None = None
    self._dialog_bundles = {}

    self._source_item = multiple_button_item(
      lambda: tr("Model hardware"),
      lambda: tr("QCOM and eGPU keep separate model selections."),
      ["QCOM", "eGPU"],
      1 if self._source == "usbgpu" else 0,
      callback=self._set_source,
      button_width=220,
    )
    self._active_item = button_item(lambda: tr("Driving model"), lambda: tr("SELECT"), callback=self._select_model,
                                    enabled=ui_state.is_offroad)
    self._status_item = text_item(lambda: tr("Download status"), "")
    self._cancel_item = button_item(lambda: tr("Model download"), lambda: tr("CANCEL"), callback=self._cancel_download,
                                    enabled=ui_state.is_offroad)
    self._refresh_item = button_item(lambda: tr("Model catalog"), lambda: tr("REFRESH"), callback=self._refresh,
                                     enabled=ui_state.is_offroad)
    self._clear_item = button_item(lambda: tr("Model cache"), lambda: tr("CLEAR"), callback=self._clear_cache,
                                   enabled=ui_state.is_offroad)

    self._scroller = Scroller([
      self._source_item,
      self._active_item,
      self._status_item,
      self._cancel_item,
      self._refresh_item,
      self._clear_item,
    ], line_separator=True, spacing=0)

  def _manager_state(self):
    try:
      if ui_state.sm.valid["modelManagerSP"]:
        return ui_state.sm["modelManagerSP"]
    except Exception:
      pass
    return None

  def _bundles(self):
    state = self._manager_state()
    if state is None:
      return []
    return list(state.availableBundlesUsbGpu if self._source == "usbgpu" else state.availableBundlesQcom)

  def _active_bundle(self):
    state = self._manager_state()
    if state is None:
      return None
    bundle = state.activeBundleUsbGpu if self._source == "usbgpu" else state.activeBundleQcom
    return bundle if bundle.ref else None

  def _set_source(self, index: int):
    self._source = "usbgpu" if index == 1 else "qcom"

  def _select_model(self):
    bundles = self._bundles()
    options = [tr("Default")]
    self._dialog_bundles = {}
    for bundle in bundles:
      label = bundle.displayName
      if label in self._dialog_bundles:
        label = f"{label} ({bundle.ref})"
      self._dialog_bundles[label] = bundle.ref
      options.append(label)

    active = self._active_bundle()
    current = active.displayName if active is not None else tr("Default")
    if active is not None and current not in self._dialog_bundles:
      current = next((label for label, ref in self._dialog_bundles.items() if ref == active.ref), tr("Default"))

    def handle_selection(result: DialogResult):
      if result == DialogResult.CONFIRM and self._dialog is not None:
        selection = self._dialog.selection
        if selection == tr("Default"):
          self._params.remove(ACTIVE_KEYS[self._source])
        elif ref := self._dialog_bundles.get(selection):
          self._params.put("ModelManager_DownloadRef", ref)
      self._dialog = None
      self._dialog_bundles = {}

    self._dialog = MultiOptionDialog(tr("Select a driving model"), options, current, callback=handle_selection)
    gui_app.push_widget(self._dialog)

  def _download_status(self) -> tuple[str, bool]:
    state = self._manager_state()
    if state is None or not state.selectedBundle.ref or state.selectedSource != self._source:
      return tr("Ready"), False
    progress = max((model.artifact.downloadProgress.progress for model in state.selectedBundle.models), default=0.0)
    eta = max((model.artifact.downloadProgress.eta for model in state.selectedBundle.models), default=0)
    if state.selectedBundle.status == custom.ModelManagerSP.DownloadStatus.failed:
      return tr("Download failed"), False
    return tr("Downloading {progress:.0f}% · {eta}s remaining").format(progress=progress, eta=eta), True

  def _cancel_download(self):
    self._params.remove("ModelManager_DownloadRef")

  def _refresh(self):
    self._params.put(SYNC_KEYS[self._source], 0)

  def _clear_cache(self):
    self._params.put_bool("ModelManager_ClearCache", True)

  def _update_state(self):
    active = self._active_bundle()
    self._active_item.action_item.set_value(active.displayName if active is not None else tr("Default"))
    status, downloading = self._download_status()
    self._status_item.action_item.set_text(status)
    self._cancel_item.set_visible(downloading)

  def show_event(self):
    super().show_event()
    self._scroller.show_event()

  def _render(self, rect):
    self._scroller.render(rect)
