"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from openpilot.common.params import Params
from opendbc.car.hyundai.values import HyundaiFlags
from openpilot.sunnypilot.selfdrive.car.hkg_cluster_display import (
  HKG_CLUSTER_TEST_PARAM,
  HKG_CLUSTER_TEST_STATUS_PARAM,
  HKG_CLUSTER_PERMISSION_PARAM,
  is_ev6_hda2_cluster_candidate,
  verified_features_for_car,
)
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.multilang import tr, tr_noop
from openpilot.system.ui.sunnypilot.widgets.list_view import toggle_item_sp, multiple_button_item_sp
from openpilot.system.ui.widgets.scroller_tici import Scroller
from openpilot.system.ui.widgets import Widget

CHEVRON_INFO_DESCRIPTION = {
  "enabled": tr_noop("Display useful metrics below the chevron that tracks the lead car " +
                     "only applicable to cars with sunnypilot longitudinal control."),
  "disabled": tr_noop("This feature requires sunnypilot longitudinal control to be available.")
}


class VisualsLayout(Widget):
  def __init__(self):
    super().__init__()

    self._params = Params()
    items = self._initialize_items()
    self._scroller = Scroller(items, line_separator=True, spacing=0)

  def _initialize_items(self):
    self._toggle_defs = {
      "AdjacentLaneObjectMarkers": (
        lambda: tr("Adjacent Lane Object Markers"),
        tr("Show yellow markers for high-confidence model lead candidates outside the current driving path. " +
           "The driving model does not provide a complete object list, so some nearby vehicles may not appear."),
        None,
      ),
      "BlindSpot": (
        lambda: tr("Show Blind Spot Warnings"),
        tr("Enabling this will display warnings when a vehicle is detected in your " +
           "blind spot as long as your car has BSM supported."),
        None,
      ),
      "HkgCornerRadarDetection": (
        lambda: tr("HKG Corner Radar Detection (Experimental)"),
        tr("Passively display candidate 64-byte corner-radar targets. Source bus, mounting, status, and speed fields " +
           "require vehicle validation. Display and logging only; no control decisions."),
        None,
      ),
      HKG_CLUSTER_PERMISSION_PARAM: (
        lambda: tr("Kia EV6 Stock Cluster Extensions (Research)"),
        tr("Master permission for verified stock-cluster extensions. Each icon also requires an exact compatible vehicle " +
           "profile and fresh valid data. A separate local, parked-only test can send restricted 0x161 pages."),
        self._on_hkg_cluster_permission,
      ),
      HKG_CLUSTER_TEST_PARAM: (
        lambda: tr("Test EV6 Arrows, Lanes and Navigation (Park Only)"),
        tr("One-shot research test for lane-change arrows, lane colors, navigation icons. " +
           "Requires this master permission, exact EV6 HDA2 detection, Park, standstill, no accelerator, and disengaged control. " +
           "The test stops on any interlock or original 0x161/0x162 conflict, turns itself off, and requires a restart to arm."),
        self._on_hkg_cluster_test,
      ),
      "TorqueBar": (
        lambda: tr("Steering Arc"),
        tr("Display steering arc on the driving screen when lateral control is enabled."),
        None,
      ),
      "RainbowMode": (
        lambda: tr("Enable Tesla Rainbow Mode"),
        tr("Choose the original rainbow path or dynamic blue acceleration and deceleration bars below. Display only."),
        None,
      ),
      "StandstillTimer": (
        lambda: tr("Enable Standstill Timer"),
        tr("Show a timer on the HUD when the car is at a standstill."),
        None,
      ),
      "RoadNameToggle": (
        lambda: tr("Display Road Name"),
        tr("Displays the name of the road the car is traveling on." +
           "<br>The OpenStreetMap database of the location must be downloaded from " +
           "the OSM panel to fetch the road name."),
        None,
      ),
      "GreenLightAlert": (
        lambda: tr("Green Traffic Light Alert (Beta)"),
        tr("A chime and on-screen alert will play when the traffic light you are waiting for " +
           "turns green and you have no vehicle in front of you." +
           "<br>Note: This chime is only designed as a notification. " +
           "It is the driver's responsibility to observe their environment and make decisions accordingly."),
        None,
      ),
      "LeadDepartAlert": (
        lambda: tr("Lead Departure Alert (Beta)"),
        tr("A chime and on-screen alert will play when you are stopped, and the vehicle in front of you start moving." +
           "<br>Note: This chime is only designed as a notification. " +
           "It is the driver's responsibility to observe their environment and make decisions accordingly."),
        None,
      ),
      "TrueVEgoUI": (
        lambda: tr("Speedometer: Always Display True Speed"),
        tr("For applicable vehicles, always display the true vehicle current speed from wheel speed sensors."),
        None,
      ),
      "HideVEgoUI": (
        lambda: tr("Speedometer: Hide from Onroad Screen"),
        tr("When enabled, the speedometer on the onroad screen is not displayed."),
        None,
      ),
      "ShowTurnSignals": (
        lambda: tr("Display Turn Signals"),
        tr("When enabled, visual turn indicators are drawn on the HUD."),
        None,
      ),
      "RocketFuel": (
        lambda: tr("Real-time Acceleration Bar"),
        tr("Show an indicator on the left side of the screen to display real-time vehicle acceleration and deceleration. " +
           "This displays what the car is currently doing, not what the planner is requesting."),
        None,
      ),
    }
    self._toggles = {}
    for param, (title, desc, callback) in self._toggle_defs.items():
      toggle = toggle_item_sp(
        title=title,
        description=desc,
        param=param,
        initial_state=ui_state.params.get_bool(param),
        callback=callback,
      )
      self._toggles[param] = toggle

    self._chevron_info = multiple_button_item_sp(
      title=lambda: tr("Display Metrics Below Chevron"),
      description="",
      buttons=[lambda: tr("Off"), lambda: tr("Distance"), lambda: tr("Speed"), lambda: tr("Time"), lambda: tr("All")],
      param="ChevronInfo",
      inline=False
    )
    self._dev_ui_info = multiple_button_item_sp(
      title=lambda: tr("Developer UI"),
      description=lambda: tr("Display real-time parameters and metrics from various sources."),
      buttons=[lambda: tr("Off"), lambda: tr("Bottom"), lambda: tr("Right"), lambda: tr("Right & Bottom")],
      param="DevUIInfo",
      button_width=350,
      inline=False
    )

    self._rainbow_style = multiple_button_item_sp(
      title=lambda: tr("Tesla Rainbow Mode Style"),
      description=lambda: tr("Blue bars animate with actual vehicle acceleration and deceleration. " +
                             "A model-predicted stop is shown for any cause, including traffic lights or stop signs. " +
                             "The model does not identify light colors or sign types."),
      buttons=[lambda: tr("Rainbow Road"), lambda: tr("Dynamic Blue Bars")],
      param="RainbowModeStyle",
      button_width=450,
      inline=False,
    )
    items = list(self._toggles.values())
    items.insert(list(self._toggles).index("RainbowMode") + 1, self._rainbow_style)
    items += [
      self._chevron_info,
      self._dev_ui_info,
    ]
    return items

  def _on_hkg_cluster_permission(self, state: bool):
    if not state:
      self._params.put_bool(HKG_CLUSTER_TEST_PARAM, False)
      self._params.put(HKG_CLUSTER_TEST_STATUS_PARAM, "permission_disabled")

  def _on_hkg_cluster_test(self, state: bool):
    self._params.put(HKG_CLUSTER_TEST_STATUS_PARAM, "armed_restart_required" if state else "cancelled_by_user")

  def _update_state(self):
    super()._update_state()

    for param in self._toggle_defs:
      self._toggles[param].action_item.set_state(self._params.get_bool(param))

    hkg_canfd = (ui_state.CP is not None and ui_state.CP.brand == "hyundai" and
                 bool(ui_state.CP.flags & HyundaiFlags.CANFD))
    self._toggles["HkgCornerRadarDetection"].set_visible(hkg_canfd)

    hkg_cluster_candidate = is_ev6_hda2_cluster_candidate(ui_state.CP)
    hkg_cluster_toggle = self._toggles[HKG_CLUSTER_PERMISSION_PARAM]
    hkg_cluster_toggle.set_visible(hkg_cluster_candidate)
    hkg_test_toggle = self._toggles[HKG_CLUSTER_TEST_PARAM]
    hkg_test_toggle.set_visible(hkg_cluster_candidate)
    master_enabled = self._params.get_bool(HKG_CLUSTER_PERMISSION_PARAM)
    hkg_test_toggle.action_item.set_enabled(master_enabled)
    test_status = self._params.get(HKG_CLUSTER_TEST_STATUS_PARAM) or "idle"
    hkg_test_toggle.set_right_value(tr(str(test_status).replace("_", " ")))
    verified_count = len(verified_features_for_car(ui_state.CP))
    if hkg_cluster_candidate:
      hkg_cluster_toggle.set_right_value(tr("{} verified").format(verified_count))
      if verified_count:
        hkg_cluster_toggle.set_description(tr(
          "Master permission for verified stock-cluster extensions. Every icon is cleared independently when its source data is invalid or stale."
        ))
      else:
        hkg_cluster_toggle.set_description(tr(
          "Compatibility is unconfirmed, so normal dynamic cluster output remains disabled. " +
          "The separate local test sends only restricted pages while parked so each display can be filmed and verified."
        ))

    self._rainbow_style.action_item.set_selected_button(1 if self._params.get("RainbowModeStyle", return_default=True) == 1 else 0)
    self._rainbow_style.action_item.set_enabled(self._params.get_bool("RainbowMode"))

    self._dev_ui_info.action_item.set_selected_button(ui_state.params.get("DevUIInfo", return_default=True))

    if ui_state.has_longitudinal_control:
      self._chevron_info.set_description(tr(CHEVRON_INFO_DESCRIPTION["enabled"]))
      self._chevron_info.action_item.set_selected_button(ui_state.params.get("ChevronInfo", return_default=True))
      self._chevron_info.action_item.set_enabled(True)
    else:
      self._chevron_info.set_description(tr(CHEVRON_INFO_DESCRIPTION["disabled"]))
      self._chevron_info.action_item.set_enabled(False)
      ui_state.params.put("ChevronInfo", 0)

  def _render(self, rect):
    self._scroller.render(rect)

  def show_event(self):
    self._scroller.show_event()
    if not ui_state.has_longitudinal_control:
      self._chevron_info.set_description(tr(CHEVRON_INFO_DESCRIPTION["disabled"]))
      self._chevron_info.show_description(True)
