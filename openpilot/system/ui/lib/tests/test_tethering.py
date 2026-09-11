from openpilot.system.ui.lib.wifi_manager import WifiManager


class InlineThread:
  def __init__(self, target, daemon=False):
    self.target = target

  def start(self):
    self.target()


def test_enable_tethering_uses_networkmanager_shared_mode(mocker):
  wm = WifiManager.__new__(WifiManager)
  wm._tethering_ssid = "weedle-test"
  activate_connection = mocker.patch.object(wm, "activate_connection")
  mocker.patch("openpilot.system.ui.lib.wifi_manager.threading.Thread", InlineThread)

  wm.set_tethering_active(True)

  activate_connection.assert_called_once_with("weedle-test", block=True)


def test_disable_tethering_deactivates_hotspot(mocker):
  wm = WifiManager.__new__(WifiManager)
  wm._tethering_ssid = "weedle-test"
  deactivate_connection = mocker.patch.object(wm, "_deactivate_connection")
  mocker.patch("openpilot.system.ui.lib.wifi_manager.threading.Thread", InlineThread)

  wm.set_tethering_active(False)

  deactivate_connection.assert_called_once_with("weedle-test")
