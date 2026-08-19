from opendbc.car.volkswagen.values import VolkswagenFlags


def supports_battery_details(car_params) -> bool:
  return (car_params is not None and car_params.brand == "volkswagen" and
          bool(car_params.flags & VolkswagenFlags.MEB))
