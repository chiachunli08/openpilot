import base64
import gzip


PUBLIC_RAW_PREFIX = "M0"
PUBLIC_GZIP_PREFIX = "M1"
SECRET_RAW_PREFIX = "S0"
SECRET_GZIP_PREFIX = "S1"
MAPBOX_QR_PREFIX = "sunnypilot-mapbox:v1:"


def decode_mapbox_token(value: str, expected_prefix: str | None = None) -> str:
  """Decode a public M0/M1 or secret S0/S1 code, or pass through a token."""
  token = value.strip()
  if token.startswith(("pk.", "sk.")):
    pass
  elif token.startswith((PUBLIC_RAW_PREFIX, SECRET_RAW_PREFIX)):
    prefix = "pk." if token.startswith(PUBLIC_RAW_PREFIX) else "sk."
    token = f"{prefix}{token[2:]}"
  elif token.startswith((PUBLIC_GZIP_PREFIX, SECRET_GZIP_PREFIX)):
    payload = token[2:]
    padding = "=" * (-len(payload) % 4)
    try:
      token = gzip.decompress(base64.urlsafe_b64decode(payload + padding)).decode()
    except (ValueError, OSError, UnicodeDecodeError) as exc:
      raise ValueError("Invalid compressed Mapbox token") from exc
  else:
    raise ValueError("Mapbox token must start with pk., sk., M0/M1, or S0/S1")

  if not token.startswith(("pk.", "sk.")):
    raise ValueError("Decoded value is not a Mapbox token")
  if expected_prefix is not None and not token.startswith(expected_prefix):
    raise ValueError(f"Expected a {expected_prefix} Mapbox token")
  return token


def decode_mapbox_public_token(value: str) -> str:
  return decode_mapbox_token(value, "pk.")


def decode_mapbox_secret_token(value: str) -> str:
  return decode_mapbox_token(value, "sk.")


def decode_mapbox_qr_payload(value: str) -> tuple[str, str]:
  """Return the destination Params key and decoded token from a scanner payload."""
  payload = value.strip()
  if not payload.startswith(MAPBOX_QR_PREFIX):
    raise ValueError("Not a sunnypilot Mapbox QR code")

  compact_token = payload.removeprefix(MAPBOX_QR_PREFIX)
  if not compact_token.startswith((PUBLIC_RAW_PREFIX, PUBLIC_GZIP_PREFIX,
                                   SECRET_RAW_PREFIX, SECRET_GZIP_PREFIX)):
    raise ValueError("Mapbox QR code must contain a compact token")

  token = decode_mapbox_token(compact_token)
  param = "MapboxPublicKey" if token.startswith("pk.") else "MapboxSecretKey"
  return param, token
