import unittest

from openpilot.sunnypilot.navd.destination_input import parse_coordinate_destination


class TestDestinationInput(unittest.TestCase):
  def test_coordinates(self):
    self.assertEqual(parse_coordinate_destination("25.0330, 121.5654"), (25.033, 121.5654))

  def test_full_width_comma(self):
    self.assertEqual(parse_coordinate_destination("25.0330，121.5654"), (25.033, 121.5654))

  def test_address(self):
    self.assertIsNone(parse_coordinate_destination("Taipei 101"))

  def test_address_with_comma(self):
    self.assertIsNone(parse_coordinate_destination("Taipei, Taiwan"))

  def test_invalid_coordinates(self):
    with self.assertRaises(ValueError):
      parse_coordinate_destination("91, 181")

  def test_cancel_coordinates(self):
    with self.assertRaises(ValueError):
      parse_coordinate_destination("0, 0")


if __name__ == "__main__":
  unittest.main()
