import base64
import gzip
import unittest

from openpilot.sunnypilot.navd.mapbox_token_codec import MAPBOX_QR_PREFIX, decode_mapbox_public_token, decode_mapbox_qr_payload
from openpilot.sunnypilot.navd.mapbox_token_codec import decode_mapbox_secret_token, decode_mapbox_token


class TestMapboxTokenCodec(unittest.TestCase):
  def test_original_token(self):
    self.assertEqual(decode_mapbox_public_token("pk.original"), "pk.original")

  def test_raw_compact_code(self):
    self.assertEqual(decode_mapbox_public_token("M0original"), "pk.original")

  def test_gzip_compact_code(self):
    token = "pk." + "repeated-token-data" * 10
    encoded = base64.urlsafe_b64encode(gzip.compress(token.encode())).decode().rstrip("=")
    self.assertEqual(decode_mapbox_public_token(f"M1{encoded}"), token)

  def test_secret_raw_compact_code(self):
    self.assertEqual(decode_mapbox_secret_token("S0secret"), "sk.secret")

  def test_secret_gzip_compact_code(self):
    token = "sk." + "repeated-secret-data" * 10
    encoded = base64.urlsafe_b64encode(gzip.compress(token.encode())).decode().rstrip("=")
    self.assertEqual(decode_mapbox_token(f"S1{encoded}"), token)

  def test_rejects_wrong_token_type(self):
    with self.assertRaises(ValueError):
      decode_mapbox_secret_token("M0public")

  def test_rejects_secret_token(self):
    with self.assertRaises(ValueError):
      decode_mapbox_public_token("sk.secret")

  def test_public_qr_payload(self):
    self.assertEqual(decode_mapbox_qr_payload(f"{MAPBOX_QR_PREFIX}M0public"),
                     ("MapboxPublicKey", "pk.public"))

  def test_secret_qr_payload(self):
    self.assertEqual(decode_mapbox_qr_payload(f"{MAPBOX_QR_PREFIX}S0secret"),
                     ("MapboxSecretKey", "sk.secret"))

  def test_rejects_unscoped_qr_payload(self):
    with self.assertRaises(ValueError):
      decode_mapbox_qr_payload("M0public")

  def test_rejects_raw_token_in_qr_payload(self):
    with self.assertRaises(ValueError):
      decode_mapbox_qr_payload(f"{MAPBOX_QR_PREFIX}pk.public")


if __name__ == "__main__":
  unittest.main()
