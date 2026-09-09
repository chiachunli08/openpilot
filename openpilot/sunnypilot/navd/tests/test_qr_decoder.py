import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from openpilot.sunnypilot.navd import qr_decoder as qr


class TestQrDecoder(unittest.TestCase):
  def setUp(self):
    temporary = tempfile.TemporaryDirectory()
    self.addCleanup(temporary.cleanup)
    self.root = Path(temporary.name)
    (self.root / "old").mkdir()
    (self.root / "current").symlink_to("old")
    for target, value in [("platform.system", "Linux"), ("platform.machine", "aarch64"),
                          ("platform.python_implementation", "CPython")]:
      p = patch.object(getattr(qr, target.split('.')[0]), target.split('.')[1], return_value=value)
      p.start()
      self.addCleanup(p.stop)
    p = patch.object(qr.sys, "version_info", (3, 12))
    p.start()
    self.addCleanup(p.stop)

  def install(self, entry="zxingcpp/__init__.py", digest=None, probe_error=None, cancelled=lambda: False):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
      archive.writestr(entry, "read_barcodes = lambda x: []")
    raw = data.getvalue()
    with patch.object(qr, "WHEELS", {"aarch64": ("test.whl", digest or hashlib.sha256(raw).hexdigest())}), \
         patch.object(qr, "urlopen", return_value=io.BytesIO(raw)), \
         patch.object(qr.subprocess, "run", side_effect=probe_error):
      return qr.install_decoder(self.root, cancelled)

  def assert_preserved(self):
    self.assertEqual((self.root / "current").readlink(), Path("old"))
    self.assertEqual(len(list(self.root.iterdir())), 2)

  def test_install_and_load_without_changing_sys_path(self):
    self.assertEqual(self.install(), qr.VERSION)
    original = list(qr.sys.path)
    self.assertEqual(qr.load_decoder(self.root).read_barcodes(None), [])
    self.assertEqual(qr.sys.path, original)

  def test_invalid_hash_preserves_old_installation(self):
    with self.assertRaisesRegex(RuntimeError, "integrity"):
      self.install(digest="bad")
    self.assert_preserved()

  def test_unsafe_archive_preserves_old_installation(self):
    with self.assertRaisesRegex(RuntimeError, "integrity"):
      self.install(entry="../escape")
    self.assert_preserved()

  def test_incompatible_binary_preserves_old_installation(self):
    with self.assertRaises(OSError):
      self.install(probe_error=OSError("incompatible"))
    self.assert_preserved()

  def test_onroad_cancels_installation(self):
    with self.assertRaisesRegex(RuntimeError, "cancelled"):
      self.install(cancelled=lambda: True)
    self.assert_preserved()
