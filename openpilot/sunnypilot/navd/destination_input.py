def parse_coordinate_destination(value: str) -> tuple[float, float] | None:
  """Return latitude/longitude for a numeric pair, or None for an address query."""
  normalized = value.strip().replace("，", ",")
  parts = [part.strip() for part in normalized.split(",")]
  if len(parts) != 2:
    return None
  try:
    latitude, longitude = (float(part) for part in parts)
  except ValueError:
    return None
  if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
    raise ValueError("Coordinates are outside the valid range")
  if latitude == 0 and longitude == 0:
    raise ValueError("0, 0 is reserved for cancelling navigation")
  return latitude, longitude
