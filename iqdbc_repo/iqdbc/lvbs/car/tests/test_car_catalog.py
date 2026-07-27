import json

from iqdbc.lvbs.car.car_catalog import build_car_catalog, CAR_LIST_JSON_OUT


class TestCarList:
  def test_generator(self):
    generated_car_list = json.dumps(build_car_catalog(), indent=2, ensure_ascii=False)
    with open(CAR_LIST_JSON_OUT) as f:
      current_car_list = f.read()

    assert generated_car_list == current_car_list, "Run iqdbc/lvbs/car/car_catalog.py to update the car list"
