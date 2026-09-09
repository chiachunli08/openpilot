"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import datetime
import os
import platform
import requests
import threading
from concurrent.futures import Future
from pathlib import Path
from time import monotonic

from openpilot.common.params import Params
from openpilot.sunnypilot.navd.mapbox_token_codec import decode_mapbox_public_token, decode_mapbox_secret_token
from openpilot.sunnypilot.navd.destination_input import parse_coordinate_destination
from openpilot.sunnypilot.navd.qr_decoder import install_decoder, VERSION
from openpilot.selfdrive.ui.ui_state import device, ui_state
from openpilot.selfdrive.ui.layouts.settings.software import time_ago
from openpilot.common.hardware.hw import Paths
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.widgets import DialogResult, Widget
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog, alert_dialog
from openpilot.system.ui.widgets.list_view import text_item
from openpilot.system.ui.widgets.scroller_tici import Scroller

from openpilot.system.ui.sunnypilot.lib.utils import NoElideButtonAction
from openpilot.system.ui.sunnypilot.widgets.list_view import ListItemSP
from openpilot.system.ui.sunnypilot.widgets.tree_dialog import TreeFolder, TreeNode, TreeOptionDialog
from openpilot.system.ui.sunnypilot.widgets.progress_bar import progress_item
from openpilot.system.ui.sunnypilot.widgets.input_dialog import InputDialogSP
from openpilot.system.ui.sunnypilot.widgets.list_view import button_item_sp, toggle_item_sp
from openpilot.selfdrive.ui.sunnypilot.widgets.mapbox_qr_scanner import MapboxQrScannerDialog

MAP_PATH = Path(Paths.mapd_root()) / "offline"


class OSMLayout(Widget):
  def __init__(self):
    super().__init__()
    self._current_percent = 0
    self._last_map_size_update = 0
    self._decoder_job = None
    self._destination_job = None
    self._decoder_status = (tr("Installed: %s") % VERSION if (Path(Paths.qr_decoder_root()) / "current").exists()
                            else tr("Not downloaded"))
    self._mem_params = Params("/dev/shm/params") if platform.system() != "Darwin" else ui_state.params
    self._initialize_items()
    self._update_map_size()
    self._progress.set_visible(False)
    self._state_btn.set_visible(False)
    self._mapd_version.action_item.set_text(ui_state.params.get("MapdVersion") or "Loading...")
    self._scroller = Scroller(self.items, line_separator=True, spacing=0)

  def _initialize_items(self):
    self._navigation_toggle = toggle_item_sp(
      tr("Navigation"),
      tr("Use Mapbox routing and show the next maneuver. A network connection is required to load or recalculate a route; " +
         "an already loaded route remains available if the connection drops."),
      initial_state=ui_state.params.get_bool("NavigationEnabled"), param="NavigationEnabled")
    self._navigation_intent_toggle = toggle_item_sp(
      tr("Navigation Intent for Driving Model"),
      tr("Convert an approaching left or right navigation maneuver into the model's existing turn desire. This does not operate the vehicle turn signals; " +
         "the driver remains responsible for signaling and supervising the maneuver."),
      initial_state=ui_state.params.get_bool("NavigationIntentEnabled"), param="NavigationIntentEnabled")
    self._mapbox_public_key = button_item_sp(
      tr("Mapbox Public Token"), lambda: tr("EDIT"),
      description=tr("Public access token used for Directions requests."),
      callback=lambda: self._edit_mapbox_key("MapboxPublicKey", tr("Mapbox Public Token"), False))
    self._mapbox_secret_key = button_item_sp(
      tr("Mapbox Secret Token"), lambda: tr("EDIT"),
      description=tr("Optional secret token. It is stored locally and excluded from logs."),
      callback=lambda: self._edit_mapbox_key("MapboxSecretKey", tr("Mapbox Secret Token"), True))
    self._mapbox_qr_scanner = button_item_sp(
      tr("Scan Mapbox Token QR"), lambda: tr("SCAN"),
      description=tr("Scan a QR code from the token webpage with the driver monitoring camera. Available only while parked."),
      callback=self._show_mapbox_qr_scanner)
    self._decoder_download = button_item_sp(
      tr("QR Decoder"), lambda: tr("DOWNLOAD / REPAIR"),
      description=tr("Download open-source ZXing-C++ over Wi-Fi or cellular. Stored independently of software updates. " +
                     "QR images and tokens stay on this device."),
      callback=self._download_decoder)
    self._decoder_info = text_item(tr("QR Decoder Status"), lambda: self._decoder_status)
    self._navigation_destination = button_item_sp(
      tr("Navigation Destination"), lambda: tr("SET"),
      description=tr("Enter latitude, longitude or an English address. Use sunnylink for Chinese address input."),
      callback=self._edit_navigation_destination)
    self._cancel_navigation = button_item_sp(
      tr("Cancel Navigation"), lambda: tr("CANCEL"),
      description=tr("Clear the active destination and route."),
      callback=self._cancel_active_navigation)
    self._mapd_version = text_item(tr("Mapd Version"), lambda: ui_state.params.get("MapdVersion") or "Loading...")
    self._delete_maps_btn = ListItemSP(tr("Downloaded Maps"), action_item=NoElideButtonAction(tr("DELETE"), enabled=True), callback=self._delete_maps)
    self._progress = progress_item(tr("Downloading Map"))
    self._update_btn = ListItemSP(tr("Database Update"), action_item=NoElideButtonAction(tr("CHECK"), enabled=True), callback=self._update_db)
    self._country_btn = ListItemSP(tr("Country"), action_item=NoElideButtonAction(tr("SELECT"), enabled=True), callback=lambda: self._select_region("Country"))
    self._state_btn = ListItemSP(tr("State"), action_item=NoElideButtonAction(tr("SELECT"), enabled=True), callback=lambda: self._select_region("State"))

    self.items = [self._navigation_toggle, self._navigation_intent_toggle,
                  self._mapbox_public_key, self._mapbox_secret_key, self._decoder_download, self._decoder_info, self._mapbox_qr_scanner,
                  self._navigation_destination, self._cancel_navigation,
                  self._mapd_version, self._delete_maps_btn, self._progress,
                  self._update_btn, self._country_btn, self._state_btn]

  @staticmethod
  def _edit_mapbox_key(param: str, title: str, password_mode: bool) -> None:
    def save_key(result: DialogResult, text: str) -> None:
      if result != DialogResult.CONFIRM:
        return
      try:
        value = decode_mapbox_public_token(text) if param == "MapboxPublicKey" else decode_mapbox_secret_token(text)
        ui_state.params.put(param, value)
      except ValueError:
        expected = tr("pk. or M0/M1") if param == "MapboxPublicKey" else tr("sk. or S0/S1")
        gui_app.push_widget(alert_dialog(tr("Enter a valid Mapbox token or compact code: %s") % expected))

    subtitle = (tr("Accepts pk. tokens and reversible M0/M1 compact codes.") if param == "MapboxPublicKey"
                else tr("Accepts sk. tokens and reversible S0/S1 compact codes."))
    InputDialogSP(title, sub_title=subtitle, current_text=ui_state.params.get(param) or "",
                  callback=save_key, min_text_size=0, password_mode=password_mode).show()

  @staticmethod
  def _show_mapbox_qr_scanner() -> None:
    if ui_state.is_onroad():
      gui_app.push_widget(alert_dialog(tr("QR scanning is available only while parked.")))
      return
    gui_app.push_widget(MapboxQrScannerDialog())

  def _download_decoder(self):
    if ui_state.is_onroad() or self._decoder_job is not None:
      return
    self._decoder_job = job = Future()
    self._decoder_status = tr("Downloading and verifying...")
    self._decoder_download.action_item.set_enabled(False)
    self._mapbox_qr_scanner.action_item.set_enabled(False)

    def download():
      try:
        job.set_result(install_decoder(Paths.qr_decoder_root(), cancelled=ui_state.is_onroad))
      except Exception as error:
        job.set_exception(error)

    threading.Thread(target=download, daemon=True).start()

  def _show_confirm(self, msg, confirm_text, func):
    gui_app.push_widget(ConfirmDialog(msg, confirm_text, callback=lambda res: func() if res == DialogResult.CONFIRM else None))

  def _edit_navigation_destination(self) -> None:
    def resolve(result: DialogResult, text: str) -> None:
      if result != DialogResult.CONFIRM or not text.strip() or self._destination_job is not None:
        return
      self._navigation_destination.action_item.set_enabled(False)
      self._navigation_destination.action_item.set_text(tr("SEARCHING..."))
      self._destination_job = job = Future()

      def search():
        try:
          job.set_result(self._resolve_navigation_destination(text.strip()))
        except Exception as error:
          job.set_exception(error)

      threading.Thread(target=search, daemon=True).start()

    InputDialogSP(tr("Navigation Destination"),
                  sub_title=tr("Latitude, longitude or English address"),
                  callback=resolve, min_text_size=1).show()

  def _resolve_navigation_destination(self, query: str) -> dict:
    try:
      coordinates = parse_coordinate_destination(query)
      if coordinates is not None:
        latitude, longitude = coordinates
        name, details = tr("Coordinate destination"), f"{latitude}, {longitude}"
      else:
        raw_token = ui_state.params.get("MapboxPublicKey") or ui_state.params.get("MapboxSecretKey") or ""
        token = (decode_mapbox_public_token(raw_token) if raw_token.startswith(("pk.", "M"))
                 else decode_mapbox_secret_token(raw_token))
        response = requests.get("https://api.mapbox.com/search/geocode/v6/forward",
                                params={"q": query, "access_token": token, "limit": 1,
                                        "language": ui_state.params.get("LanguageSetting") or "en"}, timeout=10)
        response.raise_for_status()
        features = response.json().get("features", [])
        if not features:
          raise ValueError("Destination not found")
        feature = features[0]
        longitude, latitude = feature["geometry"]["coordinates"][:2]
        properties = feature.get("properties", {})
        name = properties.get("name") or properties.get("full_address") or query
        details = properties.get("full_address") or properties.get("place_formatted") or query

      destination = {"latitude": float(latitude), "longitude": float(longitude),
                     "place_name": name, "place_details": details}
      return destination
    except (KeyError, IndexError, TypeError, ValueError, requests.RequestException) as error:
      raise ValueError("Unable to resolve destination") from error

  def _finish_navigation_destination(self):
    if self._destination_job is None or not self._destination_job.done():
      return
    job, self._destination_job = self._destination_job, None
    try:
      destination = job.result()
      if not ui_state.is_onroad():
        message = tr("Start navigation to %s?\n\n%s") % (destination["place_name"], destination["place_details"])
        gui_app.push_widget(ConfirmDialog(message, tr("Navigate"), callback=lambda result:
                            self._save_navigation_destination(result, destination)))
    except Exception:
      if not ui_state.is_onroad():
        gui_app.push_widget(alert_dialog(tr("Unable to resolve the destination. Check the token, network, address, or coordinates.")))
    finally:
      self._navigation_destination.action_item.set_enabled(True)
      self._navigation_destination.action_item.set_text(tr("SET"))

  @staticmethod
  def _save_navigation_destination(result, destination):
    if result != DialogResult.CONFIRM:
      return
    try:
      # Params serializes JSON keys itself; passing a JSON string raises TypeError.
      ui_state.params.put("NavDestination", destination, block=True)
    except (OSError, RuntimeError, TypeError, ValueError):
      gui_app.push_widget(alert_dialog(tr("Unable to save the destination. Please try again.")))

  @staticmethod
  def _cancel_active_navigation() -> None:
    ui_state.params.remove("NavDestination")

  def calculate_size(self):
    total_size = 0
    directories_to_scan = [MAP_PATH] if MAP_PATH.exists() else []
    while directories_to_scan:
      try:
        for entry in os.scandir(directories_to_scan.pop()):
          if entry.is_file():
            total_size += entry.stat().st_size
          elif entry.is_dir():
            directories_to_scan.append(entry.path)
      except OSError:
        pass
    self._delete_maps_btn.action_item.set_value(f"{total_size / 1024 ** 2:.2f} MB" if total_size < 1024 ** 3 else f"{total_size / 1024 ** 3:.2f} GB")

  def _update_map_size(self):
    threading.Thread(target=self.calculate_size, daemon=True).start()

  def _on_confirm_delete_maps(self):
    ui_state.params.put_bool("Mapd_ClearCache", True)
    self._delete_maps_btn.action_item.set_enabled(True)
    self._delete_maps_btn.action_item.set_text(tr("DELETE"))
    self._update_map_size()

  def _delete_maps(self):
    self._show_confirm(tr("This will delete ALL downloaded maps\n\nAre you sure you want to delete all maps?"),
                       tr("Yes, delete all maps"), self._on_confirm_delete_maps)

  def _update_db(self):
    self._show_confirm(tr("This will start the download process and it might take a while to complete."), tr("Start Download"),
                       lambda: ui_state.params.put_bool("OsmDbUpdatesCheck", True))

  def _select_region(self, region_type):
    is_country = region_type == "Country"
    btn = self._country_btn if is_country else self._state_btn
    btn.action_item.set_enabled(False)
    btn.action_item.set_text(tr("FETCHING..."))
    threading.Thread(target=self._do_select_region, args=(region_type, btn)).start()

  def _handle_region_selection(self, region_type, locations, key, res, ref):
    if res != DialogResult.CONFIRM or not ref:
      if region_type == "State" and res == DialogResult.CANCEL:
        if ui_state.params.get("OsmLocationName") == "US" and not ui_state.params.get("OsmStateName"):
          ui_state.params.remove("OsmLocationName")
          ui_state.params.remove("OsmLocationTitle")
          ui_state.params.remove("OsmLocal")
          self._update_labels()
      return

    if region_type == "Country":
      ui_state.params.put_bool("OsmLocal", True)
      ui_state.params.remove("OsmStateName")
      ui_state.params.remove("OsmStateTitle")

    ui_state.params.put(f"{key}Name", ref)
    name = next((n.data['display_name'] for n in locations if n.ref == ref), ref)
    ui_state.params.put(f"{key}Title", name)

    if ref == "US" and region_type == "Country":
      self._select_region("State")
    else:
      self._update_db()

  def _do_select_region(self, region_type, btn):
    base_url = "https://raw.githubusercontent.com/pfeiferj/openpilot-mapd/main/"
    url = base_url + ("nation_bounding_boxes.json" if region_type == "Country" else "us_states_bounding_boxes.json")
    try:
      data = requests.get(url, timeout=10).json()
      locations = sorted([TreeNode(ref=k, data={'display_name': v['full_name']}) for k, v in data.items()], key=lambda n: n.data['display_name'])
    except Exception:
      locations = []

    if region_type == "State":
      locations.insert(0, TreeNode(ref="All", data={'display_name': tr("All states (~6.0 GB)")}))

    btn.action_item.set_enabled(True)
    btn.action_item.set_text(tr("SELECT"))

    key = "OsmLocation" if region_type == "Country" else "OsmState"
    current = ui_state.params.get(f"{key}Name") or ""

    dialog = TreeOptionDialog(tr(f"Select {region_type}"), [TreeFolder(folder="", nodes=locations)], current_ref=current, search_prompt="Perform a search")
    dialog.on_exit = lambda res: self._handle_region_selection(region_type, locations, key, res, dialog.selection_ref)
    gui_app.push_widget(dialog)

  def _update_labels(self):
    downloading = bool(self._mem_params.get("OSMDownloadLocations"))
    self._country_btn.set_enabled(not downloading)
    self._state_btn.set_enabled(not downloading)
    self._state_btn.set_visible(ui_state.params.get("OsmLocationName") == "US")
    self._update_btn.set_visible(bool(ui_state.params.get("OsmLocationName")))

    self._country_btn.action_item.set_value(ui_state.params.get("OsmLocationTitle") or "")
    self._state_btn.action_item.set_value(ui_state.params.get("OsmStateTitle") or "")

    pending = ui_state.params.get_bool("OsmDbUpdatesCheck")
    if downloading or pending:
      if downloading:
        device._reset_interactive_timeout()
        self._update_map_size()
      self._progress.set_visible(True)
      progress = ui_state.params.get("OSMDownloadProgress")
      total = progress.get('total_files', 0) if progress else 0
      done = progress.get('downloaded_files', 0) if progress else 0
      failed = total > 0 and not downloading and done < total

      if total > 0:
        progress_perc = max(0.0, min(100.0, (done / total) * 100.0))
      else:
        progress_perc = 0.0

      if failed:
        text = "0% - Downloading Maps"
        btn_text = tr("Error: Invalid download. Retry.")
        self._current_percent = 0.0
      elif total > 0 and downloading:
        self._current_percent = progress_perc
        perc_int = int(progress_perc)
        text = f"{perc_int}% - Downloading Maps"
        btn_text = f"{done}/{total} ({perc_int}%)"
      else:
        self._current_percent = 0.0
        text = "0% - Downloading Maps"
        btn_text = tr("Downloading Maps...")

      self._progress.action_item.update(self._current_percent, text, show_progress=total > 0 and downloading and not failed)
      self._update_btn.action_item.set_enabled(not downloading)  # TODO-SP: introduce CANCEL database download with mapd
      self._update_btn.action_item.set_value(btn_text)
      self._country_btn.action_item.set_enabled(not downloading)
      self._state_btn.action_item.set_enabled(not downloading)
      self._delete_maps_btn.action_item.set_enabled(not downloading)
    else:
      self._progress.set_visible(False)
      self._update_btn.action_item.set_enabled(True)
      self._country_btn.action_item.set_enabled(True)
      self._state_btn.action_item.set_enabled(True)
      self._delete_maps_btn.action_item.set_enabled(True)

      ts = ui_state.params.get("OsmDownloadedDate")
      dt: datetime.datetime | None = None

      if ts:
        try:
          ts_f = float(ts)
          if ts_f > 0:
            dt = datetime.datetime.fromtimestamp(ts_f, tz=datetime.UTC)
        except (ValueError, TypeError):
          dt = None

      formatted = time_ago(dt)
      self._update_btn.action_item.set_value(tr("Last checked {}").format(formatted))

  def show_event(self):
    self._scroller.show_event()

  def _update_state(self):
    self._finish_navigation_destination()
    if self._decoder_job is not None and self._decoder_job.done():
      try:
        self._decoder_status = tr("Installed: %s") % self._decoder_job.result()
      except Exception:
        self._decoder_status = tr("Installation failed or cancelled. Check network and retry while parked.")
      self._decoder_job = None
    busy = self._decoder_job is not None
    self._decoder_download.action_item.set_enabled(not busy and not ui_state.is_onroad())
    self._mapbox_qr_scanner.action_item.set_enabled(not busy and not ui_state.is_onroad())
    if busy:
      device._reset_interactive_timeout()
    now = monotonic()
    if now - self._last_map_size_update >= 1.0:
      self._last_map_size_update = now
      self._update_labels()

  def _render(self, rect):
    self._scroller.render(rect)
