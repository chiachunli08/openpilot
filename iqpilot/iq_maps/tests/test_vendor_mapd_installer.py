import hashlib

import pytest

from openpilot.iqpilot.iq_maps import vendor_mapd_installer as vmi


class FakeParams:
  def __init__(self):
    self.store: dict[str, object] = {}

  def get(self, key, return_default=False):
    return self.store.get(key)

  def put(self, key, value):
    self.store[key] = value

  def remove(self, key):
    self.store.pop(key, None)


@pytest.fixture
def env(tmp_path, monkeypatch):
  binary = tmp_path / "mapd"
  hash_file = tmp_path / "mapd_hash"
  monkeypatch.setattr(vmi, "VENDOR_MAPD_PATH", str(binary))
  monkeypatch.setattr(vmi, "QUARANTINE_PATH", str(binary) + ".quarantined")
  monkeypatch.setattr(vmi, "_HASH_FILE", str(hash_file))
  monkeypatch.setattr(vmi.sentry, "init", lambda *a, **k: None)
  monkeypatch.setattr(vmi.sentry, "capture_exception", lambda *a, **k: None)
  return binary, hash_file


def test_verified_binary_stamps_version(env):
  binary, hash_file = env
  binary.write_bytes(b"vetted")
  hash_file.write_text(hashlib.sha256(b"vetted").hexdigest())

  params = FakeParams()
  assert vmi.VendorMapdInstaller(params=params).verify()
  assert params.store["MapdVersion"] == vmi.VENDOR_RELEASE_TAG
  assert binary.exists()


def test_foreign_binary_quarantined(env):
  # the fresh-install poison scenario: a stock release build on disk while the
  # pin points at the vetted build
  binary, hash_file = env
  binary.write_bytes(b"stock release build")
  hash_file.write_text(hashlib.sha256(b"vetted").hexdigest())

  params = FakeParams()
  params.store["MapdVersion"] = vmi.VENDOR_RELEASE_TAG
  assert not vmi.VendorMapdInstaller(params=params).verify()
  assert not binary.exists()
  assert (binary.parent / "mapd.quarantined").read_bytes() == b"stock release build"
  assert "MapdVersion" not in params.store


def test_verify_clears_stale_quarantine(env):
  binary, hash_file = env
  binary.write_bytes(b"vetted")
  hash_file.write_text(hashlib.sha256(b"vetted").hexdigest())
  quarantine = binary.parent / "mapd.quarantined"
  quarantine.write_bytes(b"old poison")

  assert vmi.VendorMapdInstaller(params=FakeParams()).verify()
  assert not quarantine.exists()


def test_missing_hash_pin_leaves_binary_alone(env):
  binary, _ = env
  binary.write_bytes(b"anything")

  assert not vmi.VendorMapdInstaller(params=FakeParams()).verify()
  assert binary.exists()


def test_missing_binary(env):
  _, hash_file = env
  hash_file.write_text(hashlib.sha256(b"vetted").hexdigest())

  params = FakeParams()
  params.store["MapdVersion"] = vmi.VENDOR_RELEASE_TAG
  assert not vmi.VendorMapdInstaller(params=params).verify()
  assert "MapdVersion" not in params.store
