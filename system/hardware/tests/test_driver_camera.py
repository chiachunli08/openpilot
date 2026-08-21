from openpilot.system.hardware import driver_camera_available


def test_no_driver_camera_environment(monkeypatch):
  monkeypatch.setenv("NO_DRIVER_CAMERA", "1")
  assert not driver_camera_available()


def test_driver_camera_environment_enabled(monkeypatch):
  monkeypatch.setenv("NO_DRIVER_CAMERA", "0")
  monkeypatch.setattr("openpilot.system.hardware.os.path.exists", lambda path: False)
  assert driver_camera_available()
