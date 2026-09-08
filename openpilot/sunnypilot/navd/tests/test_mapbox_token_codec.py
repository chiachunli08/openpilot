import base64
import gzip
import unittest

from openpilot.sunnypilot.navd.mapbox_token_codec import decode_mapbox_public_token


class TestMapboxTokenCodec(unittest.TestCase):
  def test_original_token(self):
    self.assertEqual(decode_mapbox_public_token("pk.original"), "pk.original")

  def test_raw_compact_code(self):
    self.assertEqual(decode_mapbox_public_token("M0original"), "pk.original")

  def test_gzip_compact_code(self):
    token = "pk." + "repeated-token-data" * 10
    encoded = base64.urlsafe_b64encode(gzip.compress(token.encode())).decode().rstrip("=")
    self.assertEqual(decode_mapbox_public_token(f"M1{encoded}"), token)

  def test_rejects_secret_token(self):
    with self.assertRaises(ValueError):
      decode_mapbox_public_token("sk.secret")


if __name__ == "__main__":
  unittest.main()
