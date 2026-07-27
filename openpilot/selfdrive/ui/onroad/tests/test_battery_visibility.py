from types import SimpleNamespace

from opendbc.car.volkswagen.values import VolkswagenFlags
from openpilot.selfdrive.ui.onroad.battery_visibility import supports_battery_details


def _car_params(brand: str, flags: int):
  return SimpleNamespace(brand=brand, flags=flags)


def test_meb_battery_details_visible():
  assert supports_battery_details(_car_params("volkswagen", VolkswagenFlags.MEB))


def test_non_meb_battery_details_hidden():
  assert not supports_battery_details(_car_params("volkswagen", VolkswagenFlags.MQB_EVO))
  assert not supports_battery_details(_car_params("volkswagen", 0))
  assert not supports_battery_details(_car_params("other", VolkswagenFlags.MEB))
  assert not supports_battery_details(None)
