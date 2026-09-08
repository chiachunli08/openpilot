import base64
import gzip


RAW_PREFIX = "M0"
GZIP_PREFIX = "M1"


def decode_mapbox_public_token(value: str) -> str:
  """Decode an M0/M1 compact code, or pass through an original pk. token."""
  token = value.strip()
  if token.startswith("pk."):
    return token
  if token.startswith(RAW_PREFIX):
    token = f"pk.{token[len(RAW_PREFIX):]}"
  elif token.startswith(GZIP_PREFIX):
    payload = token[len(GZIP_PREFIX):]
    padding = "=" * (-len(payload) % 4)
    try:
      token = gzip.decompress(base64.urlsafe_b64decode(payload + padding)).decode()
    except (ValueError, OSError, UnicodeDecodeError) as exc:
      raise ValueError("Invalid compressed Mapbox token") from exc
  else:
    raise ValueError("Mapbox token must start with pk., M0, or M1")

  if not token.startswith("pk."):
    raise ValueError("Decoded value is not a Mapbox public token")
  return token
